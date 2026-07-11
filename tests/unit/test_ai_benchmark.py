from __future__ import annotations

import pytest

from jungle.ai import SearchConfig, SearchResult
from jungle.domain import Piece, PieceType, Position, Side
from jungle.rules import legal_moves

from conftest import load_tool_module


def test_fixed_positions_reward_winning_rat_den_races() -> None:
    benchmark = load_tool_module("ai_benchmark")
    positions = {position.name: position for position in benchmark.positions()}

    assert positions["rat_wins_den_race_from_right"].accepted_destinations == frozenset(
        {Position(1, 2).index}
    )
    assert positions["rat_wins_den_race_from_above"].accepted_destinations == frozenset(
        {Position(1, 2).index}
    )


def test_opening_scenarios_build_distinct_legal_blue_to_move_states() -> None:
    benchmark = load_tool_module("ai_benchmark")

    scenarios = benchmark.opening_scenarios()
    states = [benchmark.build_opening_state(scenario) for scenario in scenarios]

    assert len(states) == 4
    assert all(state.side_to_move is Side.BLUE for state in states)
    assert len({tuple(state.board) for state in states}) == len(states)
    assert all(legal_moves(state) for state in states)


def test_combined_match_score_weights_all_games() -> None:
    benchmark = load_tool_module("ai_benchmark")

    score = benchmark.combined_match_score([0.5] * 8, [1.0] * 4)

    assert score == 2 / 3


def test_score_game_uses_node_limited_ai_and_completes_den_win() -> None:
    benchmark = load_tool_module("ai_benchmark")
    state = benchmark.make_state(
        {
            Position(1, 3).index: Piece(Side.BLUE, PieceType.CAT),
            Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
        },
        Side.BLUE,
    )

    score = benchmark.score_game(
        Side.BLUE,
        SearchConfig.hard(),
        SearchConfig.baseline(),
        state,
        node_limit=20,
        turn_cap=4,
    )

    assert score == 1.0


def test_validation_rejects_weak_combined_match_score() -> None:
    benchmark = load_tool_module("ai_benchmark")
    hard = benchmark.ConfigStats("hard", 11, 11, [1.0], [4], [100])
    responsive = SearchResult(None, 0, 4, 100, 1_800.0)

    with pytest.raises(SystemExit, match="combined match score"):
        benchmark.validate_benchmark(hard, [0.5] * 8, [0.5] * 4, responsive)
