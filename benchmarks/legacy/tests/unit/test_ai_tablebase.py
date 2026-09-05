from __future__ import annotations

from pathlib import Path

import pytest

from jungle.ai.tablebase import (
    ASSET_NAME,
    ENTRY_COUNT,
    RULES_HASH_HEX,
    TablebaseError,
    TwoPieceTablebase,
    WDL,
    default_tablebase_path,
    verify_tablebase,
)
from jungle.domain import GameState, Piece, PieceType, Position, Side


def make_state(
    blue_kind: PieceType,
    blue_position: int,
    red_kind: PieceType,
    red_position: int,
    side_to_move: Side,
) -> GameState:
    board: list[Piece | None] = [None] * 63
    board[blue_position] = Piece(Side.BLUE, blue_kind)
    board[red_position] = Piece(Side.RED, red_kind)
    return GameState(board=board, side_to_move=side_to_move)


@pytest.fixture(scope="module")
def tablebase() -> TwoPieceTablebase:
    return TwoPieceTablebase.load()


def test_bundled_asset_has_stable_format_and_valid_checksum(tablebase: TwoPieceTablebase) -> None:
    path = default_tablebase_path()

    assert path.name == ASSET_NAME
    assert path.stat().st_size == 84 + ENTRY_COUNT * 2
    assert len(RULES_HASH_HEX) == 64
    assert tablebase.max_distance == 34
    assert verify_tablebase(path) is None


def test_probe_codes_matches_game_state_probe(tablebase: TwoPieceTablebase) -> None:
    state = make_state(PieceType.RAT, 0, PieceType.RAT, 5, Side.BLUE)

    assert tablebase.probe(state) == tablebase.probe_codes(
        PieceType.RAT, 0, PieceType.RAT, 5, Side.BLUE
    )
    assert tablebase.probe_codes(0, 0, PieceType.RAT, 5, Side.BLUE) is None
    assert tablebase.probe_codes(PieceType.CAT, Position(3, 1).index, PieceType.RAT, 5, Side.BLUE) is None


def test_probe_rejects_states_outside_exact_domain(tablebase: TwoPieceTablebase) -> None:
    board: list[Piece | None] = [None] * 63
    board[0] = Piece(Side.BLUE, PieceType.RAT)
    board[1] = Piece(Side.BLUE, PieceType.CAT)
    board[2] = Piece(Side.RED, PieceType.RAT)

    assert tablebase.probe(GameState(board, Side.BLUE)) is None
    assert tablebase.probe(make_state(PieceType.CAT, Position(3, 1).index, PieceType.RAT, 2, Side.BLUE)) is None
    assert tablebase.probe_codes(PieceType.RAT, -1, PieceType.RAT, 2, Side.BLUE) is None


def test_den_terminal_is_exact_for_either_side_to_move(tablebase: TwoPieceTablebase) -> None:
    red_den = Position(0, 3).index
    red_piece = Position(8, 6).index
    winner_to_move = make_state(PieceType.CAT, red_den, PieceType.RAT, red_piece, Side.BLUE)
    loser_to_move = make_state(PieceType.CAT, red_den, PieceType.RAT, red_piece, Side.RED)

    assert tablebase.probe(winner_to_move).wdl is WDL.WIN
    assert tablebase.probe(winner_to_move).distance == 0
    assert tablebase.probe(loser_to_move).wdl is WDL.LOSS
    assert tablebase.probe(loser_to_move).distance == 0
    assert tablebase.rank_moves(loser_to_move) == ()


def test_immediate_capture_and_den_entry_have_distance_one(tablebase: TwoPieceTablebase) -> None:
    capture = make_state(PieceType.RAT, 14, PieceType.ELEPHANT, 15, Side.BLUE)
    den_entry = make_state(PieceType.CAT, Position(1, 3).index, PieceType.RAT, 62, Side.BLUE)

    capture_entry = tablebase.probe(capture)
    assert capture_entry is not None
    assert capture_entry.wdl is WDL.WIN
    assert capture_entry.distance == 1
    assert tablebase.choose_move(capture).destination == 15

    den_entry_result = tablebase.probe(den_entry)
    assert den_entry_result is not None
    assert den_entry_result.wdl is WDL.WIN
    assert den_entry_result.distance == 1
    assert tablebase.choose_move(den_entry).destination == Position(0, 3).index


