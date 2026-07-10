from __future__ import annotations

from jungle.ai import AlphaBetaAI, SearchConfig
from jungle.domain import Move, Piece, PieceType, Position, Side
from jungle.engine import Game
from jungle.rules import legal_moves


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


def test_search_config_baseline_preserves_default_constructor() -> None:
    game = Game()
    default = AlphaBetaAI(80).choose_move(game.state)
    baseline = AlphaBetaAI(80, SearchConfig.baseline()).choose_move(game.state)

    assert default.move is not None
    assert baseline.move is not None
    assert (default.move.origin, default.move.destination) == (baseline.move.origin, baseline.move.destination)


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


def test_hard_search_config_is_distinct_profile() -> None:
    hard = SearchConfig.hard()

    assert hard.label == "hard"
    assert hard.use_enhanced_ordering
    assert hard.use_quiescence
    assert hard.use_killer_moves
    assert hard.use_history_heuristic
    assert hard.use_den_safety


def test_hard_search_config_enables_game_strength_features() -> None:
    hard = SearchConfig.hard()

    assert hard.force_full_evaluation
    assert hard.use_aspiration_windows
    assert hard.use_late_move_reductions
    assert hard.use_repetition_penalty
    assert hard.use_den_race_score


def test_hard_ai_avoids_unsafe_non_capture_jump() -> None:
    lion = Position(3, 0).index
    unsafe_landing = Position(3, 3).index
    state = make_state(
        {
            lion: Piece(Side.BLUE, PieceType.LION),
            Position(6, 6).index: Piece(Side.BLUE, PieceType.RAT),
            Position(2, 3).index: Piece(Side.RED, PieceType.LION),
            Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
        }
    )

    ai = AlphaBetaAI(300, SearchConfig.hard())
    result = ai.choose_move(state)

    assert result.move is not None
    assert result.move.destination != unsafe_landing


def test_hard_ai_detects_recent_reversal_from_move_history() -> None:
    cat = Piece(Side.BLUE, PieceType.CAT)
    state = make_state(
        {
            Position(3, 3).index: cat,
            Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
        }
    )
    state.move_history = [
        Move(Position(2, 3).index, Position(3, 3).index, cat),
        Move(Position(0, 6).index, Position(1, 6).index, Piece(Side.RED, PieceType.TIGER)),
    ]
    reversing_move = Move(Position(3, 3).index, Position(2, 3).index, cat)
    forward_move = Move(Position(3, 3).index, Position(4, 3).index, cat)

    ai = AlphaBetaAI(300, SearchConfig.hard())

    assert ai.is_recent_reversal(state, reversing_move)
    assert not ai.is_recent_reversal(state, forward_move)


def test_node_limit_keeps_last_fully_completed_iteration() -> None:
    game = Game()
    root_move_count = len(legal_moves(game.state))
    config = SearchConfig(label="node-limited", max_depth=4)

    result = AlphaBetaAI(10_000, config, node_limit=root_move_count + 1).choose_move(game.state)

    assert result.move in legal_moves(game.state)
    assert result.depth == 1
    assert result.nodes == root_move_count + 1


def test_hard_search_does_not_use_speculative_tactical_shortcut() -> None:
    class ShortcutProbeAI(AlphaBetaAI):
        def find_enhanced_tactical_move(self, state):
            raise AssertionError("speculative shortcut must not run")

    result = ShortcutProbeAI(10_000, SearchConfig.hard(), node_limit=0).choose_move(Game().state)

    assert result.move in legal_moves(Game().state)
    assert result.depth == 0


def test_zero_budget_fallback_uses_static_capture_ordering() -> None:
    rat = Piece(Side.BLUE, PieceType.RAT)
    elephant = Piece(Side.RED, PieceType.ELEPHANT)
    state = make_state(
        {
            Position(2, 0).index: rat,
            Position(2, 1).index: elephant,
            Position(8, 6).index: Piece(Side.RED, PieceType.LION),
        }
    )

    result = AlphaBetaAI(10_000, SearchConfig.hard(), node_limit=0).choose_move(state)

    assert result.depth == 0
    assert result.move is not None
    assert result.move.origin == Position(2, 0).index
    assert result.move.destination == Position(2, 1).index
