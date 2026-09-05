use serde::{Deserialize, Serialize};
use std::sync::OnceLock;

pub const QUIET_LIMIT: u16 = 100;
pub const NAMES: [&str; 9] = [
    "", "Rat", "Cat", "Dog", "Wolf", "Leopard", "Tiger", "Lion", "Elephant",
];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Side {
    Blue,
    Red,
}
impl Side {
    pub fn other(self) -> Self {
        if self == Self::Blue {
            Self::Red
        } else {
            Self::Blue
        }
    }
    pub fn sign(self) -> i8 {
        if self == Self::Blue {
            1
        } else {
            -1
        }
    }
    pub fn index(self) -> usize {
        if self == Self::Blue {
            0
        } else {
            1
        }
    }
    pub fn den(self) -> u8 {
        if self == Self::Blue {
            59
        } else {
            3
        }
    }
}
pub fn side_of(piece: i8) -> Option<Side> {
    if piece > 0 {
        Some(Side::Blue)
    } else if piece < 0 {
        Some(Side::Red)
    } else {
        None
    }
}
pub fn water(square: u8) -> bool {
    (3..=5).contains(&(square / 7)) && matches!(square % 7, 1 | 2 | 4 | 5)
}
pub fn trap(square: u8) -> Option<Side> {
    match square {
        58 | 60 | 52 => Some(Side::Blue),
        2 | 4 | 10 => Some(Side::Red),
        _ => None,
    }
}
pub fn terrain(square: u8) -> &'static str {
    if water(square) {
        "water"
    } else if square == 3 || square == 59 {
        "den"
    } else if trap(square).is_some() {
        "trap"
    } else {
        "land"
    }
}
pub fn neighbor(square: u8, direction: usize) -> Option<u8> {
    let (r, c) = (square / 7, square % 7);
    match direction {
        0 if r > 0 => Some(square - 7),
        1 if c < 6 => Some(square + 1),
        2 if r < 8 => Some(square + 7),
        3 if c > 0 => Some(square - 1),
        _ => None,
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Move {
    pub from: u8,
    pub to: u8,
    pub capture: i8,
    pub jump: bool,
}
impl Move {
    pub fn key(self) -> u16 {
        u16::from(self.from) * 63 + u16::from(self.to)
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct PositionData {
    pub board: Vec<i8>,
    pub side: Side,
    #[serde(default)]
    pub quiet: u16,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Position {
    pub board: [i8; 63],
    pub side: Side,
    pub quiet: u16,
    pub hash: u64,
}

#[derive(Clone, Copy)]
pub struct Undo {
    captured: i8,
    quiet: u16,
    hash: u64,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Outcome {
    pub kind: String,
    pub winner: Option<Side>,
    pub message: String,
}
impl Outcome {
    pub fn ongoing() -> Self {
        Self {
            kind: "ongoing".into(),
            winner: None,
            message: String::new(),
        }
    }
    fn win(kind: &str, winner: Side, reason: &str) -> Self {
        Self {
            kind: kind.into(),
            winner: Some(winner),
            message: format!("{winner:?} wins — {reason}."),
        }
    }
    pub fn ended(&self) -> bool {
        self.kind != "ongoing"
    }
}

pub fn mix(mut x: u64) -> u64 {
    x = x.wrapping_add(0x9e3779b97f4a7c15);
    x = (x ^ (x >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
    x = (x ^ (x >> 27)).wrapping_mul(0x94d049bb133111eb);
    x ^ (x >> 31)
}
fn keys() -> &'static [[u64; 17]; 63] {
    static KEYS: OnceLock<[[u64; 17]; 63]> = OnceLock::new();
    KEYS.get_or_init(|| {
        let mut result = [[0; 17]; 63];
        for (sq, row) in result.iter_mut().enumerate() {
            for (piece, value) in row.iter_mut().enumerate() {
                *value = mix((sq * 17 + piece) as u64 + 0x4a554e474c45);
            }
        }
        result
    })
}
fn piece_key(square: u8, piece: i8) -> u64 {
    if piece == 0 {
        0
    } else {
        keys()[square as usize][(piece + 8) as usize]
    }
}

impl Default for Position {
    fn default() -> Self {
        Self::initial()
    }
}
impl Position {
    pub fn initial() -> Self {
        let mut board = [0; 63];
        for (square, piece) in [
            (42, 8),
            (44, 4),
            (46, 5),
            (48, 1),
            (50, 2),
            (54, 3),
            (56, 6),
            (62, 7),
            (14, -1),
            (16, -5),
            (18, -4),
            (20, -8),
            (8, -3),
            (12, -2),
            (0, -7),
            (6, -6),
        ] {
            board[square] = piece;
        }
        let mut p = Self {
            board,
            side: Side::Blue,
            quiet: 0,
            hash: 0,
        };
        p.rehash();
        p
    }
    pub fn from_data(data: PositionData) -> Result<Self, String> {
        let board: [i8; 63] = data
            .board
            .try_into()
            .map_err(|_| "A board must contain exactly 63 squares.")?;
        let mut seen = [false; 17];
        for (sq, &piece) in board.iter().enumerate() {
            if !(-8..=8).contains(&piece) {
                return Err("Invalid animal rank.".into());
            }
            if piece == 0 {
                continue;
            }
            if seen[(piece + 8) as usize] {
                return Err("Each side may have at most one of each animal.".into());
            }
            seen[(piece + 8) as usize] = true;
            if water(sq as u8) && piece.abs() != 1 {
                return Err("Only rats may occupy water.".into());
            }
            if (sq == 3 && piece < 0) || (sq == 59 && piece > 0) {
                return Err("A piece cannot occupy its own den.".into());
            }
        }
        if board.iter().all(|&p| p == 0) {
            return Err("An empty board is not a game.".into());
        }
        let mut p = Self {
            board,
            side: data.side,
            quiet: data.quiet.min(QUIET_LIMIT),
            hash: 0,
        };
        p.rehash();
        Ok(p)
    }
    pub fn data(&self) -> PositionData {
        PositionData {
            board: self.board.to_vec(),
            side: self.side,
            quiet: self.quiet,
        }
    }
    pub fn rehash(&mut self) {
        self.hash = if self.side == Side::Red {
            mix(99999)
        } else {
            0
        };
        for (sq, &piece) in self.board.iter().enumerate() {
            self.hash ^= piece_key(sq as u8, piece);
        }
    }
    pub fn tt_key(&self) -> u64 {
        self.hash ^ mix(100000 + self.quiet as u64)
    }
    pub fn effective_rank(&self, square: u8) -> i8 {
        let piece = self.board[square as usize];
        if side_of(piece).is_some_and(|side| trap(square) == Some(side.other())) {
            0
        } else {
            piece.abs()
        }
    }
    pub fn can_capture(&self, from: u8, to: u8) -> bool {
        let (a, b) = (self.board[from as usize], self.board[to as usize]);
        if a == 0 || b == 0 || a.signum() == b.signum() {
            return false;
        }
        if water(from) || water(to) {
            return water(from) && water(to) && a.abs() == 1 && b.abs() == 1;
        }
        if a.abs() == 1 && b.abs() == 8 {
            return true;
        }
        if a.abs() == 8 && b.abs() == 1 {
            return trap(to) == side_of(a);
        }
        self.effective_rank(from) >= self.effective_rank(to)
    }
    pub fn moves(&self) -> Vec<Move> {
        let mut out = Vec::with_capacity(32);
        self.generate(&mut out);
        out
    }
    pub fn generate(&self, out: &mut Vec<Move>) {
        out.clear();
        for from in 0..63u8 {
            let piece = self.board[from as usize];
            if side_of(piece) != Some(self.side) {
                continue;
            }
            for direction in 0..4 {
                let Some(mut to) = neighbor(from, direction) else {
                    continue;
                };
                let mut jump = false;
                if water(to) && piece.abs() != 1 {
                    if piece.abs() != 7 && piece.abs() != 6 {
                        continue;
                    }
                    if piece.abs() == 6 && direction % 2 == 0 {
                        continue;
                    }
                    let mut blocked = false;
                    while water(to) {
                        if self.board[to as usize] != 0 {
                            blocked = true;
                            break;
                        }
                        if let Some(next) = neighbor(to, direction) {
                            to = next;
                        } else {
                            blocked = true;
                            break;
                        }
                    }
                    if blocked {
                        continue;
                    }
                    jump = true;
                }
                if to == self.side.den() {
                    continue;
                }
                let target = self.board[to as usize];
                if target == 0 || self.can_capture(from, to) {
                    out.push(Move {
                        from,
                        to,
                        capture: target,
                        jump,
                    });
                }
            }
        }
    }
    pub fn outcome(&self, moves: &[Move]) -> Outcome {
        if self.board[3] > 0 {
            return Outcome::win("den_entry", Side::Blue, "the opposing den was reached");
        }
        if self.board[59] < 0 {
            return Outcome::win("den_entry", Side::Red, "the opposing den was reached");
        }
        if !self.board.iter().any(|&p| p > 0) {
            return Outcome::win(
                "capture_all",
                Side::Red,
                "all opposing animals were captured",
            );
        }
        if !self.board.iter().any(|&p| p < 0) {
            return Outcome::win(
                "capture_all",
                Side::Blue,
                "all opposing animals were captured",
            );
        }
        if moves.is_empty() {
            return Outcome::win(
                "no_legal_moves",
                self.side.other(),
                "the opponent has no legal move",
            );
        }
        if self.quiet >= QUIET_LIMIT {
            return Outcome {
                kind: "no_capture_draw".into(),
                winner: None,
                message: "Draw — 100 plies without a capture.".into(),
            };
        }
        Outcome::ongoing()
    }
    pub fn play(&mut self, from: u8, to: u8) -> Result<Move, String> {
        let moves = self.moves();
        if self.outcome(&moves).ended() {
            return Err("This game has ended. Undo or start a new game.".into());
        }
        let mv = *moves
            .iter()
            .find(|m| m.from == from && m.to == to)
            .ok_or("That move is not legal.")?;
        self.make(mv);
        Ok(mv)
    }
    pub fn make(&mut self, mv: Move) -> Undo {
        let captured = self.board[mv.to as usize];
        let undo = Undo {
            captured,
            quiet: self.quiet,
            hash: self.hash,
        };
        let piece = self.board[mv.from as usize];
        self.hash ^= piece_key(mv.from, piece)
            ^ piece_key(mv.to, piece)
            ^ piece_key(mv.to, captured)
            ^ mix(99999);
        self.board[mv.to as usize] = piece;
        self.board[mv.from as usize] = 0;
        self.side = self.side.other();
        self.quiet = if captured == 0 {
            self.quiet.saturating_add(1)
        } else {
            0
        };
        undo
    }
    pub fn unmake(&mut self, mv: Move, undo: Undo) {
        self.board[mv.from as usize] = self.board[mv.to as usize];
        self.board[mv.to as usize] = undo.captured;
        self.side = self.side.other();
        self.quiet = undo.quiet;
        self.hash = undo.hash;
    }
}
pub fn perft(p: &mut Position, depth: u8) -> u64 {
    if depth == 0 {
        return 1;
    }
    let moves = p.moves();
    if p.outcome(&moves).ended() {
        return 0;
    }
    if depth == 1 {
        return moves.len() as u64;
    }
    moves
        .into_iter()
        .map(|m| {
            let u = p.make(m);
            let count = perft(p, depth - 1);
            p.unmake(m, u);
            count
        })
        .sum()
}
