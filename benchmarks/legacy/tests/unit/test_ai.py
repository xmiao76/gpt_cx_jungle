from __future__ import annotations

import math
import time
from collections import Counter

from jungle.ai import AlphaBetaAI, SearchConfig
from jungle.ai.evaluation import TERMINAL_SCORE
from jungle.ai.position import apply_search_move, position_key
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
    default = AlphaBetaAI(10_000, node_limit=500).choose_move(game.state)
    baseline = AlphaBetaAI(10_000, SearchConfig.baseline(), node_limit=500).choose_move(game.state)

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
    assert hard.use_principal_variation_search
    assert hard.use_cycle_detection


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


def test_move_ordering_does_not_simulate_child_positions() -> None:
    class StaticOrderingAI(AlphaBetaAI):
        def apply(self, state, move):
            raise AssertionError("move ordering must remain static")

    game = Game()
    ai = StaticOrderingAI(1_000, SearchConfig.hard())

    ordered = ai.order_moves(game.state, legal_moves(game.state), tactical=True)

    assert set(ordered) == set(legal_moves(game.state))


def test_forcing_move_generation_is_static_without_den_threat() -> None:
    class StaticForcingAI(AlphaBetaAI):
        def apply(self, state, move):
            raise AssertionError("quiet forcing generation must remain static")

    rat = Piece(Side.BLUE, PieceType.RAT)
    elephant = Piece(Side.RED, PieceType.ELEPHANT)
    state = make_state(
        {
            Position(2, 0).index: rat,
            Position(2, 1).index: elephant,
            Position(8, 6).index: Piece(Side.RED, PieceType.LION),
        }
    )

    forcing = StaticForcingAI(1_000, SearchConfig.hard()).forcing_moves(state)

    assert any(move.destination == Position(2, 1).index for move in forcing)


def test_forcing_moves_under_den_threat_exclude_irrelevant_captures() -> None:
    state = make_state(
        {
            Position(7, 3).index: Piece(Side.RED, PieceType.CAT),
            Position(7, 2).index: Piece(Side.BLUE, PieceType.DOG),
            Position(2, 0).index: Piece(Side.BLUE, PieceType.RAT),
            Position(2, 1).index: Piece(Side.RED, PieceType.ELEPHANT),
            Position(0, 0).index: Piece(Side.RED, PieceType.LION),
        },
        Side.BLUE,
    )
    ai = AlphaBetaAI(1_000, SearchConfig.hard())

    forcing = ai.forcing_moves(state, under_den_threat=True)

    assert any(move.destination == Position(7, 3).index for move in forcing)
    assert all(move.destination != Position(2, 1).index for move in forcing)


def test_terminal_scores_prefer_faster_wins_and_slower_losses() -> None:
    state = make_state({Position(0, 3).index: Piece(Side.BLUE, PieceType.CAT)}, Side.RED)
    state.winner = Side.BLUE

    ai = AlphaBetaAI(1_000)

    assert ai.terminal_score(state, Side.BLUE, ply=3) == TERMINAL_SCORE - 3
    assert ai.terminal_score(state, Side.RED, ply=3) == -TERMINAL_SCORE + 3


def test_search_scores_no_legal_moves_as_a_terminal_loss() -> None:
    board = [Piece(Side.BLUE, PieceType.ELEPHANT) for _ in range(63)]
    board[Position(4, 3).index] = Piece(Side.RED, PieceType.RAT)
    state = make_state({index: piece for index, piece in enumerate(board)}, Side.BLUE)
    assert legal_moves(state) == []

    ai = AlphaBetaAI(1_000)
    ai.deadline = time.perf_counter() + 1

    assert ai._alphabeta(state, 1, -math.inf, math.inf, ply=4) == -TERMINAL_SCORE + 4


def test_transposition_scores_preserve_mate_distance_across_plies() -> None:
    ai = AlphaBetaAI(1_000)

    stored_win = ai.score_to_tt(TERMINAL_SCORE - 5, ply=5)
    stored_loss = ai.score_to_tt(-TERMINAL_SCORE + 5, ply=5)

    assert ai.score_from_tt(stored_win, ply=2) == TERMINAL_SCORE - 2
    assert ai.score_from_tt(stored_loss, ply=2) == -TERMINAL_SCORE + 2
    assert ai.score_from_tt(ai.score_to_tt(1234, ply=5), ply=2) == 1234


def test_principal_variation_search_uses_null_windows_for_later_moves() -> None:
    class WindowProbeAI(AlphaBetaAI):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.windows = []

        def _alphabeta(self, state, depth, alpha, beta, ply=0):
            self.windows.append((alpha, beta))
            return super()._alphabeta(state, depth, alpha, beta, ply)

    state = make_state(
        {
            Position(6, 0).index: Piece(Side.BLUE, PieceType.CAT),
            Position(2, 6).index: Piece(Side.RED, PieceType.CAT),
        }
    )
    config = SearchConfig(label="pvs", max_depth=2, use_principal_variation_search=True)
    ai = WindowProbeAI(10_000, config)

    result = ai.choose_move(state)

    assert result.depth == 2
    assert any(math.isfinite(alpha) and math.isfinite(beta) and beta - alpha == 1 for alpha, beta in ai.windows)


