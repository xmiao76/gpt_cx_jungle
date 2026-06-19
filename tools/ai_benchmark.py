from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import median
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jungle.ai import AlphaBetaAI, SearchConfig
from jungle.domain import GameState, Move, Piece, PieceType, Position, Side
from jungle.engine import Game


FIXED_TIME_MS = 80
HEAD_TO_HEAD_TIME_MS = 120
HEAD_TO_HEAD_TURN_CAP = 80


@dataclass(frozen=True, slots=True)
class BenchmarkPosition:
    name: str
    state: GameState
    accepted_destinations: frozenset[int]
    accepted_origins: frozenset[int] = frozenset()

    def accepts(self, move: Move | None) -> bool:
        if move is None:
            return False
        if self.accepted_origins and move.origin not in self.accepted_origins:
            return False
        return move.destination in self.accepted_destinations


@dataclass(slots=True)
class ConfigStats:
    label: str
    passed: int
    total: int
    elapsed_values: list[float]
    depths: list[int]
    nodes: list[int]

    @property
    def median_elapsed(self) -> float:
        return median(self.elapsed_values) if self.elapsed_values else 0.0

    @property
    def worst_elapsed(self) -> float:
        return max(self.elapsed_values) if self.elapsed_values else 0.0


@dataclass(frozen=True, slots=True)
class HeadToHeadScenario:
    name: str
    state: GameState
    stronger_side: Side


def make_state(pieces: dict[int, Piece], side_to_move: Side = Side.BLUE) -> GameState:
    board = [None] * 63
    for index, piece in pieces.items():
        board[index] = piece
    return GameState(board=board, side_to_move=side_to_move)


def positions() -> list[BenchmarkPosition]:
    return [
        BenchmarkPosition(
            "immediate_den_entry",
            make_state(
                {
                    Position(1, 3).index: Piece(Side.BLUE, PieceType.CAT),
                    Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
                }
            ),
            frozenset({Position(0, 3).index}),
        ),
        BenchmarkPosition(
            "block_den_entry",
            make_state(
                {
                    Position(7, 3).index: Piece(Side.RED, PieceType.CAT),
                    Position(7, 2).index: Piece(Side.BLUE, PieceType.DOG),
                    Position(0, 0).index: Piece(Side.RED, PieceType.LION),
                }
            ),
            frozenset({Position(7, 3).index}),
        ),
        BenchmarkPosition(
            "trap_capture",
            make_state(
                {
                    Position(7, 3).index: Piece(Side.RED, PieceType.ELEPHANT),
                    Position(7, 2).index: Piece(Side.BLUE, PieceType.RAT),
                    Position(0, 0).index: Piece(Side.RED, PieceType.LION),
                }
            ),
            frozenset({Position(7, 3).index}),
        ),
        BenchmarkPosition(
            "rat_takes_elephant",
            make_state(
                {
                    Position(2, 0).index: Piece(Side.BLUE, PieceType.RAT),
                    Position(2, 1).index: Piece(Side.RED, PieceType.ELEPHANT),
                    Position(8, 6).index: Piece(Side.RED, PieceType.LION),
                }
            ),
            frozenset({Position(2, 1).index}),
        ),
        BenchmarkPosition(
            "rat_takes_elephant_from_right",
            make_state(
                {
                    Position(2, 2).index: Piece(Side.BLUE, PieceType.RAT),
                    Position(2, 1).index: Piece(Side.RED, PieceType.ELEPHANT),
                    Position(8, 6).index: Piece(Side.RED, PieceType.LION),
                }
            ),
            frozenset({Position(2, 1).index}),
        ),
        BenchmarkPosition(
            "rat_takes_elephant_from_above",
            make_state(
                {
                    Position(1, 1).index: Piece(Side.BLUE, PieceType.RAT),
                    Position(2, 1).index: Piece(Side.RED, PieceType.ELEPHANT),
                    Position(8, 6).index: Piece(Side.RED, PieceType.LION),
                }
            ),
            frozenset({Position(2, 1).index}),
        ),
        BenchmarkPosition(
            "lion_uses_three_square_span",
            make_state(
                {
                    Position(3, 0).index: Piece(Side.BLUE, PieceType.LION),
                    Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
                }
            ),
            frozenset({Position(3, 3).index}),
        ),
        BenchmarkPosition(
            "lion_avoids_unsafe_empty_jump",
            make_state(
                {
                    Position(3, 0).index: Piece(Side.BLUE, PieceType.LION),
                    Position(6, 6).index: Piece(Side.BLUE, PieceType.RAT),
                    Position(2, 3).index: Piece(Side.RED, PieceType.LION),
                    Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
                }
            ),
            frozenset(
                {
                    Position(4, 0).index,
                    Position(2, 0).index,
                    Position(7, 6).index,
                    Position(5, 6).index,
                    Position(6, 5).index,
                }
            ),
        ),
        BenchmarkPosition(
            "tiger_uses_two_square_span",
            make_state(
                {
                    Position(3, 0).index: Piece(Side.BLUE, PieceType.TIGER),
                    Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
                }
            ),
            frozenset({Position(3, 3).index}),
        ),
        BenchmarkPosition(
            "tiger_avoids_three_square_span",
            make_state(
                {
                    Position(2, 1).index: Piece(Side.BLUE, PieceType.TIGER),
                    Position(8, 6).index: Piece(Side.RED, PieceType.LION),
                }
            ),
            frozenset({Position(2, 0).index, Position(2, 2).index, Position(1, 1).index}),
        ),
        BenchmarkPosition(
            "den_race_pressure",
            make_state(
                {
                    Position(2, 3).index: Piece(Side.BLUE, PieceType.CAT),
                    Position(7, 6).index: Piece(Side.RED, PieceType.ELEPHANT),
                    Position(8, 0).index: Piece(Side.BLUE, PieceType.RAT),
                }
            ),
            frozenset({Position(1, 3).index}),
        ),
    ]


