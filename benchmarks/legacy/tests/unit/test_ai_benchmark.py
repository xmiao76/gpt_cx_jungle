from __future__ import annotations

import pytest

from jungle.ai import SearchConfig, SearchResult
from jungle.domain import Piece, PieceType, Position, Side
from jungle.engine import Game
from jungle.rules import legal_moves

from conftest import load_tool_module


def _outcome(benchmark, side: Side, score: float, name: str = "test"):
    winner = side if score == 1.0 else side.opponent if score == 0.0 else None
    return benchmark.GameOutcome(name, "opening", side, score, 10, "test", winner)


def _responsive_result() -> SearchResult:
    return SearchResult(Game().list_moves()[0], 0, 6, 100, 2_000.0)


def test_fixed_positions_reward_winning_rat_den_races() -> None:
    benchmark = load_tool_module("ai_benchmark")
    positions = {position.name: position for position in benchmark.positions()}

    assert positions["rat_wins_den_race_from_right"].accepted_destinations == frozenset(
        {Position(1, 2).index}
    )
    assert positions["rat_wins_den_race_from_above"].accepted_destinations == frozenset(
        {Position(1, 2).index}
    )


def test_opening_corpus_contains_twelve_distinct_legal_blue_to_move_states() -> None:
    benchmark = load_tool_module("ai_benchmark")
    scenarios = benchmark.opening_scenarios()
    states = []

    assert len(scenarios) == 12
    assert len({scenario.name for scenario in scenarios}) == 12
    for scenario in scenarios:
        game = Game()
        assert len(scenario.moves) % 2 == 0
        for origin, destination in scenario.moves:
            assert (origin, destination) in {
                (move.origin, move.destination) for move in game.list_moves()
            }
            game.apply_coordinates(origin, destination)
        state = benchmark.build_opening_state(scenario)
        assert state.board == game.state.board
        states.append(state)

    assert all(state.side_to_move is Side.BLUE for state in states)
    assert all(state.winner is None and legal_moves(state) for state in states)
    assert len({benchmark.position_signature(state) for state in states}) == 12


def test_play_game_adjudicates_threefold_repetition_without_changing_rules(monkeypatch) -> None:
    benchmark = load_tool_module("ai_benchmark")
    state = benchmark.make_state(
        {
            Position(4, 0).index: Piece(Side.BLUE, PieceType.CAT),
            Position(4, 6).index: Piece(Side.RED, PieceType.CAT),
        }
    )

    class CyclingAI:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def choose_move(self, current_state):
            if current_state.side_to_move is Side.BLUE:
                origin = (
                    Position(4, 0).index
                    if current_state.board[Position(4, 0).index] is not None
                    else Position(5, 0).index
                )
                destination = (
                    Position(5, 0).index
                    if origin == Position(4, 0).index
                    else Position(4, 0).index
                )
            else:
                origin = (
                    Position(4, 6).index
                    if current_state.board[Position(4, 6).index] is not None
                    else Position(3, 6).index
                )
                destination = (
                    Position(3, 6).index
                    if origin == Position(4, 6).index
                    else Position(4, 6).index
                )
            move = next(
                move
                for move in legal_moves(current_state)
                if move.origin == origin and move.destination == destination
            )
            return SearchResult(move, 0, 1, 1, 0.0)

    monkeypatch.setattr(benchmark, "AlphaBetaAI", CyclingAI)
    outcome = benchmark.play_game(
        Side.BLUE,
        SearchConfig.hard(),
        SearchConfig.baseline(),
        state,
        node_limit=1,
        ply_cap=30,
    )

    assert outcome.score == 0.5
    assert outcome.winner is None
    assert outcome.plies == 8
    assert outcome.termination == benchmark.THREEFOLD_REPETITION
    assert state.winner is None
    assert state.move_history == []
    assert legal_moves(state)


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


def test_match_budget_models_compact_engine_throughput_advantage(monkeypatch) -> None:
    benchmark = load_tool_module("ai_benchmark")
    limits: list[int | None] = []

    class RecordingAI:
        def __init__(self, _time_limit, _config, *, node_limit=None):
            limits.append(node_limit)

        def choose_move(self, state):
            move = legal_moves(state)[0]
            return SearchResult(move, 0, 1, 1, 0.0)

    monkeypatch.setattr(benchmark, "AlphaBetaAI", RecordingAI)
    state = benchmark.make_state(
        {
            Position(1, 3).index: Piece(Side.BLUE, PieceType.CAT),
            Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
        },
        Side.BLUE,
    )

    benchmark.play_game(
        Side.BLUE,
        SearchConfig.hard(),
        SearchConfig.baseline(),
        state,
        node_limit=20,
        ply_cap=1,
    )

    assert limits == [60, 20]


