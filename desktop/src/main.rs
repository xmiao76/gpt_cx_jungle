#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use jungle_engine::{Game, Position, PositionData, SearchOptions};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc, Mutex,
};
use std::time::Instant;
use tauri::{Emitter, Manager, State};

fn fit_initial_window(window: &tauri::WebviewWindow) -> tauri::Result<()> {
    let Some(monitor) = window.current_monitor()? else {
        return Ok(());
    };
    let area = monitor.work_area();
    let scale = window.scale_factor()?;
    let inner = window.inner_size()?;
    let outer = window.outer_size()?;
    let border_width = outer.width.saturating_sub(inner.width);
    let border_height = outer.height.saturating_sub(inner.height);
    let margin = (12.0 * scale).ceil() as u32;
    let width = inner.width.min(
        area.size
            .width
            .saturating_sub(border_width + margin * 2)
            .max(1),
    );
    let height = inner.height.min(
        area.size
            .height
            .saturating_sub(border_height + margin * 2)
            .max(1),
    );
    // Constrain this application only, respecting taskbars and display scaling.
    window.set_min_size(Some(tauri::PhysicalSize::new(
        ((720.0 * scale) as u32).min(width),
        ((560.0 * scale) as u32).min(height),
    )))?;
    window.set_size(tauri::PhysicalSize::new(width, height))?;
    window.set_position(tauri::PhysicalPosition::new(
        area.position.x + (area.size.width.saturating_sub(width + border_width) / 2) as i32,
        area.position.y + (area.size.height.saturating_sub(height + border_height) / 2) as i32,
    ))?;
    Ok(())
}

