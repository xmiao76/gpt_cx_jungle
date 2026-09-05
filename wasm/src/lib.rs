use js_sys::Function;
use jungle_engine::{Game, Position, PositionData, SearchOptions};
use wasm_bindgen::prelude::*;

fn error(s: String) -> JsValue {
    JsValue::from_str(&s)
}
fn position(json: &str) -> Result<Position, JsValue> {
    Position::from_data(
        serde_json::from_str::<PositionData>(json).map_err(|e| error(e.to_string()))?,
    )
    .map_err(error)
}
#[wasm_bindgen]
pub struct Engine {
    game: Game,
}
#[wasm_bindgen]
impl Engine {
    #[wasm_bindgen(constructor)]
    pub fn new() -> Self {
        Self {
            game: Game::default(),
        }
    }
    pub fn dispatch(&mut self, request: &str) -> Result<String, JsValue> {
        self.game.dispatch_json(request).map_err(error)
    }
}
impl Default for Engine {
    fn default() -> Self {
        Self::new()
    }
}
#[wasm_bindgen]
pub fn inspect(json: &str) -> Result<String, JsValue> {
    Ok(jungle_engine::inspect(&position(json)?).to_string())
}
#[wasm_bindgen]
pub fn apply(json: &str, from: u8, to: u8) -> Result<String, JsValue> {
    let mut p = position(json)?;
    p.play(from, to).map_err(error)?;
    Ok(jungle_engine::inspect(&p).to_string())
}
#[wasm_bindgen]
pub fn search(json: &str, options: &str, progress: Function) -> Result<String, JsValue> {
    let p = position(json)?;
    let options: SearchOptions = serde_json::from_str(options).map_err(|e| error(e.to_string()))?;
    let performance = js_sys::Reflect::get(&js_sys::global(), &JsValue::from_str("performance"))?
        .dyn_into::<web_sys::Performance>()?;
    let start = performance.now();
    let result = jungle_engine::search(
        &p,
        &options,
        &|| performance.now() - start,
        &|| false,
        &mut |r| {
            if let Ok(json) = serde_json::to_string(r) {
                let _ = progress.call1(&JsValue::NULL, &JsValue::from_str(&json));
            }
        },
    );
    serde_json::to_string(&result).map_err(|e| error(e.to_string()))
}