def test_tablebase_obeys_traps_and_project_tiger_jump_restriction(
    tablebase: TwoPieceTablebase,
) -> None:
    trapped_rat = make_state(
        PieceType.ELEPHANT,
        Position(8, 1).index,
        PieceType.RAT,
        Position(8, 2).index,
        Side.BLUE,
    )
    assert tablebase.probe(trapped_rat).distance == 1
    assert tablebase.choose_move(trapped_rat).destination == Position(8, 2).index

    # A cat can capture an elephant whose effective rank is zero in the blue
    # trap, so the tablebase reports an immediate conversion.
    trapped_elephant = make_state(
        PieceType.CAT,
        Position(8, 1).index,
        PieceType.ELEPHANT,
        Position(8, 2).index,
        Side.BLUE,
    )
    assert tablebase.probe(trapped_elephant).distance == 1
    assert tablebase.choose_move(trapped_elephant).destination == Position(8, 2).index

    # This repository forbids the tiger's three-water-square vertical jump.
    tiger = make_state(
        PieceType.TIGER,
        Position(2, 1).index,
        PieceType.CAT,
        Position(8, 6).index,
        Side.BLUE,
    )
    destinations = {item.move.destination for item in tablebase.rank_moves(tiger)}
    assert Position(6, 1).index not in destinations


def test_move_ranking_selects_fastest_forced_win(tablebase: TwoPieceTablebase) -> None:
    # Both rat moves win, but 0->1 converts four plies sooner than 0->7.
    state = make_state(PieceType.RAT, 0, PieceType.RAT, 5, Side.BLUE)

    ranked = tablebase.rank_moves(state)

    assert [(item.move.destination, item.wdl, item.distance) for item in ranked] == [
        (1, WDL.WIN, 5),
        (7, WDL.WIN, 9),
    ]
    assert tablebase.choose_move(state).destination == 1


def test_move_ranking_prefers_draw_to_loss(tablebase: TwoPieceTablebase) -> None:
    state = make_state(PieceType.RAT, 0, PieceType.RAT, 2, Side.BLUE)

    entry = tablebase.probe(state)
    ranked = tablebase.rank_moves(state)

    assert entry is not None and entry.wdl is WDL.DRAW and entry.distance is None
    assert [(item.move.destination, item.wdl, item.distance) for item in ranked] == [
        (7, WDL.DRAW, None),
        (1, WDL.LOSS, 2),
    ]
    assert tablebase.choose_move(state).destination == 7


def test_move_ranking_maximizes_resistance_when_lost(tablebase: TwoPieceTablebase) -> None:
    state = make_state(PieceType.RAT, 0, PieceType.RAT, 2, Side.RED)

    entry = tablebase.probe(state)
    ranked = tablebase.rank_moves(state)

    assert entry is not None and entry.wdl is WDL.LOSS and entry.distance == 6
    assert [(item.move.destination, item.wdl, item.distance) for item in ranked] == [
        (9, WDL.LOSS, 6),
        (1, WDL.LOSS, 2),
    ]
    assert tablebase.choose_move(state).destination == 9


def test_missing_or_corrupt_asset_falls_back_cleanly(tmp_path: Path) -> None:
    missing = tmp_path / "missing.jgtb"
    assert TwoPieceTablebase.try_load(missing) is None

    data = bytearray(default_tablebase_path().read_bytes())
    data[-1] ^= 0xFF
    corrupt = tmp_path / "corrupt.jgtb"
    corrupt.write_bytes(data)

    assert TwoPieceTablebase.try_load(corrupt) is None
    with pytest.raises(TablebaseError, match="checksum"):
        TwoPieceTablebase.load(corrupt)
