use crate::board::{side_of, terrain, trap, Move, Outcome, Position, PositionData, Side, NAMES};
use crate::{RULES_ID, VERSION};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(default)]
pub struct Settings {
    pub human: Side,
    pub difficulty: String,
    pub mode: String,
}
impl Default for Settings {
    fn default() -> Self {
        Self {
            human: Side::Blue,
            difficulty: "medium".into(),
            mode: "human".into(),
        }
    }
}
impl Settings {
    pub fn validate(&self) -> Result<(), String> {
        if !["easy", "medium", "hard"].contains(&self.difficulty.as_str()) {
            return Err("Unknown difficulty.".into());
        }
        if !["human", "watch"].contains(&self.mode.as_str()) {
            return Err("Unknown game mode.".into());
        }
        Ok(())
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct HistoryMove {
    pub from: u8,
    pub to: u8,
    pub piece: i8,
    pub capture: i8,
    pub jump: bool,
    pub notation: String,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TerrainInfo {
    pub kind: String,
    pub owner: Option<Side>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Snapshot {
    pub protocol_version: u8,
    pub revision: u32,
    pub version: String,
    pub rules_id: String,
    pub position: PositionData,
    pub legal_moves: Vec<Move>,
    pub outcome: Outcome,
    pub history: Vec<HistoryMove>,
    pub cursor: usize,
    pub captured: Vec<i8>,
    pub settings: Settings,
    pub can_undo: bool,
    pub can_redo: bool,
    pub terrain: Vec<TerrainInfo>,
}
#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Command {
    Snapshot,
    New { settings: Settings },
    Move { from: u8, to: u8, revision: u32 },
    Undo,
    Redo,
    Settings { settings: Settings },
    Import { contents: String },
    Export,
}
#[derive(Clone, Serialize, Deserialize)]
pub struct SaveGame {
    pub format_version: u8,
    pub rules_id: String,
    pub initial: PositionData,
    pub moves: Vec<Move>,
    pub cursor: usize,
    pub settings: Settings,
}
#[derive(Clone)]
pub struct Game {
    states: Vec<Position>,
    moves: Vec<Move>,
    pub cursor: usize,
    pub settings: Settings,
    revision: u32,
}
impl Default for Game {
    fn default() -> Self {
        Self::new(Settings::default())
    }
}
fn coordinate(sq: u8) -> String {
    format!("{}{}", char::from(b'a' + sq % 7), 9 - sq / 7)
}
impl Game {
    pub fn new(settings: Settings) -> Self {
        Self {
            states: vec![Position::initial()],
            moves: vec![],
            cursor: 0,
            settings,
            revision: 1,
        }
    }
    pub fn position(&self) -> &Position {
        &self.states[self.cursor]
    }
    pub fn revision(&self) -> u32 {
        self.revision
    }
    fn changed(&mut self) {
        self.revision = self.revision.wrapping_add(1);
    }
    fn undo_target(&self) -> Option<usize> {
        if self.cursor == 0 {
            return None;
        }
        if self.settings.mode == "watch" {
            return Some(self.cursor - 1);
        }
        (0..self.cursor)
            .rev()
            .find(|&i| self.states[i].side == self.settings.human)
    }
    pub fn snapshot(&self) -> Snapshot {
        let p = self.position();
        let mut legal_moves = p.moves();
        let outcome = p.outcome(&legal_moves);
        if outcome.ended() {
            legal_moves.clear();
        }
        let history = self
            .moves
            .iter()
            .enumerate()
            .map(|(i, m)| {
                let piece = self.states[i].board[m.from as usize];
                HistoryMove {
                    from: m.from,
                    to: m.to,
                    piece,
                    capture: m.capture,
                    jump: m.jump,
                    notation: format!(
                        "{} {}{}{}{}",
                        NAMES[piece.unsigned_abs() as usize],
                        coordinate(m.from),
                        if m.capture != 0 { " × " } else { " → " },
                        coordinate(m.to),
                        if m.jump { " · jump" } else { "" }
                    ),
                }
            })
            .collect();
        let terrain = (0..63)
            .map(|sq| TerrainInfo {
                kind: terrain(sq).into(),
                owner: if sq == 3 {
                    Some(Side::Red)
                } else if sq == 59 {
                    Some(Side::Blue)
                } else {
                    trap(sq)
                },
            })
            .collect();
        Snapshot {
            protocol_version: 1,
            revision: self.revision,
            version: VERSION.into(),
            rules_id: RULES_ID.into(),
            position: p.data(),
            legal_moves,
            outcome,
            history,
            cursor: self.cursor,
            captured: self.moves[..self.cursor]
                .iter()
                .filter_map(|m| (m.capture != 0).then_some(m.capture))
                .collect(),
            settings: self.settings.clone(),
            can_undo: self.undo_target().is_some(),
            can_redo: self.cursor < self.moves.len(),
            terrain,
        }
    }
    pub fn apply(&mut self, from: u8, to: u8, revision: u32) -> Result<(), String> {
        if revision != self.revision {
            return Err("The position changed; that result is obsolete.".into());
        }
        let mut next = self.position().clone();
        let mv = next.play(from, to)?;
        self.states.truncate(self.cursor + 1);
        self.moves.truncate(self.cursor);
        self.states.push(next);
        self.moves.push(mv);
        self.cursor += 1;
        self.changed();
        Ok(())
    }
    pub fn undo(&mut self) -> Result<(), String> {
        self.cursor = self
            .undo_target()
            .ok_or("There is no earlier decision to undo.")?;
        self.changed();
        Ok(())
    }
    pub fn redo(&mut self) -> Result<(), String> {
        if self.cursor == self.moves.len() {
            return Err("There is no move to redo.".into());
        }
        self.cursor = if self.settings.mode == "watch" {
            self.cursor + 1
        } else {
            ((self.cursor + 1)..=self.moves.len())
                .find(|&i| {
                    self.states[i].side == self.settings.human
                        || self.states[i].outcome(&self.states[i].moves()).ended()
                })
                .unwrap_or(self.moves.len())
        };
        self.changed();
        Ok(())
    }
    pub fn save(&self) -> Result<String, String> {
        serde_json::to_string_pretty(&SaveGame {
            format_version: 1,
            rules_id: RULES_ID.into(),
            initial: self.states[0].data(),
            moves: self.moves.clone(),
            cursor: self.cursor,
            settings: self.settings.clone(),
        })
        .map_err(|e| e.to_string())
    }
    pub fn from_save(save: SaveGame) -> Result<Self, String> {
        if save.format_version != 1 || save.rules_id != RULES_ID {
            return Err("This save uses an unsupported version or rules profile.".into());
        }
        save.settings.validate()?;
        if save.moves.len() > 4096 || save.cursor > save.moves.len() {
            return Err("Invalid save history length or cursor.".into());
        }
        let mut p = Position::from_data(save.initial)?;
        let mut states = vec![p.clone()];
        for mv in &save.moves {
            let actual = p
                .play(mv.from, mv.to)
                .map_err(|e| format!("Invalid saved move {}: {e}", states.len()))?;
            if actual != *mv {
                return Err("Saved capture or jump metadata does not match the rules.".into());
            }
            states.push(p.clone());
        }
        Ok(Self {
            states,
            moves: save.moves,
            cursor: save.cursor,
            settings: save.settings,
            revision: 1,
        })
    }
    pub fn import(&mut self, contents: &str) -> Result<(), String> {
        if contents.len() > 4 * 1024 * 1024 {
            return Err("Save files must be smaller than 4 MiB.".into());
        }
        let value: Value =
            serde_json::from_str(contents).map_err(|_| "This file is not valid JSON.")?;
        let mut next = if value.get("format_version").is_some() {
            Self::from_save(
                serde_json::from_value(value).map_err(|e| format!("Invalid save: {e}"))?,
            )?
        } else {
            Self::from_legacy(value, self.settings.clone())?
        };
        next.revision = self.revision.wrapping_add(1);
        *self = next;
        Ok(())
    }
    fn from_legacy(value: Value, settings: Settings) -> Result<Self, String> {
        #[derive(Deserialize)]
        struct Piece {
            side: Side,
            kind: String,
        }
        impl Piece {
            fn code(&self) -> Result<i8, String> {
                NAMES
                    .iter()
                    .position(|n| n.eq_ignore_ascii_case(&self.kind))
                    .filter(|&i| i > 0)
                    .map(|i| i as i8 * self.side.sign())
                    .ok_or_else(|| "Unknown animal in legacy save.".into())
            }
        }
        #[derive(Deserialize)]
        struct OldMove {
            origin: u8,
            destination: u8,
            piece: Piece,
            captured: Option<Piece>,
            #[serde(default)]
            is_jump: bool,
        }
        #[derive(Deserialize)]
        struct Legacy {
            board: Vec<Option<Piece>>,
            side_to_move: Side,
            #[serde(default)]
            move_history: Vec<OldMove>,
        }
        let old: Legacy =
            serde_json::from_value(value).map_err(|e| format!("Unrecognized legacy save: {e}"))?;
        if old.board.len() != 63 || old.move_history.len() > 4096 {
            return Err("Invalid legacy board or history length.".into());
        }
        let board = old
            .board
            .iter()
            .map(|p| p.as_ref().map_or(Ok(0), Piece::code))
            .collect::<Result<Vec<_>, _>>()?;
        let final_board = board.clone();
        let mut initial = Position::from_data(PositionData {
            board,
            side: old.side_to_move,
            quiet: 0,
        })?;
        let mut moves = Vec::new();
        for m in &old.move_history {
            if m.origin >= 63 || m.destination >= 63 {
                return Err("Legacy move is outside the board.".into());
            }
            moves.push(Move {
                from: m.origin,
                to: m.destination,
                capture: m.captured.as_ref().map_or(Ok(0), Piece::code)?,
                jump: m.is_jump,
            });
        }
        for (m, old_move) in moves.iter().zip(&old.move_history).rev() {
            let piece = old_move.piece.code()?;
            if initial.board[m.to as usize] != piece
                || initial.board[m.from as usize] != 0
                || side_of(piece) != Some(initial.side.other())
            {
                return Err("Legacy board and move history disagree.".into());
            }
            initial.board[m.from as usize] = piece;
            initial.board[m.to as usize] = m.capture;
            initial.side = initial.side.other();
        }
        initial.rehash();
        let game = Self::from_save(SaveGame {
            format_version: 1,
            rules_id: RULES_ID.into(),
            initial: initial.data(),
            cursor: moves.len(),
            moves,
            settings,
        })?;
        if game.position().board.as_slice() != final_board
            || game.position().side != old.side_to_move
        {
            return Err("Legacy board does not match replayed history.".into());
        }
        Ok(game)
    }
    pub fn dispatch(&mut self, command: Command) -> Result<Value, String> {
        match command {
            Command::Snapshot => {}
            Command::New { settings } => {
                settings.validate()?;
                let revision = self.revision.wrapping_add(1);
                *self = Self::new(settings);
                self.revision = revision;
            }
            Command::Move { from, to, revision } => self.apply(from, to, revision)?,
            Command::Undo => self.undo()?,
            Command::Redo => self.redo()?,
            Command::Settings { settings } => {
                settings.validate()?;
                self.settings = settings;
                self.changed();
            }
            Command::Import { contents } => self.import(&contents)?,
            Command::Export => return Ok(json!({"save":self.save()?})),
        }
        serde_json::to_value(self.snapshot()).map_err(|e| e.to_string())
    }
    pub fn dispatch_json(&mut self, request: &str) -> Result<String, String> {
        let command =
            serde_json::from_str(request).map_err(|e| format!("Invalid engine command: {e}"))?;
        serde_json::to_string(&self.dispatch(command)?).map_err(|e| e.to_string())
    }
}
