pub mod board;
pub mod game;
pub mod search;
pub mod tablebase;

pub const VERSION: &str = env!("CARGO_PKG_VERSION");
pub const RULES_ID: &str = "jungle-tiger-ew-quiet100-v1";
pub use board::{Move, Outcome, Position, PositionData, Side};
pub use game::{Command, Game, Settings, Snapshot};
pub use search::{search, SearchOptions, SearchResult};

pub fn inspect(p: &Position) -> serde_json::Value {
    let mut moves = p.moves();
    let outcome = p.outcome(&moves);
    if outcome.ended() {
        moves.clear();
    }
    serde_json::json!({"position":p.data(),"moves":moves,"outcome":outcome,"hash":format!("{:016x}",p.hash),"evaluation":search::evaluate(p,true)})
}

pub fn smoke() -> serde_json::Value {
    let mut p = Position::initial();
    let mut plies = 0;
    loop {
        let moves = p.moves();
        let outcome = p.outcome(&moves);
        if outcome.ended() {
            return serde_json::json!({"passed":true,"plies":plies,"outcome":outcome,"version":VERSION,"rules":RULES_ID});
        }
        if plies >= 1600 {
            return serde_json::json!({"passed":false,"error":"game did not terminate"});
        }
        let result = search(
            &p,
            &SearchOptions {
                node_limit: Some(1000),
                max_depth: Some(4),
                ..SearchOptions::default()
            },
            &|| 0.0,
            &|| false,
            &mut |_| {},
        );
        let Some(m) = result.best_move else {
            return serde_json::json!({"passed":false,"error":"missing legal move"});
        };
        if let Err(e) = p.play(m.from, m.to) {
            return serde_json::json!({"passed":false,"error":e});
        }
        plies += 1;
    }
}
