from __future__ import annotations

from jungle.domain import (
    BLUE_DEN,
    BLUE_TRAPS,
    RED_DEN,
    RED_TRAPS,
    WATER,
    Move,
    Piece,
    PieceType,
    Position,
    ResultType,
    Side,
    initial_state,
)
from jungle.engine import Game
from jungle.rules import can_capture, effective_rank, evaluate_result, find_legal_move, generate_piece_moves, legal_moves


def make_state(pieces: dict[int, Piece], side_to_move: Side = Side.BLUE):
    board = [None] * 63
    for index, piece in pieces.items():
        board[index] = piece
    from jungle.domain import GameState

    return GameState(board=board, side_to_move=side_to_move)


def test_initial_state_has_16_pieces() -> None:
    state = initial_state()
    assert sum(piece is not None for piece in state.board) == 16
    assert state.side_to_move is Side.BLUE


def test_initial_state_matches_standard_starting_positions() -> None:
    state = initial_state()
    expected = {
        Position(0, 0).index: Piece(Side.RED, PieceType.LION),
        Position(0, 6).index: Piece(Side.RED, PieceType.TIGER),
        Position(1, 1).index: Piece(Side.RED, PieceType.DOG),
        Position(1, 5).index: Piece(Side.RED, PieceType.CAT),
        Position(2, 0).index: Piece(Side.RED, PieceType.RAT),
        Position(2, 2).index: Piece(Side.RED, PieceType.LEOPARD),
        Position(2, 4).index: Piece(Side.RED, PieceType.WOLF),
        Position(2, 6).index: Piece(Side.RED, PieceType.ELEPHANT),
        Position(6, 0).index: Piece(Side.BLUE, PieceType.ELEPHANT),
        Position(6, 2).index: Piece(Side.BLUE, PieceType.WOLF),
        Position(6, 4).index: Piece(Side.BLUE, PieceType.LEOPARD),
        Position(6, 6).index: Piece(Side.BLUE, PieceType.RAT),
        Position(7, 1).index: Piece(Side.BLUE, PieceType.CAT),
        Position(7, 5).index: Piece(Side.BLUE, PieceType.DOG),
        Position(8, 0).index: Piece(Side.BLUE, PieceType.TIGER),
        Position(8, 6).index: Piece(Side.BLUE, PieceType.LION),
    }
    actual = {index: piece for index, piece in enumerate(state.board) if piece is not None}
    assert actual == expected


def test_initial_state_pieces_do_not_start_in_dens_traps_or_water() -> None:
    blocked = WATER | BLUE_TRAPS | RED_TRAPS | {BLUE_DEN, RED_DEN}
    state = initial_state()
    assert all(piece is None for index, piece in enumerate(state.board) if index in blocked)


def test_rat_can_enter_water_but_cat_cannot() -> None:
    rat = Position(2, 1).index
    cat = Position(2, 4).index
    state = make_state(
        {
            rat: Piece(Side.BLUE, PieceType.RAT),
            cat: Piece(Side.BLUE, PieceType.CAT),
        }
    )
    rat_moves = {move.destination for move in generate_piece_moves(state, rat)}
    cat_moves = {move.destination for move in generate_piece_moves(state, cat)}
    assert Position(3, 1).index in WATER
    assert Position(3, 1).index in rat_moves
    assert Position(3, 4).index not in cat_moves


def test_rat_in_water_only_captures_rat_in_water() -> None:
    attacker = Position(3, 1).index
    defender = Position(3, 2).index
    land_defender = Position(2, 1).index
    state = make_state(
        {
            attacker: Piece(Side.BLUE, PieceType.RAT),
            defender: Piece(Side.RED, PieceType.RAT),
            land_defender: Piece(Side.RED, PieceType.CAT),
        }
    )
    assert can_capture(state, attacker, defender)
    assert not can_capture(state, attacker, land_defender)


def test_rat_can_capture_elephant_only_from_land() -> None:
    rat = Position(2, 0).index
    elephant = Position(2, 1).index
    state = make_state(
        {
            rat: Piece(Side.BLUE, PieceType.RAT),
            elephant: Piece(Side.RED, PieceType.ELEPHANT),
        }
    )
    assert can_capture(state, rat, elephant)

    water_rat = Position(3, 1).index
    adjacent_elephant = Position(2, 1).index
    water_state = make_state(
        {
            water_rat: Piece(Side.BLUE, PieceType.RAT),
            adjacent_elephant: Piece(Side.RED, PieceType.ELEPHANT),
        }
    )
    assert not can_capture(water_state, water_rat, adjacent_elephant)


