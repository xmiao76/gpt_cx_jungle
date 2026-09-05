use jungle_engine::board::{mix, perft};
use jungle_engine::{search, Game, Position, PositionData, SearchOptions};
use serde_json::{json, Value};
use std::io::{self, BufRead, Write};
use std::time::Instant;

fn answer(v: Value) -> Result<Value, String> {
    let op = v["op"].as_str().unwrap_or("inspect");
    let p = if v.get("position").is_some() {
        Position::from_data(
            serde_json::from_value::<PositionData>(v["position"].clone())
                .map_err(|e| e.to_string())?,
        )?
    } else {
        Position::initial()
    };
    match op {
        "search" => {
            let options: SearchOptions =
                serde_json::from_value(v.get("options").cloned().unwrap_or(json!({})))
                    .map_err(|e| e.to_string())?;
            let start = Instant::now();
            let result = search(
                &p,
                &options,
                &|| start.elapsed().as_secs_f64() * 1000.0,
                &|| false,
                &mut |_| {},
            );
            Ok(serde_json::to_value(result).unwrap())
        }
        "inspect" => Ok(jungle_engine::inspect(&p)),
        "apply" => {
            let mut next = p;
            let from = v["from"]
                .as_u64()
                .filter(|n| *n < 63)
                .ok_or("Invalid origin.")? as u8;
            let to = v["to"]
                .as_u64()
                .filter(|n| *n < 63)
                .ok_or("Invalid destination.")? as u8;
            next.play(from, to)?;
            Ok(jungle_engine::inspect(&next))
        }
        "session" => {
            let mut g = Game::default();
            g.dispatch_json(&v["command"].to_string())
                .and_then(|s| serde_json::from_str(&s).map_err(|e| e.to_string()))
        }
        _ => Err("Unknown operation.".into()),
    }
}
fn main() {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("serve") => {
            for line in io::stdin().lock().lines() {
                let response = line
                    .map_err(|e| e.to_string())
                    .and_then(|s| serde_json::from_str(&s).map_err(|e| e.to_string()))
                    .and_then(answer);
                println!(
                    "{}",
                    match response {
                        Ok(v) => v,
                        Err(e) => json!({"error":e}),
                    }
                );
                let _ = io::stdout().flush();
            }
        }
        Some("perft") => {
            let d = args.get(2).and_then(|s| s.parse::<u8>().ok()).unwrap_or(4);
            println!(
                "{}",
                json!({"depth":d,"nodes":perft(&mut Position::initial(),d)})
            );
        }
        Some("corpus") => {
            let count = args
                .get(2)
                .and_then(|s| s.parse::<usize>().ok())
                .unwrap_or(10000);
            let mut p = Position::initial();
            let mut seed = 42u64;
            for i in 0..count {
                println!("{}", json!({"id":i,"expected":jungle_engine::inspect(&p)}));
                let moves = p.moves();
                if p.outcome(&moves).ended() {
                    p = Position::initial();
                } else {
                    seed = mix(seed);
                    p.make(moves[seed as usize % moves.len()]);
                }
            }
        }
        Some("smoke") => {
            let result = jungle_engine::smoke();
            println!("{result}");
            if result["passed"] != true {
                std::process::exit(1);
            }
        }
        _ => {
            let start = Instant::now();
            let result = search(
                &Position::initial(),
                &SearchOptions::default(),
                &|| start.elapsed().as_secs_f64() * 1000.0,
                &|| false,
                &mut |_| {},
            );
            println!("{}", serde_json::to_string(&result).unwrap());
        }
    }
}