def evaluate_fixed_positions(config: SearchConfig, time_limit_ms: int = FIXED_TIME_MS) -> ConfigStats:
    elapsed_values: list[float] = []
    depths: list[int] = []
    nodes: list[int] = []
    passed = 0
    print(f"\nfixed_positions config={config.label} time_ms={time_limit_ms}")
    for position in positions():
        result = AlphaBetaAI(time_limit_ms, config).choose_move(position.state)
        ok = position.accepts(result.move)
        passed += int(ok)
        elapsed_values.append(result.elapsed_ms)
        depths.append(result.depth)
        nodes.append(result.nodes)
        move_text = "none" if result.move is None else f"{result.move.origin}->{result.move.destination}"
        print(
            f"  {position.name}: {'PASS' if ok else 'FAIL'} move={move_text} "
            f"depth={result.depth} nodes={result.nodes} elapsed_ms={result.elapsed_ms:.0f}"
        )
    return ConfigStats(config.label, passed, len(positions()), elapsed_values, depths, nodes)


def head_to_head_scenarios() -> list[HeadToHeadScenario]:
    return [
        HeadToHeadScenario(
            "blue_den_race_conversion",
            make_state(
                {
                    Position(2, 3).index: Piece(Side.BLUE, PieceType.CAT),
                    Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
                    Position(8, 0).index: Piece(Side.BLUE, PieceType.RAT),
                },
                Side.BLUE,
            ),
            Side.BLUE,
        ),
        HeadToHeadScenario(
            "red_den_race_conversion",
            make_state(
                {
                    Position(6, 3).index: Piece(Side.RED, PieceType.CAT),
                    Position(0, 0).index: Piece(Side.BLUE, PieceType.RAT),
                    Position(0, 6).index: Piece(Side.RED, PieceType.RAT),
                },
                Side.RED,
            ),
            Side.RED,
        ),
        HeadToHeadScenario(
            "blue_trap_pressure_conversion",
            make_state(
                {
                    Position(1, 2).index: Piece(Side.BLUE, PieceType.CAT),
                    Position(1, 3).index: Piece(Side.RED, PieceType.ELEPHANT),
                    Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
                },
                Side.BLUE,
            ),
            Side.BLUE,
        ),
        HeadToHeadScenario(
            "red_trap_pressure_conversion",
            make_state(
                {
                    Position(7, 4).index: Piece(Side.RED, PieceType.CAT),
                    Position(7, 3).index: Piece(Side.BLUE, PieceType.ELEPHANT),
                    Position(0, 0).index: Piece(Side.BLUE, PieceType.RAT),
                },
                Side.RED,
            ),
            Side.RED,
        ),
    ]