def test_elephant_cannot_capture_rat() -> None:
    elephant = Position(2, 0).index
    rat = Position(2, 1).index
    state = make_state(
        {
            elephant: Piece(Side.BLUE, PieceType.ELEPHANT),
            rat: Piece(Side.RED, PieceType.RAT),
        }
    )
    assert not can_capture(state, elephant, rat)


def test_legal_moves_include_rat_capturing_elephant() -> None:
    rat = Position(2, 0).index
    elephant = Position(2, 1).index
    state = make_state(
        {
            rat: Piece(Side.BLUE, PieceType.RAT),
            elephant: Piece(Side.RED, PieceType.ELEPHANT),
        }
    )

    moves = legal_moves(state)

    assert any(move.origin == rat and move.destination == elephant and move.captured is not None for move in moves)


def test_legal_moves_exclude_elephant_capturing_rat() -> None:
    elephant = Position(2, 0).index
    rat = Position(2, 1).index
    state = make_state(
        {
            elephant: Piece(Side.BLUE, PieceType.ELEPHANT),
            rat: Piece(Side.RED, PieceType.RAT),
        }
    )

    moves = legal_moves(state)

    assert not any(move.origin == elephant and move.destination == rat for move in moves)


def test_lion_jump_is_blocked_by_rat_in_river() -> None:
    lion = Position(2, 1).index
    blocker = Position(3, 1).index
    landing = Position(6, 1).index
    state = make_state(
        {
            lion: Piece(Side.BLUE, PieceType.LION),
            blocker: Piece(Side.RED, PieceType.RAT),
        }
    )
    moves = {move.destination for move in generate_piece_moves(state, lion)}
    assert landing not in moves


def test_lion_vertical_jump_works_without_blocker() -> None:
    lion = Position(2, 1).index
    landing = Position(6, 1).index
    state = make_state({lion: Piece(Side.BLUE, PieceType.LION)})
    moves = {move.destination for move in generate_piece_moves(state, lion)}
    assert landing in moves


def test_tiger_horizontal_jump_works() -> None:
    tiger = Position(3, 0).index
    landing = Position(3, 3).index
    state = make_state({tiger: Piece(Side.BLUE, PieceType.TIGER)})
    moves = {move.destination for move in generate_piece_moves(state, tiger)}
    assert landing in moves


def test_trap_reduces_rank_to_zero() -> None:
    trapped = Position(0, 2).index
    state = make_state({trapped: Piece(Side.BLUE, PieceType.ELEPHANT)})
    assert effective_rank(state, trapped) == 0


def test_piece_cannot_enter_own_den() -> None:
    piece_index = Position(7, 3).index
    state = make_state({piece_index: Piece(Side.BLUE, PieceType.CAT)})
    assert find_legal_move(state, piece_index, BLUE_DEN) is None


def test_den_entry_wins() -> None:
    state = make_state({RED_DEN: Piece(Side.BLUE, PieceType.CAT)}, side_to_move=Side.RED)
    result = evaluate_result(state)
    assert result.status is ResultType.DEN_ENTRY
    assert result.winner is Side.BLUE


def test_capture_all_wins() -> None:
    state = make_state({Position(6, 0).index: Piece(Side.BLUE, PieceType.CAT)}, side_to_move=Side.RED)
    result = evaluate_result(state)
    assert result.status is ResultType.CAPTURE_ALL
    assert result.winner is Side.BLUE


def test_apply_move_and_undo_redo() -> None:
    game = Game()
    move = find_legal_move(game.state, Position(6, 6).index, Position(5, 6).index)
    assert move is not None
    game.apply_move(move)
    assert game.state.board[Position(5, 6).index] is not None
    assert game.undo()
    assert game.state.board[Position(6, 6).index] is not None
    assert game.redo()
    assert game.state.board[Position(5, 6).index] is not None


def test_save_and_load_round_trip(tmp_path) -> None:
    game = Game()
    move = find_legal_move(game.state, Position(6, 6).index, Position(5, 6).index)
    assert move is not None
    game.apply_move(move)
    path = tmp_path / "save.json"
    game.save(path)
    loaded = Game.load(path)
    assert loaded.state.to_dict() == game.state.to_dict()


def test_legal_moves_exist_for_initial_position() -> None:
    assert legal_moves(initial_state())
