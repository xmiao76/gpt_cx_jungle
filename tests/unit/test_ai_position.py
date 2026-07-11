from __future__ import annotations

from jungle.domain import GameState, Move, Piece, PieceType, Position, ResultType, Side
from jungle.engine import Game


def make_state(pieces: dict[int, Piece], side_to_move: Side = Side.BLUE) -> GameState:
    board = [None] * 63
    for index, piece in pieces.items():
        board[index] = piece
    return GameState(board=board, side_to_move=side_to_move)


def assert_transition_matches_game(state: GameState, move: Move) -> GameState:
    from jungle.ai.position import apply_search_move

    expected = Game(state)
    expected.apply_move(move)
    actual = apply_search_move(state, move)

    assert actual.board == expected.state.board
    assert actual.side_to_move is expected.state.side_to_move
    assert actual.winner is expected.state.winner
    assert actual.result is expected.state.result
    assert actual.result_reason == expected.state.result_reason
    assert actual.move_history == expected.state.move_history
    return actual


def test_search_transition_matches_game_for_quiet_move_and_capture() -> None:
    blue_cat = Piece(Side.BLUE, PieceType.CAT)
    red_rat = Piece(Side.RED, PieceType.RAT)
    quiet_state = make_state(
        {
            Position(6, 0).index: blue_cat,
            Position(0, 6).index: red_rat,
        }
    )
    quiet_move = Move(Position(6, 0).index, Position(5, 0).index, blue_cat)
    quiet_result = assert_transition_matches_game(quiet_state, quiet_move)

    capture_state = quiet_result.copy()
    capture_state.side_to_move = Side.BLUE
    capture_state.board[Position(4, 0).index] = Piece(Side.RED, PieceType.RAT)
    capture_move = Move(
        Position(5, 0).index,
        Position(4, 0).index,
        blue_cat,
        captured=Piece(Side.RED, PieceType.RAT),
    )
    assert_transition_matches_game(capture_state, capture_move)


def test_search_transition_matches_game_for_den_and_capture_all_wins() -> None:
    blue_cat = Piece(Side.BLUE, PieceType.CAT)
    red_rat = Piece(Side.RED, PieceType.RAT)
    den_state = make_state(
        {
            Position(1, 3).index: blue_cat,
            Position(8, 6).index: red_rat,
        }
    )
    den_move = Move(Position(1, 3).index, Position(0, 3).index, blue_cat)
    den_result = assert_transition_matches_game(den_state, den_move)
    assert den_result.result is ResultType.DEN_ENTRY

    capture_state = make_state(
        {
            Position(2, 0).index: blue_cat,
            Position(2, 1).index: red_rat,
        }
    )
    capture_move = Move(Position(2, 0).index, Position(2, 1).index, blue_cat, captured=red_rat)
    capture_result = assert_transition_matches_game(capture_state, capture_move)
    assert capture_result.result is ResultType.CAPTURE_ALL


def test_search_transition_keeps_only_recent_history() -> None:
    from jungle.ai.position import SEARCH_HISTORY_LIMIT, apply_search_move

    blue_cat = Piece(Side.BLUE, PieceType.CAT)
    red_cat = Piece(Side.RED, PieceType.CAT)
    state = make_state(
        {
            Position(6, 0).index: blue_cat,
            Position(2, 6).index: red_cat,
        }
    )
    state.move_history = [
        Move(Position(6, 0).index, Position(5, 0).index, blue_cat),
        Move(Position(2, 6).index, Position(3, 6).index, red_cat),
    ] * (SEARCH_HISTORY_LIMIT + 1)
    move = Move(Position(6, 0).index, Position(6, 1).index, blue_cat)

    result = apply_search_move(state, move)

    assert len(result.move_history) == SEARCH_HISTORY_LIMIT
    assert result.move_history[-1] == move


def test_recent_position_counts_reconstructs_reversible_cycle() -> None:
    from jungle.ai.position import position_key, recent_position_counts

    game = Game(
        make_state(
            {
                Position(6, 0).index: Piece(Side.BLUE, PieceType.CAT),
                Position(2, 6).index: Piece(Side.RED, PieceType.CAT),
            }
        )
    )
    for origin, destination in (
        (Position(6, 0).index, Position(5, 0).index),
        (Position(2, 6).index, Position(3, 6).index),
        (Position(5, 0).index, Position(6, 0).index),
        (Position(3, 6).index, Position(2, 6).index),
    ):
        game.apply_coordinates(origin, destination)

    counts = recent_position_counts(game.state)

    assert counts[position_key(game.state)] == 2
