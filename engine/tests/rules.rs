use jungle_engine::board::{mix, perft, trap, water};
use jungle_engine::game::SaveGame;
use jungle_engine::search::evaluate;
use jungle_engine::{search, Command, Game, Position, PositionData, SearchOptions, Settings, Side};

fn position(pieces: &[(u8, i8)], side: Side, quiet: u16) -> Position {
    let mut board = vec![0; 63];
    for &(s, p) in pieces {
        board[s as usize] = p;
    }
    Position::from_data(PositionData { board, side, quiet }).unwrap()
}
fn has(p: &Position, from: u8, to: u8) -> bool {
    p.moves().iter().any(|m| m.from == from && m.to == to)
}
#[test]
fn setup_and_terrain() {
    let p = Position::initial();
    assert_eq!(p.board.iter().filter(|&&x| x != 0).count(), 16);
    assert_eq!(p.side, Side::Blue);
    assert_eq!((0..63).filter(|&s| water(s)).count(), 12);
    assert_eq!((0..63).filter(|&s| trap(s).is_some()).count(), 6);
    assert_eq!(p.board[42], 8);
    assert_eq!(p.board[14], -1);
    assert_eq!(p.board[56], 6);
    assert_eq!(p.board[0], -7);
}
#[test]
fn lion_jumps_both_tiger_only_east_west() {
    for rank in [6, 7] {
        let p = position(&[(15, rank), (6, -8)], Side::Blue, 0);
        assert_eq!(has(&p, 15, 43), rank == 7);
        let p = position(&[(21, rank), (6, -8)], Side::Blue, 0);
        assert!(has(&p, 21, 24));
    }
}
#[test]
fn all_rat_blockers_and_reverse_jumps() {
    for &(from, to, path) in &[
        (15, 43, &[22, 29, 36][..]),
        (43, 15, &[36, 29, 22][..]),
        (21, 24, &[22, 23][..]),
        (24, 21, &[23, 22][..]),
        (24, 27, &[25, 26][..]),
        (27, 24, &[26, 25][..]),
    ] {
        let clear = position(&[(from, 7), (6, -8)], Side::Blue, 0);
        assert!(has(&clear, from, to));
        for &square in path {
            for rat in [-1, 1] {
                let p = position(&[(from, 7), (6, -8), (square, rat)], Side::Blue, 0);
                assert!(
                    !has(&p, from, to),
                    "blocked {from}->{to}, rat {rat} at {square}"
                );
            }
        }
    }
}
#[test]
fn every_river_lane_and_color_obeys_the_selected_jump_profile() {
    let mut lanes = Vec::new();
    for row in 3..=5 {
        for column in [0, 3] {
            lanes.push((
                row * 7 + column,
                row * 7 + column + 3,
                vec![row * 7 + column + 1, row * 7 + column + 2],
                false,
            ));
        }
    }
    for column in [1, 2, 4, 5] {
        lanes.push((
            14 + column,
            42 + column,
            vec![21 + column, 28 + column, 35 + column],
            true,
        ));
    }
    for (a, b, path, vertical) in lanes {
        for (from, to) in [(a, b), (b, a)] {
            for side in [Side::Blue, Side::Red] {
                for rank in [6, 7] {
                    let animal = rank * side.sign();
                    let guard = -8 * side.sign();
                    let clear = position(&[(from, animal), (0, guard)], side, 0);
                    assert_eq!(has(&clear, from, to), !vertical || rank == 7);
                    for &square in &path {
                        for rat in [-1, 1] {
                            let blocked =
                                position(&[(from, animal), (0, guard), (square, rat)], side, 0);
                            assert!(
                                !has(&blocked, from, to),
                                "blocked {from}->{to}; rat {rat} at {square}"
                            );
                        }
                    }
                }
            }
        }
    }
}
#[test]
fn jump_capture_and_friendly_destination() {
    assert!(has(&position(&[(21, 7), (24, -6)], Side::Blue, 0), 21, 24));
    assert!(!has(&position(&[(21, 7), (24, -8)], Side::Blue, 0), 21, 24));
    assert!(!has(
        &position(&[(21, 7), (24, 6), (6, -8)], Side::Blue, 0),
        21,
        24
    ));
}
#[test]
fn water_boundaries_and_exceptions() {
    assert!(has(&position(&[(21, 1), (6, -8)], Side::Blue, 0), 21, 22));
    assert!(has(&position(&[(22, 1), (23, -1)], Side::Blue, 0), 22, 23));
    assert!(!has(
        &position(&[(21, 1), (22, -1), (6, -8)], Side::Blue, 0),
        21,
        22
    ));
    assert!(!has(&position(&[(22, 1), (21, -8)], Side::Blue, 0), 22, 21));
    assert!(has(&position(&[(14, 1), (15, -8)], Side::Blue, 0), 14, 15));
    assert!(!has(&position(&[(14, 8), (15, -1)], Side::Blue, 0), 14, 15));
    assert!(has(&position(&[(57, 8), (58, -1)], Side::Blue, 0), 57, 58));
}
#[test]
fn traps_are_owned_and_affect_both_ranks() {
    let p = position(&[(1, 8), (2, -2)], Side::Blue, 0);
    assert_eq!(p.effective_rank(2), 2);
    assert!(has(&p, 1, 2));
    let p = position(&[(57, 2), (58, -8)], Side::Blue, 0);
    assert_eq!(p.effective_rank(58), 0);
    assert!(has(&p, 57, 58));
    let p = position(&[(2, 8), (1, -2)], Side::Blue, 0);
    assert_eq!(p.effective_rank(2), 0);
    assert!(!has(&p, 2, 1));
}
#[test]
fn own_den_and_winning_den() {
    let p = position(&[(52, 7), (6, -8)], Side::Blue, 0);
    assert!(!has(&p, 52, 59));
    let mut p = position(&[(10, 7), (6, -8)], Side::Blue, 99);
    p.play(10, 3).unwrap();
    let result = p.outcome(&p.moves());
    assert_eq!(result.kind, "den_entry");
    assert_eq!(result.winner, Some(Side::Blue));
}
#[test]
fn elimination_and_no_move_precede_draw() {
    let mut p = position(&[(14, 7), (15, -2)], Side::Blue, 99);
    p.play(14, 15).unwrap();
    assert_eq!(p.outcome(&p.moves()).kind, "capture_all");
    assert_eq!(p.quiet, 0);
    let p = position(&[(0, 2), (1, -8), (7, -7)], Side::Blue, 100);
    assert!(p.moves().is_empty());
    assert_eq!(p.outcome(&p.moves()).kind, "no_legal_moves");
}
#[test]
fn draw_counter_and_make_unmake() {
    let mut p = position(&[(56, 6), (6, -7)], Side::Blue, 99);
    let original = p.clone();
    let m = p.moves()[0];
    let u = p.make(m);
    assert_eq!(p.quiet, 100);
    assert_eq!(p.outcome(&p.moves()).kind, "no_capture_draw");
    assert!(p.play(6, 5).is_err());
    p.unmake(m, u);
    assert_eq!(p, original);
}
#[test]
fn ten_thousand_position_invariants() {
    let mut p = Position::initial();
    let mut seed = 42u64;
    for _ in 0..10_000 {
        let moves = p.moves();
        if p.outcome(&moves).ended() {
            p = Position::initial();
            continue;
        }
        let original = p.clone();
        for &m in &moves {
            let u = p.make(m);
            let hash = p.hash;
            p.rehash();
            assert_eq!(hash, p.hash);
            assert!(p
                .board
                .iter()
                .enumerate()
                .all(|(s, &piece)| !water(s as u8) || piece == 0 || piece.abs() == 1));
            p.unmake(m, u);
            assert_eq!(p, original);
        }
        let mut rotated = p.clone();
        rotated.board.reverse();
        for x in &mut rotated.board {
            *x = -*x;
        }
        rotated.side = p.side.other();
        rotated.rehash();
        assert_eq!(evaluate(&p, true), evaluate(&rotated, true));
        let mut mirrored: Vec<_> = rotated
            .moves()
            .into_iter()
            .map(|m| (62 - m.from, 62 - m.to))
            .collect();
        mirrored.sort();
        let mut normal: Vec<_> = moves.iter().map(|m| (m.from, m.to)).collect();
        normal.sort();
        assert_eq!(normal, mirrored);
        seed = mix(seed);
        p.make(moves[seed as usize % moves.len()]);
    }
}
#[test]
fn session_undo_redo_and_stale_revision() {
    let mut game = Game::default();
    let original = game.position().clone();
    let revision = game.revision();
    let m = game.position().moves()[0];
    game.apply(m.from, m.to, revision).unwrap();
    assert!(game.apply(m.from, m.to, revision).is_err());
    let m = game.position().moves()[0];
    game.apply(m.from, m.to, game.revision()).unwrap();
    let after = game.position().clone();
    game.undo().unwrap();
    assert_eq!(game.position(), &original);
    game.redo().unwrap();
    assert_eq!(game.position(), &after);
    let save = game.save().unwrap();
    let mut restored = Game::default();
    restored.import(&save).unwrap();
    assert_eq!(restored.position(), game.position());
}
#[test]
fn ai_first_has_no_spurious_undo() {
    let mut g = Game::new(Settings {
        human: Side::Red,
        ..Settings::default()
    });
    let m = g.position().moves()[0];
    g.apply(m.from, m.to, g.revision()).unwrap();
    assert!(!g.snapshot().can_undo);
    let m = g.position().moves()[0];
    g.apply(m.from, m.to, g.revision()).unwrap();
    g.undo().unwrap();
    assert_eq!(g.cursor, 1);
}
#[test]
fn import_is_atomic_and_rejects_tampering() {
    let mut g = Game::default();
    let before = g.save().unwrap();
    assert!(g.import("bad json").is_err());
    assert_eq!(g.save().unwrap(), before);
    let mut save: SaveGame = serde_json::from_str(&before).unwrap();
    save.initial.board.push(0);
    assert!(Game::from_save(save).is_err());
    assert!(g
        .dispatch(Command::Move {
            from: 255,
            to: 1,
            revision: g.revision()
        })
        .is_err());
}
#[test]
fn legacy_import_replays_history() {
    let mut p = Position::initial();
    let initial = p.clone();
    let m = p.moves()[0];
    let piece = p.board[m.from as usize];
    p.make(m);
    let piece_json = |p: i8| {
        if p == 0 {
            serde_json::Value::Null
        } else {
            serde_json::json!({"side":if p>0{"blue"}else{"red"},"kind":jungle_engine::board::NAMES[p.unsigned_abs() as usize].to_uppercase()})
        }
    };
    let legacy = serde_json::json!({"board":p.board.iter().map(|&p|piece_json(p)).collect::<Vec<_>>(),"side_to_move":p.side,
        "move_history":[{"origin":m.from,"destination":m.to,"piece":piece_json(piece),"captured":null,"is_jump":false}]});
    let mut g = Game::default();
    g.import(&legacy.to_string()).unwrap();
    assert_eq!(g.position(), &p);
    assert_eq!(g.position().quiet, 1);
    g.undo().unwrap();
    assert_eq!(g.position(), &initial);
}
#[test]
fn search_finds_den_and_keeps_root_unchanged() {
    let p = position(&[(10, 7), (6, -8)], Side::Blue, 0);
    let original = p.clone();
    let result = search(
        &p,
        &SearchOptions {
            node_limit: Some(2000),
            ..SearchOptions::default()
        },
        &|| 0.0,
        &|| false,
        &mut |_| {},
    );
    assert_eq!(result.best_move.unwrap().to, 3);
    assert_eq!(p, original);
}
#[test]
fn bounded_search_is_repeatable_and_cancel_has_fallback() {
    let p = Position::initial();
    let options = SearchOptions {
        node_limit: Some(1500),
        ..SearchOptions::default()
    };
    let a = search(&p, &options, &|| 0.0, &|| false, &mut |_| {});
    let b = search(&p, &options, &|| 0.0, &|| false, &mut |_| {});
    assert_eq!(a.best_move, b.best_move);
    assert_eq!(a.nodes, b.nodes);
    assert!(a.nodes <= 1500);
    let stopped = search(&p, &options, &|| 0.0, &|| true, &mut |_| {});
    assert!(p.moves().contains(&stopped.best_move.unwrap()));
}
#[test]
fn perft_fixture() {
    // Independently cross-checked with the pre-refactor move generator and reviewed setup.
    for (depth, expected) in [(1, 24), (2, 576), (3, 12240)] {
        assert_eq!(perft(&mut Position::initial(), depth), expected);
    }
}