def test_match_metrics_report_score_color_split_and_decisive_rate() -> None:
    benchmark = load_tool_module("ai_benchmark")
    outcomes = [
        _outcome(benchmark, Side.BLUE, 1.0),
        _outcome(benchmark, Side.BLUE, 0.5),
        _outcome(benchmark, Side.RED, 0.5),
        _outcome(benchmark, Side.RED, 0.0),
    ]

    metrics = benchmark.calculate_match_metrics(outcomes)

    assert (metrics.games, metrics.wins, metrics.draws, metrics.losses) == (4, 1, 2, 1)
    assert metrics.score == 0.5
    assert metrics.blue_score == 0.75
    assert metrics.red_score == 0.25
    assert metrics.decisive_rate == 0.5


def test_combined_match_score_weights_all_games() -> None:
    benchmark = load_tool_module("ai_benchmark")

    score = benchmark.combined_match_score([0.5] * 24, [1.0] * 4)

    assert score == pytest.approx(4 / 7)


def test_validation_does_not_allow_conversion_wins_to_pad_drawn_openings() -> None:
    benchmark = load_tool_module("ai_benchmark")
    hard = benchmark.ConfigStats("hard", 20, 20, [1.0], [6], [100])
    openings = [
        _outcome(benchmark, Side.BLUE if index % 2 == 0 else Side.RED, 0.5)
        for index in range(24)
    ]
    conversions = [
        _outcome(benchmark, Side.BLUE if index % 2 == 0 else Side.RED, 1.0)
        for index in range(4)
    ]

    with pytest.raises(SystemExit, match="opening overall score"):
        benchmark.validate_benchmark(hard, openings, conversions, _responsive_result())


def test_validation_rejects_a_weak_score_with_either_color() -> None:
    benchmark = load_tool_module("ai_benchmark")
    hard = benchmark.ConfigStats("hard", 20, 20, [1.0], [6], [100])
    openings = [
        *[_outcome(benchmark, Side.BLUE, 1.0) for _ in range(4)],
        _outcome(benchmark, Side.RED, 1.0),
        *[_outcome(benchmark, Side.RED, 0.0) for _ in range(3)],
    ]
    conversions = [_outcome(benchmark, Side.BLUE, 1.0)]

    with pytest.raises(SystemExit, match="opening red score"):
        benchmark.validate_benchmark(hard, openings, conversions, _responsive_result())


def test_validation_rejects_an_insufficient_decisive_rate() -> None:
    benchmark = load_tool_module("ai_benchmark")
    hard = benchmark.ConfigStats("hard", 20, 20, [1.0], [6], [100])
    openings = []
    for side in (Side.BLUE, Side.RED):
        openings.append(_outcome(benchmark, side, 1.0))
        openings.extend(_outcome(benchmark, side, 0.5) for _ in range(4))
    conversions = [_outcome(benchmark, Side.BLUE, 1.0)]

    with pytest.raises(SystemExit, match="decisive rate"):
        benchmark.validate_benchmark(hard, openings, conversions, _responsive_result())


def test_validation_accepts_all_thresholds_at_or_above_the_boundaries() -> None:
    benchmark = load_tool_module("ai_benchmark")
    hard = benchmark.ConfigStats("hard", 20, 20, [1.0], [6], [100])
    openings = [
        *[_outcome(benchmark, Side.BLUE, 1.0) for _ in range(3)],
        *[_outcome(benchmark, Side.BLUE, 0.5) for _ in range(7)],
        *[_outcome(benchmark, Side.RED, 1.0) for _ in range(2)],
        *[_outcome(benchmark, Side.RED, 0.5) for _ in range(8)],
    ]
    conversions = [
        _outcome(benchmark, Side.BLUE, 1.0),
        _outcome(benchmark, Side.RED, 1.0),
        _outcome(benchmark, Side.BLUE, 1.0),
        _outcome(benchmark, Side.RED, 0.0),
    ]

    benchmark.validate_benchmark(hard, openings, conversions, _responsive_result())
