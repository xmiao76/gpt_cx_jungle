use crate::board::{neighbor, side_of, trap, water, Move, Position, Side};
use serde::{Deserialize, Serialize};
const MATE: i32 = 100_000;
const INF: i32 = 110_000;
const MAX_PLY: usize = 100;
const VALUES: [i32; 9] = [0, 140, 190, 260, 340, 480, 620, 800, 1050];
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct SearchOptions {
    pub difficulty: String,
    pub time_ms: f64,
    pub node_limit: Option<u64>,
    pub profile: String,
    pub max_depth: Option<u8>,
}
impl Default for SearchOptions {
    fn default() -> Self {
        Self {
            difficulty: "hard".into(),
            time_ms: 1900.0,
            node_limit: None,
            profile: "candidate".into(),
            max_depth: None,
        }
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SearchResult {
    pub best_move: Option<Move>,
    pub score: i32,
    pub depth: u8,
    pub nodes: u64,
    pub elapsed_ms: f64,
    pub pv: Vec<Move>,
    pub tt_hits: u64,
    pub tablebase_hits: u64,
    pub aborted: bool,
    pub profile: String,
}
#[derive(Clone, Copy, Default)]
struct Entry {
    key: u64,
    score: i32,
    depth: i16,
    bound: u8,
    mv: u16,
}
struct Searcher<'a> {
    table: Vec<Entry>,
    clock: &'a dyn Fn() -> f64,
    cancel: &'a dyn Fn() -> bool,
    start: f64,
    deadline: f64,
    limit: Option<u64>,
    nodes: u64,
    hits: u64,
    tablebase_hits: u64,
    tablebase: bool,
    candidate: bool,
    lmr: bool,
    quiescence: bool,
    killers: [[u16; 2]; MAX_PLY],
    history: Box<[[[i32; 63]; 63]; 2]>,
    lists: Vec<Vec<Move>>,
}
pub fn immediate_den_threat(p: &Position, attacker: Side) -> bool {
    let target = attacker.other().den();
    (0..4)
        .filter_map(|d| neighbor(target, d))
        .any(|sq| side_of(p.board[sq as usize]) == Some(attacker))
}
pub fn evaluate(p: &Position, candidate: bool) -> i32 {
    let mut score = 0;
    for (i, &piece) in p.board.iter().enumerate() {
        let Some(side) = side_of(piece) else {
            continue;
        };
        let sq = i as u8;
        let rank = piece.unsigned_abs() as usize;
        let (r, c) = (i / 7, i % 7);
        let distance = if side == Side::Blue { r } else { 8 - r };
        let col_distance = (c as i32 - 3).abs();
        let progress = 8 - distance as i32;
        let mut value = VALUES[rank] + progress * 9;
        if candidate {
            value += progress * 13 + (6 - (distance as i32 + col_distance)).max(0) * 32;
            if matches!(c, 0 | 3 | 6) {
                value += 16;
            }
            if rank == 1 && p.board.contains(&(side.other().sign() * 8)) {
                value += 130;
            }
            if rank == 1 && water(sq) {
                value += 42;
            }
            if rank == 6 || rank == 7 {
                value += 30;
            }
            if trap(sq) == Some(side.other()) {
                value -= VALUES[rank] * 3 / 4;
            }
            if distance as i32 + col_distance == 1 {
                value += 6000;
            }
            let own_distance = if side == Side::Blue { 8 - r } else { r };
            if own_distance as i32 + col_distance <= 2 {
                value += 35;
            }
        }
        score += value * i32::from(side.sign());
    }
    let relative = score * i32::from(p.side.sign());
    if candidate && p.quiet > 80 {
        relative * i32::from(100 - p.quiet.min(100)) / 20
    } else {
        relative
    }
}
fn stored(score: i32, ply: usize) -> i32 {
    if score > MATE - 1000 {
        score + ply as i32
    } else if score < -MATE + 1000 {
        score - ply as i32
    } else {
        score
    }
}
fn restored(score: i32, ply: usize) -> i32 {
    if score > MATE - 1000 {
        score - ply as i32
    } else if score < -MATE + 1000 {
        score + ply as i32
    } else {
        score
    }
}
impl Searcher<'_> {
    fn check(&mut self) -> Result<(), ()> {
        self.nodes += 1;
        if self.limit.is_some_and(|n| self.nodes >= n) {
            return Err(());
        }
        if self.nodes.is_multiple_of(128) && ((self.cancel)() || (self.clock)() >= self.deadline) {
            return Err(());
        }
        Ok(())
    }
    fn terminal(p: &Position, moves: &[Move], ply: usize) -> Option<i32> {
        let outcome = p.outcome(moves);
        if !outcome.ended() {
            None
        } else {
            Some(outcome.winner.map_or(0, |side| {
                if side == p.side {
                    MATE - ply as i32
                } else {
                    -MATE + ply as i32
                }
            }))
        }
    }
    fn order(&self, p: &Position, m: Move, tt: u16, ply: usize) -> i32 {
        if m.to == p.side.other().den() {
            return 2_000_000;
        }
        if m.key() == tt {
            return 1_000_000;
        }
        let mut score = 0;
        if m.capture != 0 {
            score += 100_000 + VALUES[m.capture.unsigned_abs() as usize] * 16
                - VALUES[p.board[m.from as usize].unsigned_abs() as usize];
        }
        if self.candidate {
            if self.killers[ply][0] == m.key() {
                score += 80_000;
            } else if self.killers[ply][1] == m.key() {
                score += 70_000;
            }
            score += self.history[p.side.index()][m.from as usize][m.to as usize];
            if m.jump {
                score += 400;
            }
            let row = m.to / 7;
            score += if p.side == Side::Blue {
                i32::from(8 - row)
            } else {
                i32::from(row)
            } * 12;
        }
        score
    }
    fn qsearch(
        &mut self,
        p: &mut Position,
        mut alpha: i32,
        beta: i32,
        ply: usize,
        qdepth: u8,
    ) -> Result<i32, ()> {
        self.check()?;
        let mut moves = std::mem::take(&mut self.lists[ply]);
        p.generate(&mut moves);
        if let Some(result) = Self::terminal(p, &moves, ply) {
            self.lists[ply] = moves;
            return Ok(result);
        }
        let value = evaluate(p, self.candidate);
        if self.tablebase {
            if let Some(score) = crate::tablebase::probe(p, ply) {
                self.tablebase_hits += 1;
                self.lists[ply] = moves;
                return Ok(score);
            }
        }
        if ply >= MAX_PLY - 2 || qdepth >= 6 {
            self.lists[ply] = moves;
            return Ok(value);
        }
        let threatened = immediate_den_threat(p, p.side.other());
        if !threatened {
            if value >= beta {
                self.lists[ply] = moves;
                return Ok(value);
            }
            alpha = alpha.max(value);
            moves.retain(|m| m.capture != 0 || m.to == p.side.other().den());
        }
        moves.sort_unstable_by_key(|m| (-self.order(p, *m, u16::MAX, ply), m.key()));
        for &m in &moves {
            let undo = p.make(m);
            let result = self.qsearch(p, -beta, -alpha, ply + 1, qdepth + 1);
            p.unmake(m, undo);
            let score = -result?;
            if score >= beta {
                self.lists[ply] = moves;
                return Ok(score);
            }
            alpha = alpha.max(score);
        }
        self.lists[ply] = moves;
        Ok(alpha)
    }
    fn node(
        &mut self,
        p: &mut Position,
        depth: i16,
        mut alpha: i32,
        beta: i32,
        ply: usize,
    ) -> Result<i32, ()> {
        self.check()?;
        if depth <= 0 && self.quiescence {
            return self.qsearch(p, alpha, beta, ply, 0);
        }
        let mut moves = std::mem::take(&mut self.lists[ply]);
        p.generate(&mut moves);
        if let Some(result) = Self::terminal(p, &moves, ply) {
            self.lists[ply] = moves;
            return Ok(result);
        }
        if self.tablebase {
            if let Some(score) = crate::tablebase::probe(p, ply) {
                self.tablebase_hits += 1;
                self.lists[ply] = moves;
                return Ok(score);
            }
        }
        if depth <= 0 || ply >= MAX_PLY - 2 {
            self.lists[ply] = moves;
            return Ok(evaluate(p, self.candidate));
        }
        let key = p.tt_key();
        let slot = key as usize & (self.table.len() - 1);
        let entry = self.table[slot];
        let original_alpha = alpha;
        let mut tt = u16::MAX;
        if entry.key == key && entry.bound != 0 {
            tt = entry.mv;
            if entry.depth >= depth && ply > 0 {
                self.hits += 1;
                let score = restored(entry.score, ply);
                if entry.bound == 1
                    || (entry.bound == 2 && score >= beta)
                    || (entry.bound == 3 && score <= alpha)
                {
                    self.lists[ply] = moves;
                    return Ok(score);
                }
            }
        }
        let threatened = immediate_den_threat(p, p.side.other());
        moves.sort_unstable_by_key(|m| (-self.order(p, *m, tt, ply), m.key()));
        let mut best = -INF;
        let mut best_move = moves[0];
        for (index, &m) in moves.iter().enumerate() {
            let undo = p.make(m);
            let mut reduction = 0;
            if self.lmr
                && depth >= 3
                && index >= 4
                && m.capture == 0
                && !m.jump
                && !threatened
                && !immediate_den_threat(p, p.side.other())
            {
                reduction = 1;
            }
            let result = if index == 0 || !self.candidate {
                self.node(p, depth - 1, -beta, -alpha, ply + 1).map(|s| -s)
            } else {
                self.node(p, depth - 1 - reduction, -alpha - 1, -alpha, ply + 1)
                    .and_then(|s| {
                        let mut score = -s;
                        if score > alpha && reduction > 0 {
                            score = -self.node(p, depth - 1, -alpha - 1, -alpha, ply + 1)?;
                        }
                        if score > alpha && score < beta {
                            score = -self.node(p, depth - 1, -beta, -alpha, ply + 1)?;
                        }
                        Ok(score)
                    })
            };
            p.unmake(m, undo);
            let score = result?;
            if score > best {
                best = score;
                best_move = m;
            }
            alpha = alpha.max(score);
            if alpha >= beta {
                if m.capture == 0 && self.candidate {
                    if self.killers[ply][0] != m.key() {
                        self.killers[ply][1] = self.killers[ply][0];
                        self.killers[ply][0] = m.key();
                    }
                    let h = &mut self.history[p.side.index()][m.from as usize][m.to as usize];
                    *h = (*h + i32::from(depth) * i32::from(depth)).min(40_000);
                }
                break;
            }
        }
        self.table[slot] = Entry {
            key,
            score: stored(best, ply),
            depth,
            bound: if best <= original_alpha {
                3
            } else if best >= beta {
                2
            } else {
                1
            },
            mv: best_move.key(),
        };
        self.lists[ply] = moves;
        Ok(best)
    }
    fn pv(&self, root: &Position, depth: u8) -> Vec<Move> {
        let mut p = root.clone();
        let mut pv = Vec::new();
        for _ in 0..depth {
            let moves = p.moves();
            if p.outcome(&moves).ended() {
                break;
            }
            let key = p.tt_key();
            let entry = self.table[key as usize & (self.table.len() - 1)];
            if entry.key != key || entry.bound == 0 {
                break;
            }
            let Some(m) = moves.into_iter().find(|m| m.key() == entry.mv) else {
                break;
            };
            pv.push(m);
            p.make(m);
        }
        pv
    }
}
pub fn search(
    root: &Position,
    options: &SearchOptions,
    clock: &dyn Fn() -> f64,
    cancel: &dyn Fn() -> bool,
    progress: &mut dyn FnMut(&SearchResult),
) -> SearchResult {
    let start = clock();
    let moves = root.moves();
    let outcome = root.outcome(&moves);
    let mut result = SearchResult {
        best_move: if outcome.ended() {
            None
        } else {
            moves.first().copied()
        },
        score: 0,
        depth: 0,
        nodes: 0,
        elapsed_ms: 0.0,
        pv: vec![],
        tt_hits: 0,
        tablebase_hits: 0,
        aborted: false,
        profile: options.profile.clone(),
    };
    if outcome.ended() {
        return result;
    }
    let use_tablebase = options.profile != "baseline" && options.profile != "no_tablebase";
    if use_tablebase && !cancel() {
        if let Some((mv, score)) = crate::tablebase::best(root) {
            result.best_move = Some(mv);
            result.score = score;
            result.pv = vec![mv];
            result.tablebase_hits = 1;
            result.elapsed_ms = clock() - start;
            progress(&result);
            return result;
        }
    }
    let time = if options.time_ms.is_finite() {
        options.time_ms.clamp(1.0, 5000.0)
    } else {
        1.0
    };
    let candidate = options.profile != "baseline";
    let mut engine = Searcher {
        table: vec![Entry::default(); 1 << 18],
        clock,
        cancel,
        start,
        deadline: start + time,
        limit: options.node_limit,
        nodes: 0,
        hits: 0,
        tablebase_hits: 0,
        tablebase: use_tablebase,
        candidate,
        lmr: candidate && options.profile != "no_lmr",
        quiescence: candidate && options.profile != "no_quiescence",
        killers: [[u16::MAX; 2]; MAX_PLY],
        history: Box::new([[[0; 63]; 63]; 2]),
        lists: (0..MAX_PLY).map(|_| Vec::with_capacity(32)).collect(),
    };
    let default_depth = match options.difficulty.as_str() {
        "easy" => 3,
        "medium" => 8,
        _ => 64,
    };
    let max_depth = options.max_depth.unwrap_or(default_depth).clamp(1, 64);
    progress(&result);
    for depth in 1..=max_depth {
        if cancel() || clock() >= engine.deadline {
            result.aborted = true;
            break;
        }
        let mut p = root.clone();
        let window = if candidate && depth >= 4 { 160 } else { INF };
        let alpha = (result.score - window).max(-INF);
        let beta = (result.score + window).min(INF);
        let attempt = engine
            .node(&mut p, i16::from(depth), alpha, beta, 0)
            .and_then(|score| {
                if score <= alpha || score >= beta {
                    engine.node(&mut p, i16::from(depth), -INF, INF, 0)
                } else {
                    Ok(score)
                }
            });
        match attempt {
            Ok(score) => {
                let pv = engine.pv(root, depth);
                if let Some(best) = pv.first() {
                    result.best_move = Some(*best);
                }
                result.score = score;
                result.depth = depth;
                result.pv = pv;
                result.nodes = engine.nodes;
                result.tt_hits = engine.hits;
                result.tablebase_hits = engine.tablebase_hits;
                result.elapsed_ms = clock() - engine.start;
                progress(&result);
                if score.abs() >= MATE - 100 || moves.len() == 1 {
                    break;
                }
            }
            Err(()) => {
                result.aborted = true;
                break;
            }
        }
    }
    result.nodes = engine.nodes;
    result.tt_hits = engine.hits;
    result.tablebase_hits = engine.tablebase_hits;
    result.elapsed_ms = clock() - start;
    result
}
