from __future__ import annotations

from jungle.ai import AlphaBetaAI, SearchConfig
from jungle.ai.search import TERMINAL_SCORE
from jungle.domain import GameState, Move, Piece, PieceType, Position, ResultType, Side


def make_state(pieces: dict[int, Piece], side_to_move: Side = Side.BLUE) -> GameState:
    board = [None] * 63
    for index, piece in pieces.items():
        board[index] = piece
    return GameState(board=board, side_to_move=side_to_move)


def choose(state: GameState, time_ms: int = 120) -> Move:
    result = AlphaBetaAI(time_ms, SearchConfig.candidate()).choose_move(state)
    assert result.move is not None
    assert result.elapsed_ms <= time_ms + 40
    return result.move


def test_candidate_rat_takes_elephant_from_right() -> None:
    state = make_state(
        {
            Position(2, 2).index: Piece(Side.BLUE, PieceType.RAT),
            Position(2, 1).index: Piece(Side.RED, PieceType.ELEPHANT),
            Position(8, 6).index: Piece(Side.RED, PieceType.LION),
        }
    )

    move = choose(state)

    assert move.origin == Position(2, 2).index
    assert move.destination == Position(2, 1).index


def test_candidate_rat_takes_elephant_from_above() -> None:
    state = make_state(
        {
            Position(1, 1).index: Piece(Side.BLUE, PieceType.RAT),
            Position(2, 1).index: Piece(Side.RED, PieceType.ELEPHANT),
            Position(8, 6).index: Piece(Side.RED, PieceType.LION),
        }
    )

    move = choose(state)

    assert move.origin == Position(1, 1).index
    assert move.destination == Position(2, 1).index


def test_candidate_prefers_tiger_two_square_river_jump() -> None:
    state = make_state(
        {
            Position(3, 0).index: Piece(Side.BLUE, PieceType.TIGER),
            Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
        }
    )

    move = choose(state)

    assert move.origin == Position(3, 0).index
    assert move.destination == Position(3, 3).index
    assert move.is_jump


def test_candidate_avoids_losing_piece_after_bad_capture() -> None:
    blue_cat = Position(6, 2).index
    red_rat = Position(5, 2).index
    safer_step = Position(6, 1).index
    state = make_state(
        {
            blue_cat: Piece(Side.BLUE, PieceType.CAT),
            red_rat: Piece(Side.RED, PieceType.RAT),
            Position(5, 3).index: Piece(Side.RED, PieceType.DOG),
            Position(8, 6).index: Piece(Side.RED, PieceType.LION),
        }
    )

    move = choose(state, time_ms=180)

    assert move.destination in {safer_step, Position(7, 2).index, Position(6, 3).index}
    assert move.destination != red_rat


def test_ai_prefers_fastest_den_entry_path() -> None:
    near_den_cat = Position(1, 3).index
    slower_lion = Position(3, 0).index
    state = make_state(
        {
            near_den_cat: Piece(Side.BLUE, PieceType.CAT),
            slower_lion: Piece(Side.BLUE, PieceType.LION),
            Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
        }
    )

    move = choose(state, time_ms=120)

    assert move.origin == near_den_cat
    assert move.destination == Position(0, 3).index


def test_terminal_scores_are_not_reused_across_different_plies() -> None:
    state = make_state(
        {
            Position(0, 3).index: Piece(Side.BLUE, PieceType.CAT),
            Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
        },
        side_to_move=Side.RED,
    )
    state.winner = Side.BLUE
    state.result = ResultType.DEN_ENTRY
    state.result_reason = "Blue entered red den"
    ai = AlphaBetaAI(120, SearchConfig.candidate())
    ai.deadline = float("inf")

    first_score = ai._alphabeta(state, depth=0, alpha=-1_000_000, beta=1_000_000, ply=1)
    second_score = ai._alphabeta(state, depth=0, alpha=-1_000_000, beta=1_000_000, ply=5)

    assert first_score == -TERMINAL_SCORE + 1
    assert second_score == -TERMINAL_SCORE + 5


def test_default_ai_reaches_search_depth_under_short_time_limit() -> None:
    state = make_state(
        {
            Position(6, 0).index: Piece(Side.BLUE, PieceType.ELEPHANT),
            Position(6, 2).index: Piece(Side.BLUE, PieceType.WOLF),
            Position(6, 4).index: Piece(Side.BLUE, PieceType.LEOPARD),
            Position(6, 6).index: Piece(Side.BLUE, PieceType.RAT),
            Position(7, 1).index: Piece(Side.BLUE, PieceType.CAT),
            Position(7, 5).index: Piece(Side.BLUE, PieceType.DOG),
            Position(8, 0).index: Piece(Side.BLUE, PieceType.TIGER),
            Position(8, 6).index: Piece(Side.BLUE, PieceType.LION),
            Position(2, 0).index: Piece(Side.RED, PieceType.RAT),
            Position(2, 2).index: Piece(Side.RED, PieceType.LEOPARD),
            Position(2, 4).index: Piece(Side.RED, PieceType.WOLF),
            Position(2, 6).index: Piece(Side.RED, PieceType.ELEPHANT),
            Position(1, 1).index: Piece(Side.RED, PieceType.DOG),
            Position(1, 5).index: Piece(Side.RED, PieceType.CAT),
            Position(0, 0).index: Piece(Side.RED, PieceType.LION),
            Position(0, 6).index: Piece(Side.RED, PieceType.TIGER),
        }
    )

    result = AlphaBetaAI(180).choose_move(state)

    assert result.move is not None
    assert result.depth >= 2
    assert result.elapsed_ms <= 230


def test_ai_values_entering_enemy_trap_near_den() -> None:
    cat = Position(2, 3).index
    trap = Position(1, 3).index
    state = make_state(
        {
            cat: Piece(Side.BLUE, PieceType.CAT),
            Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
        }
    )

    move = choose(state, time_ms=120)

    assert move.origin == cat
    assert move.destination == trap


def test_ai_does_not_walk_high_value_piece_into_simple_capture() -> None:
    blue_elephant = Position(6, 0).index
    state = make_state(
        {
            blue_elephant: Piece(Side.BLUE, PieceType.ELEPHANT),
            Position(5, 1).index: Piece(Side.RED, PieceType.RAT),
            Position(8, 6).index: Piece(Side.RED, PieceType.LION),
        }
    )

    move = choose(state, time_ms=180)

    assert move.origin == blue_elephant
    assert move.destination != Position(6, 1).index