def score_game(
    stronger_side: Side,
    stronger_config: SearchConfig,
    baseline_config: SearchConfig,
    initial_state: GameState | None = None,
) -> float:
    game = Game(initial_state)
    turns = 0
    while game.state.winner is None and turns < HEAD_TO_HEAD_TURN_CAP:
        if game.state.side_to_move is stronger_side:
            config = stronger_config
        else:
            config = baseline_config
        result = AlphaBetaAI(HEAD_TO_HEAD_TIME_MS, config).choose_move(game.state)
        if result.move is None:
            break
        game.apply_move(result.move)
        turns += 1
    if game.state.winner is stronger_side:
        return 1.0
    if game.state.winner is stronger_side.opponent:
        return 0.0
    return 0.5


def run_initial_head_to_head(stronger_config: SearchConfig, baseline_config: SearchConfig) -> float:
    scores = [
        score_game(Side.BLUE, stronger_config, baseline_config),
        score_game(Side.RED, stronger_config, baseline_config),
        score_game(Side.BLUE, stronger_config, baseline_config),
        score_game(Side.RED, stronger_config, baseline_config),
    ]
    score = sum(scores) / len(scores)
    print(
        "\ninitial_head_to_head "
        f"stronger={stronger_config.label} baseline={baseline_config.label} "
        f"time_ms={HEAD_TO_HEAD_TIME_MS} turn_cap={HEAD_TO_HEAD_TURN_CAP} "
        f"scores={scores} score={score:.2f}"
    )
    return score


def run_seeded_head_to_head(stronger_config: SearchConfig, baseline_config: SearchConfig) -> float:
    scenarios = head_to_head_scenarios()
    scores: list[float] = []
    print(
        "\nseeded_head_to_head "
        f"stronger={stronger_config.label} baseline={baseline_config.label} "
        f"time_ms={HEAD_TO_HEAD_TIME_MS} turn_cap={HEAD_TO_HEAD_TURN_CAP}"
    )
    for scenario in scenarios:
        score = score_game(scenario.stronger_side, stronger_config, baseline_config, scenario.state)
        scores.append(score)
        print(f"  {scenario.name}: score={score:.2f} stronger_side={scenario.stronger_side.value}")
    total = sum(scores) / len(scores)
    print(f"  seeded_score={total:.2f}")
    return total


def print_summary(
    baseline: ConfigStats,
    medium: ConfigStats,
    hard: ConfigStats,
    initial_head_to_head_score: float,
    seeded_head_to_head_score: float,
) -> None:
    print("\nsummary")
    for stats in (baseline, medium, hard):
        avg_depth = sum(stats.depths) / len(stats.depths)
        avg_nodes = sum(stats.nodes) / len(stats.nodes)
        print(
            f"  {stats.label}: passed={stats.passed}/{stats.total} "
            f"median_ms={stats.median_elapsed:.0f} worst_ms={stats.worst_elapsed:.0f} "
            f"avg_depth={avg_depth:.1f} avg_nodes={avg_nodes:.0f}"
        )
    print(f"  hard_fixed_position_delta={hard.passed - baseline.passed}")
    combined_head_to_head = (initial_head_to_head_score + seeded_head_to_head_score) / 2
    print(f"  hard_initial_head_to_head_score={initial_head_to_head_score:.2f}")
    print(f"  hard_seeded_head_to_head_score={seeded_head_to_head_score:.2f}")
    print(f"  hard_combined_head_to_head_score={combined_head_to_head:.2f}")


def main() -> None:
    baseline_config = SearchConfig.baseline()
    medium_config = SearchConfig(
        label="medium",
        use_threat_score=True,
        use_quiescence=False,
        use_enhanced_ordering=True,
        threat_weight=1,
    )
    hard_config = SearchConfig.hard()
    baseline = evaluate_fixed_positions(baseline_config)
    medium = evaluate_fixed_positions(medium_config)
    hard = evaluate_fixed_positions(hard_config)
    initial_head_to_head_score = run_initial_head_to_head(hard_config, baseline_config)
    seeded_head_to_head_score = run_seeded_head_to_head(hard_config, baseline_config)
    print_summary(baseline, medium, hard, initial_head_to_head_score, seeded_head_to_head_score)


if __name__ == "__main__":
    main()