def test_cycle_detection_penalizes_seen_child_without_recursing() -> None:
    class CycleProbeAI(AlphaBetaAI):
        def _alphabeta(self, state, depth, alpha, beta, ply=0):
            raise AssertionError("repeated position must not be searched again")

    game = Game()
    move = legal_moves(game.state)[0]
    child = apply_search_move(game.state, move)
    ai = CycleProbeAI(1_000, SearchConfig.hard())
    ai.path_counts = Counter({position_key(child): 1})

    score = ai._negamax_child(child, 2, -math.inf, math.inf, 1)

    assert score == -SearchConfig.hard().repetition_penalty * 8


def test_equal_root_scores_use_static_tactical_tie_break() -> None:
    class EqualScoreAI(AlphaBetaAI):
        def _search_child(self, child, depth, alpha, beta, ply, later_move):
            return 0

    rat = Piece(Side.BLUE, PieceType.RAT)
    elephant = Piece(Side.RED, PieceType.ELEPHANT)
    state = make_state(
        {
            Position(2, 0).index: rat,
            Position(2, 1).index: elephant,
            Position(8, 6).index: Piece(Side.RED, PieceType.LION),
        }
    )
    quiet = next(move for move in legal_moves(state) if move.captured is None)
    ai = EqualScoreAI(1_000, SearchConfig.hard())
    ai.deadline = time.perf_counter() + 1

    _score, move = ai._search_root(state, 2, quiet)

    assert move is not None
    assert move.destination == Position(2, 1).index


def test_root_tie_break_does_not_treat_alpha_bound_as_exact() -> None:
    class BoundScoreAI(AlphaBetaAI):
        def _search_child(self, child, depth, alpha, beta, ply, later_move):
            elephant_alive = any(
                piece is not None and piece.side is Side.RED and piece.kind is PieceType.ELEPHANT
                for piece in child.board
            )
            if elephant_alive:
                return 0
            return -100 if math.isinf(alpha) and math.isinf(beta) else alpha

    rat = Piece(Side.BLUE, PieceType.RAT)
    state = make_state(
        {
            Position(2, 0).index: rat,
            Position(2, 1).index: Piece(Side.RED, PieceType.ELEPHANT),
            Position(8, 6).index: Piece(Side.RED, PieceType.LION),
        }
    )
    safe = next(move for move in legal_moves(state) if move.captured is None)
    ai = BoundScoreAI(1_000, SearchConfig.hard())
    ai.deadline = time.perf_counter() + 1

    _score, move = ai._search_root(state, 2, safe)

    assert move is not None
    assert move.destination != Position(2, 1).index


def test_quiescence_uses_ply_aware_terminal_score() -> None:
    state = make_state({Position(0, 3).index: Piece(Side.BLUE, PieceType.CAT)}, Side.RED)
    state.winner = Side.BLUE
    ai = AlphaBetaAI(1_000, SearchConfig.hard())
    ai.deadline = time.perf_counter() + 1

    score = ai._quiescence(state, -math.inf, math.inf, extension_depth=0, ply=5)

    assert score == -TERMINAL_SCORE + 5


def test_quiescence_cannot_stand_pat_under_immediate_den_threat() -> None:
    class OptimisticEvaluationAI(AlphaBetaAI):
        def evaluate(self, state, perspective):
            return 10_000

    state = make_state(
        {
            Position(7, 3).index: Piece(Side.RED, PieceType.CAT),
            Position(7, 2).index: Piece(Side.BLUE, PieceType.DOG),
            Position(0, 0).index: Piece(Side.RED, PieceType.LION),
        },
        Side.BLUE,
    )
    ai = OptimisticEvaluationAI(1_000, SearchConfig.hard())
    ai.deadline = time.perf_counter() + 1

    score = ai._quiescence(state, -math.inf, 0, extension_depth=0, ply=0)

    assert score < 0


def test_quiescence_scores_unavoidable_den_threat_as_loss() -> None:
    state = make_state(
        {
            Position(7, 3).index: Piece(Side.RED, PieceType.CAT),
            Position(6, 0).index: Piece(Side.BLUE, PieceType.CAT),
            Position(0, 0).index: Piece(Side.RED, PieceType.LION),
        },
        Side.BLUE,
    )
    ai = AlphaBetaAI(1_000, SearchConfig.hard())
    ai.deadline = time.perf_counter() + 1

    score = ai._quiescence(state, -math.inf, math.inf, extension_depth=0, ply=4)

    assert score == -TERMINAL_SCORE + 4


def test_choose_move_handles_state_with_no_legal_moves() -> None:
    board = [Piece(Side.BLUE, PieceType.ELEPHANT) for _ in range(63)]
    board[Position(4, 3).index] = Piece(Side.RED, PieceType.RAT)
    state = make_state({index: piece for index, piece in enumerate(board)}, Side.BLUE)

    result = AlphaBetaAI(1_000, SearchConfig.hard()).choose_move(state)

    assert result.move is None
    assert result.score == -TERMINAL_SCORE
    assert result.depth == 0