#[tauri::command]
fn diagnostic_bounds(window: tauri::WebviewWindow) -> Result<serde_json::Value, String> {
    if std::env::var("JUNGLE_GUI_TEST").as_deref() != Ok("1") {
        return Err("Window diagnostics are disabled.".into());
    }
    let monitor = window.current_monitor().map_err(|e| e.to_string())?;
    Ok(serde_json::json!({
        "outer": window.outer_size().map_err(|e| e.to_string())?,
        "position": window.outer_position().map_err(|e| e.to_string())?,
        "workArea": monitor.as_ref().map(|m| m.work_area())
    }))
}
#[tauri::command]
async fn diagnostic_window(
    window: tauri::WebviewWindow,
    scale: f64,
    width: u32,
    height: u32,
) -> Result<serde_json::Value, String> {
    if std::env::var("JUNGLE_GUI_TEST").as_deref() != Ok("1") {
        return Err("Window diagnostics are disabled.".into());
    }
    if !(0.75..=3.0).contains(&scale)
        || !(720..=1800).contains(&width)
        || !(560..=1200).contains(&height)
    {
        return Err("Invalid diagnostic dimensions.".into());
    }
    let system_scale = window.scale_factor().map_err(|e| e.to_string())?;
    window
        .set_min_size(None::<tauri::PhysicalSize<u32>>)
        .map_err(|e| e.to_string())?;
    window
        .set_size(tauri::PhysicalSize::new(
            (f64::from(width) * scale) as u32,
            (f64::from(height) * scale) as u32,
        ))
        .map_err(|e| e.to_string())?;
    #[cfg(windows)]
    {
        let (tx, rx) = std::sync::mpsc::sync_channel(1);
        window
            .with_webview(move |webview| {
                use webview2_com::Microsoft::Web::WebView2::Win32::{
                    ICoreWebView2Controller3, COREWEBVIEW2_BOUNDS_MODE_USE_RAW_PIXELS,
                };
                use windows_core::Interface;
                let result = (|| -> Result<(), String> {
                    let controller: ICoreWebView2Controller3 =
                        webview.controller().cast().map_err(|e| e.to_string())?;
                    // This changes only this application WebView, never the user's display settings.
                    unsafe {
                        controller
                            .SetShouldDetectMonitorScaleChanges(false)
                            .map_err(|e| e.to_string())?;
                        controller
                            .SetBoundsMode(COREWEBVIEW2_BOUNDS_MODE_USE_RAW_PIXELS)
                            .map_err(|e| e.to_string())?;
                        controller
                            .SetRasterizationScale(scale)
                            .map_err(|e| e.to_string())?;
                    }
                    Ok(())
                })();
                let _ = tx.send(result);
            })
            .map_err(|e| e.to_string())?;
        tauri::async_runtime::spawn_blocking(move || {
            rx.recv_timeout(std::time::Duration::from_secs(5))
        })
        .await
        .map_err(|e| e.to_string())?
        .map_err(|e| e.to_string())??;
    }
    Ok(
        serde_json::json!({"system_scale":system_scale,"rasterization_scale":scale,"width":width,"height":height}),
    )
}
struct RunningSearch {
    job: String,
    flag: Arc<AtomicBool>,
}
struct AppState {
    game: Mutex<Game>,
    cancel: Mutex<Option<RunningSearch>>,
}
impl AppState {
    fn stop(&self) {
        if let Some(search) = self.cancel.lock().unwrap().take() {
            search.flag.store(true, Ordering::Relaxed);
        }
    }
}
#[tauri::command]
fn engine_command(request: String, state: State<'_, AppState>) -> Result<String, String> {
    let value: serde_json::Value = serde_json::from_str(&request).map_err(|e| e.to_string())?;
    // State changes and search registration share the same lock order. A reset
    // cannot slip between validating a position and registering its cancel flag.
    let mut game = state.game.lock().map_err(|_| "Game state unavailable.")?;
    if !matches!(value["type"].as_str(), Some("snapshot" | "export")) {
        state.stop();
    }
    game.dispatch_json(&request)
}
#[tauri::command]
fn cancel_search(job: Option<String>, state: State<'_, AppState>) {
    let mut current = state.cancel.lock().unwrap();
    if current
        .as_ref()
        .is_some_and(|search| job.as_ref().is_none_or(|id| id == &search.job))
    {
        if let Some(search) = current.take() {
            search.flag.store(true, Ordering::Relaxed);
        }
    }
}
#[tauri::command]
async fn engine_search(
    position: String,
    options: String,
    job: String,
    revision: Option<u32>,
    app: tauri::AppHandle,
    state: State<'_, AppState>,
) -> Result<String, String> {
    let p = Position::from_data(
        serde_json::from_str::<PositionData>(&position).map_err(|e| e.to_string())?,
    )?;
    let options: SearchOptions = serde_json::from_str(&options).map_err(|e| e.to_string())?;
    let cancel = Arc::new(AtomicBool::new(false));
    {
        let game = state.game.lock().map_err(|_| "Game state unavailable.")?;
        if revision.is_some_and(|r| r != game.revision()) || &p != game.position() {
            return Err("The position changed before search started.".into());
        }
        state.stop();
        *state.cancel.lock().unwrap() = Some(RunningSearch {
            job: job.clone(),
            flag: cancel.clone(),
        });
    }
    tauri::async_runtime::spawn_blocking(move || {
        let start = Instant::now();
        let result = jungle_engine::search(
            &p,
            &options,
            &|| start.elapsed().as_secs_f64() * 1000.0,
            &|| cancel.load(Ordering::Relaxed),
            &mut |result| {
                let _ = app.emit(
                    "search-progress",
                    serde_json::json!({"job":job,"result":result}),
                );
            },
        );
        serde_json::to_string(&result).map_err(|e| e.to_string())
    })
    .await
    .map_err(|e| e.to_string())?
}
#[tauri::command]
async fn save_game(state: State<'_, AppState>) -> Result<bool, String> {
    let contents = state
        .game
        .lock()
        .map_err(|_| "Game state unavailable.")?
        .save()?;
    let Some(file) = rfd::AsyncFileDialog::new()
        .add_filter("Jungle save", &["json"])
        .set_file_name("jungle-save.json")
        .save_file()
        .await
    else {
        return Ok(false);
    };
    file.write(contents.as_bytes())
        .await
        .map_err(|e| e.to_string())?;
    Ok(true)
}
#[tauri::command]
async fn open_game() -> Result<Option<String>, String> {
    let Some(file) = rfd::AsyncFileDialog::new()
        .add_filter("Jungle save", &["json"])
        .pick_file()
        .await
    else {
        return Ok(None);
    };
    if std::fs::metadata(file.path())
        .map_err(|e| e.to_string())?
        .len()
        > 4 * 1024 * 1024
    {
        return Err("Save files must be smaller than 4 MiB.".into());
    }
    String::from_utf8(file.read().await)
        .map(Some)
        .map_err(|_| "Save file is not UTF-8.".into())
}
fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.iter().any(|a| a == "--smoke-test") {
        let report = jungle_engine::smoke();
        let output = serde_json::to_string_pretty(&report).unwrap();
        if let Some(i) = args.iter().position(|a| a == "--report") {
            if let Some(path) = args.get(i + 1) {
                if let Err(e) = std::fs::write(path, &output) {
                    eprintln!("{e}");
                    std::process::exit(2);
                }
            }
        }
        println!("{output}");
        std::process::exit(if report["passed"] == true { 0 } else { 1 });
    }
    tauri::Builder::default()
        .setup(|app| {
            if let Some(window) = app.get_webview_window("main") {
                fit_initial_window(&window)?;
            }
            Ok(())
        })
        .manage(AppState {
            game: Mutex::new(Game::default()),
            cancel: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            engine_command,
            engine_search,
            cancel_search,
            save_game,
            open_game,
            diagnostic_window,
            diagnostic_bounds
        ])
        .run(tauri::generate_context!())
        .expect("Unable to launch Jungle.");
}
