from __future__ import annotations

from jungle.ai import AlphaBetaAI, SearchConfig
from jungle.domain import Piece, PieceType, Position, Side
from jungle.engine import Game


def make_state(pieces, side_to_move=Side.BLUE):
    from jungle.domain import GameState

    board = [None] * 63
    for index, piece in pieces.items():
        board[index] = piece
    return GameState(board=board, side_to_move=side_to_move)


def test_ai_returns_a_move_from_initial_position() -> None:
    game = Game()
    ai = AlphaBetaAI(80)
    result = ai.choose_move(game.state)
    assert result.move is not None


def test_ai_prefers_den_entry_when_available() -> None:
    blue_cat = Position(1, 3).index
    state = make_state(
        {
            blue_cat: Piece(Side.BLUE, PieceType.CAT),
            Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
        }
    )
    ai = AlphaBetaAI(80)
    result = ai.choose_move(state)
    assert result.move is not None
    assert result.move.destination == Position(0, 3).index


def test_ai_blocks_immediate_den_entry_threat() -> None:
    red_cat_in_blue_trap = Position(7, 3).index
    blue_dog = Position(7, 2).index
    state = make_state(
        {
            red_cat_in_blue_trap: Piece(Side.RED, PieceType.CAT),
            blue_dog: Piece(Side.BLUE, PieceType.DOG),
            Position(0, 0).index: Piece(Side.RED, PieceType.LION),
        }
    )

    ai = AlphaBetaAI(300)
    result = ai.choose_move(state)

    assert result.move is not None
    assert result.move.origin == blue_dog
    assert result.move.destination == red_cat_in_blue_trap


def test_ai_uses_trap_to_capture_stronger_piece() -> None:
    red_elephant_in_blue_trap = Position(7, 3).index
    blue_rat = Position(7, 2).index
    state = make_state(
        {
            red_elephant_in_blue_trap: Piece(Side.RED, PieceType.ELEPHANT),
            blue_rat: Piece(Side.BLUE, PieceType.RAT),
            Position(0, 0).index: Piece(Side.RED, PieceType.LION),
        }
    )

    ai = AlphaBetaAI(300)
    result = ai.choose_move(state)

    assert result.move is not None
    assert result.move.origin == blue_rat
    assert result.move.destination == red_elephant_in_blue_trap


def test_ai_rat_captures_elephant_but_elephant_does_not_chase_rat() -> None:
    blue_rat = Position(2, 0).index
    red_elephant = Position(2, 1).index
    state = make_state(
        {
            blue_rat: Piece(Side.BLUE, PieceType.RAT),
            red_elephant: Piece(Side.RED, PieceType.ELEPHANT),
            Position(8, 6).index: Piece(Side.RED, PieceType.LION),
        }
    )

    ai = AlphaBetaAI(300)
    result = ai.choose_move(state)

    assert result.move is not None
    assert result.move.origin == blue_rat
    assert result.move.destination == red_elephant


def test_search_config_stronger_is_default_constructor() -> None:
    game = Game()
    default = AlphaBetaAI(80).choose_move(game.state)
    stronger = AlphaBetaAI(80, SearchConfig.stronger()).choose_move(game.state)

    assert default.move is not None
    assert stronger.move is not None
    assert (default.move.origin, default.move.destination) == (stronger.move.origin, stronger.move.destination)


def test_search_config_legacy_positional_constructor_shape_is_preserved() -> None:
    config = SearchConfig("medium", True, False, True, 1, 4, 1)

    assert config.quiescence_max_depth == 1
    assert config.quiescence_candidate_limit == 4
    assert config.threat_weight == 1
    assert config.use_killer_moves is False
    assert config.use_history_ordering is False


def test_candidate_ai_respects_tiger_jump_limit() -> None:
    tiger = Position(2, 1).index
    blocked_span_landing = Position(6, 1).index
    legal_step = Position(2, 0).index
    state = make_state(
        {
            tiger: Piece(Side.BLUE, PieceType.TIGER),
            Position(8, 6).index: Piece(Side.RED, PieceType.LION),
        }
    )

    ai = AlphaBetaAI(300, SearchConfig.candidate())
    result = ai.choose_move(state)

    assert result.move is not None
    assert result.move.destination in {legal_step, Position(2, 2).index, Position(1, 1).index}
    assert result.move.destination != blocked_span_landing


def test_candidate_ai_can_use_lion_three_square_span_jump() -> None:
    lion = Position(3, 0).index
    landing = Position(3, 3).index
    state = make_state(
        {
            lion: Piece(Side.BLUE, PieceType.LION),
            landing: Piece(Side.RED, PieceType.RAT),
        }
    )

    ai = AlphaBetaAI(300, SearchConfig.candidate())
    result = ai.choose_move(state)

    assert result.move is not None
    assert result.move.destination == landing
