use crate::board::{water, Move, Position, Side};
use std::cmp::Reverse;
use std::collections::BinaryHeap;
pub const COUNT: usize = 64 * 63 * 63 * 2;
const HEADER: usize = 28;
pub fn checksum(bytes: &[u8]) -> u64 {
    bytes.iter().fold(0xcbf29ce484222325, |h, b| {
        (h ^ u64::from(*b)).wrapping_mul(0x100000001b3)
    })
}
fn index(p: &Position) -> Option<usize> {
    let mut blue = None;
    let mut red = None;
    for (s, &piece) in p.board.iter().enumerate() {
        if piece > 0 {
            if blue.is_some() {
                return None;
            }
            blue = Some((s, piece as usize));
        }
        if piece < 0 {
            if red.is_some() {
                return None;
            }
            red = Some((s, (-piece) as usize));
        }
    }
    let (b, br) = blue?;
    let (r, rr) = red?;
    Some(((((br - 1) * 8 + rr - 1) * 63 + b) * 63 + r) * 2 + p.side.index())
}
fn decode(id: usize) -> Option<Position> {
    let side = if id.is_multiple_of(2) {
        Side::Blue
    } else {
        Side::Red
    };
    let red = (id / 2) % 63;
    let blue = (id / 2 / 63) % 63;
    let pair = id / 2 / 63 / 63;
    let br = (pair / 8 + 1) as i8;
    let rr = (pair % 8 + 1) as i8;
    if blue == red
        || blue == 59
        || red == 3
        || water(blue as u8) && br != 1
        || water(red as u8) && rr != 1
    {
        return None;
    }
    let mut p = Position {
        board: [0; 63],
        side,
        quiet: 0,
        hash: 0,
    };
    p.board[blue] = br;
    p.board[red] = -rr;
    p.rehash();
    Some(p)
}
pub fn generate() -> Vec<u8> {
    let mut status = vec![0u8; COUNT];
    let mut distance = vec![0u16; COUNT];
    let mut degree = vec![0u8; COUNT];
    let mut longest = vec![0u16; COUNT];
    let mut parents: Vec<Vec<u32>> = (0..COUNT).map(|_| Vec::new()).collect();
    let mut queue = BinaryHeap::new();
    for id in 0..COUNT {
        let Some(mut p) = decode(id) else {
            continue;
        };
        let moves = p.moves();
        let outcome = p.outcome(&moves);
        if outcome.ended() {
            status[id] = if outcome.winner == Some(p.side) {
                2
            } else if outcome.winner.is_some() {
                3
            } else {
                4
            };
            queue.push(Reverse((0u16, id as u32)));
            continue;
        }
        status[id] = 1;
        degree[id] = moves.len() as u8;
        for m in moves {
            let undo = p.make(m);
            if let Some(child) = index(&p) {
                parents[child].push(id as u32);
            } else {
                // With one animal per side, every capture immediately wins by elimination.
                status[id] = 2;
                distance[id] = 1;
            }
            p.unmake(m, undo);
        }
        if status[id] == 2 {
            queue.push(Reverse((1, id as u32)));
        }
    }
    while let Some(Reverse((dtm, child))) = queue.pop() {
        let child = child as usize;
        for &parent in &parents[child] {
            let parent = parent as usize;
            if status[parent] != 1 {
                continue;
            }
            if status[child] == 3 {
                status[parent] = 2;
                distance[parent] = dtm.saturating_add(1);
                queue.push(Reverse((distance[parent], parent as u32)));
            } else if status[child] == 2 {
                degree[parent] -= 1;
                longest[parent] = longest[parent].max(dtm);
                if degree[parent] == 0 {
                    status[parent] = 3;
                    distance[parent] = longest[parent].saturating_add(1);
                    queue.push(Reverse((distance[parent], parent as u32)));
                }
            }
        }
    }
    for s in &mut status {
        if *s == 1 {
            *s = 4;
        }
    }
    let mut payload = status;
    for d in distance {
        payload.extend_from_slice(&d.to_le_bytes());
    }
    let mut output = b"JGTB0001".to_vec();
    output.extend_from_slice(&(COUNT as u32).to_le_bytes());
    output.extend_from_slice(&checksum(crate::RULES_ID.as_bytes()).to_le_bytes());
    output.extend_from_slice(&checksum(&payload).to_le_bytes());
    output.extend(payload);
    output
}
#[cfg(feature = "tablebase")]
const DATA: &[u8] = include_bytes!("../data/two_piece.bin");
#[cfg(not(feature = "tablebase"))]
const DATA: &[u8] = &[];
pub fn validate() -> bool {
    DATA.len() == HEADER + COUNT * 3
        && &DATA[..8] == b"JGTB0001"
        && u32::from_le_bytes(DATA[8..12].try_into().unwrap()) as usize == COUNT
        && u64::from_le_bytes(DATA[12..20].try_into().unwrap())
            == checksum(crate::RULES_ID.as_bytes())
        && u64::from_le_bytes(DATA[20..28].try_into().unwrap()) == checksum(&DATA[HEADER..])
}
pub fn probe(p: &Position, ply: usize) -> Option<i32> {
    if DATA.is_empty() {
        return None;
    }
    let id = index(p)?;
    let status = DATA[HEADER + id];
    if status == 0 {
        return None;
    }
    let offset = HEADER + COUNT + id * 2;
    let dtm = u16::from_le_bytes([DATA[offset], DATA[offset + 1]]);
    // In a two-animal game, a capture ends play. Every nonterminal move increments
    // the quiet clock, so exact distance-to-mate also resolves the finite draw limit.
    if status == 4 || dtm > 100 - p.quiet.min(100) {
        return Some(0);
    }
    let score = 100_000 - ply as i32 - i32::from(dtm);
    Some(if status == 2 { score } else { -score })
}
pub fn best(p: &Position) -> Option<(Move, i32)> {
    let score = probe(p, 0)?;
    let mut best = None;
    let mut value = i32::MIN;
    for m in p.moves() {
        let mut child = p.clone();
        child.make(m);
        let outcome = child.outcome(&child.moves());
        let next = if outcome.ended() {
            outcome
                .winner
                .map_or(0, |s| if s == p.side { 99_999 } else { -99_999 })
        } else {
            -probe(&child, 1)?
        };
        if next > value {
            value = next;
            best = Some(m);
        }
    }
    best.map(|m| (m, score))
}
#[cfg(all(test, feature = "tablebase"))]
mod tests {
    use super::*;
    fn solve(p: &mut Position) -> i32 {
        let moves = p.moves();
        let outcome = p.outcome(&moves);
        if outcome.ended() {
            return outcome
                .winner
                .map_or(0, |s| if s == p.side { 1 } else { -1 });
        }
        let mut best = -1;
        for m in moves {
            let u = p.make(m);
            let result = -solve(p);
            p.unmake(m, u);
            best = best.max(result);
            if best == 1 {
                break;
            }
        }
        best
    }
    #[test]
    fn checked_payload_and_finite_clock() {
        assert!(validate());
        let mut seed = 7u64;
        let mut checked = 0;
        for _ in 0..2000 {
            seed = crate::board::mix(seed);
            let Some(mut p) = decode(seed as usize % COUNT) else {
                continue;
            };
            if p.outcome(&p.moves()).ended() {
                continue;
            }
            p.quiet = 95 + (seed % 5) as u16;
            assert_eq!(
                probe(&p, 0).unwrap().signum(),
                solve(&mut p),
                "position {:?}",
                p.data()
            );
            checked += 1;
        }
        assert!(checked > 500);
    }
}
