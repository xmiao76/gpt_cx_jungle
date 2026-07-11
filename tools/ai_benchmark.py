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
MATCH_TIME_MS = 5_000
MATCH_NODE_LIMIT = 300
MATCH_TURN_CAP = 60


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


@dataclass(frozen=True, slots=True)
class OpeningScenario:
    name: str
    moves: tuple[tuple[int, int], ...]


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
            "rat_wins_den_race_from_right",
            make_state(
                {
                    Position(2, 2).index: Piece(Side.BLUE, PieceType.RAT),
                    Position(2, 1).index: Piece(Side.RED, PieceType.ELEPHANT),
                    Position(8, 6).index: Piece(Side.RED, PieceType.LION),
                }
            ),
            frozenset({Position(1, 2).index}),
        ),
        BenchmarkPosition(
            "rat_wins_den_race_from_above",
            make_state(
                {
                    Position(1, 1).index: Piece(Side.BLUE, PieceType.RAT),
                    Position(2, 1).index: Piece(Side.RED, PieceType.ELEPHANT),
                    Position(8, 6).index: Piece(Side.RED, PieceType.LION),
                }
            ),
            frozenset({Position(1, 2).index}),
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


def opening_scenarios() -> list[OpeningScenario]:
    return [
        OpeningScenario(
            "flank_rats",
            (
                (Position(6, 6).index, Position(5, 6).index),
                (Position(2, 0).index, Position(3, 0).index),
            ),
        ),
        OpeningScenario(
            "center_wolves",
            (
                (Position(6, 2).index, Position(6, 3).index),
                (Position(2, 4).index, Position(2, 3).index),
            ),
        ),
        OpeningScenario(
            "heavy_wings",
            (
                (Position(6, 0).index, Position(5, 0).index),
                (Position(2, 6).index, Position(3, 6).index),
            ),
        ),
        OpeningScenario(
            "minor_development",
            (
                (Position(7, 1).index, Position(6, 1).index),
                (Position(1, 5).index, Position(2, 5).index),
            ),
        ),
    ]


def build_opening_state(scenario: OpeningScenario) -> GameState:
    game = Game()
    for origin, destination in scenario.moves:
        game.apply_coordinates(origin, destination)
    return game.state.copy()


def combined_match_score(opening_scores: list[float], conversion_scores: list[float]) -> float:
    scores = opening_scores + conversion_scores
    return sum(scores) / len(scores) if scores else 0.0


def score_game(
    stronger_side: Side,
    stronger_config: SearchConfig,
    baseline_config: SearchConfig,
    initial_state: GameState | None = None,
    *,
    node_limit: int = MATCH_NODE_LIMIT,
    turn_cap: int = MATCH_TURN_CAP,
) -> float:
    game = Game(initial_state)
    turns = 0
    while game.state.winner is None and turns < turn_cap:
        moves = game.list_moves()
        if not moves:
            break
        if game.state.side_to_move is stronger_side:
            config = stronger_config
        else:
            config = baseline_config
        result = AlphaBetaAI(MATCH_TIME_MS, config, node_limit=node_limit).choose_move(game.state)
        if result.move is None:
            raise RuntimeError("AI returned no move for an ongoing game.")
        if result.move not in moves:
            raise RuntimeError(f"AI returned illegal move {result.move.origin}->{result.move.destination}.")
        game.apply_move(result.move)
        turns += 1
    if game.state.winner is stronger_side:
        return 1.0
    if game.state.winner is stronger_side.opponent:
        return 0.0
    return 0.5


def validate_benchmark(
    hard: ConfigStats,
    opening_scores: list[float],
    conversion_scores: list[float],
    responsive: SearchResult,
) -> None:
    if hard.passed != hard.total:
        raise SystemExit(f"hard config failed fixed positions: {hard.passed}/{hard.total}")
    opening_score = sum(opening_scores) / len(opening_scores) if opening_scores else 0.0
    if opening_score < 0.50:
        raise SystemExit(f"paired opening score too low: {opening_score:.2f}")
    combined = combined_match_score(opening_scores, conversion_scores)
    if combined < 0.60:
        raise SystemExit(f"combined match score too low: {combined:.2f}")
    conversion_score = sum(conversion_scores) / len(conversion_scores) if conversion_scores else 0.0
    if conversion_score < 0.75:
        raise SystemExit(f"conversion score too low: {conversion_score:.2f}")
    if responsive.move not in Game().list_moves():
        raise SystemExit("hard responsiveness returned an illegal move")
    if responsive.depth < 4:
        raise SystemExit(f"hard responsiveness depth too low: {responsive.depth}")
    if responsive.elapsed_ms > 2_000:
        raise SystemExit(f"hard responsiveness exceeded 2000 ms: {responsive.elapsed_ms:.0f}")


def run_paired_openings(stronger_config: SearchConfig, baseline_config: SearchConfig) -> list[float]:
    scores: list[float] = []
    print(
        "\npaired_openings "
        f"stronger={stronger_config.label} baseline={baseline_config.label} "
        f"node_limit={MATCH_NODE_LIMIT} turn_cap={MATCH_TURN_CAP}"
    )
    for scenario in opening_scenarios():
        state = build_opening_state(scenario)
        for stronger_side in (Side.BLUE, Side.RED):
            score = score_game(stronger_side, stronger_config, baseline_config, state)
            scores.append(score)
            print(f"  {scenario.name}: score={score:.2f} stronger_side={stronger_side.value}")
    total = sum(scores) / len(scores)
    print(f"  paired_opening_score={total:.2f}")
    return scores


def run_conversion_games(stronger_config: SearchConfig, baseline_config: SearchConfig) -> list[float]:
    scenarios = head_to_head_scenarios()
    scores: list[float] = []
    print(
        "\nconversion_games "
        f"stronger={stronger_config.label} baseline={baseline_config.label} "
        f"node_limit={MATCH_NODE_LIMIT} turn_cap={MATCH_TURN_CAP}"
    )
    for scenario in scenarios:
        score = score_game(scenario.stronger_side, stronger_config, baseline_config, scenario.state)
        scores.append(score)
        print(f"  {scenario.name}: score={score:.2f} stronger_side={scenario.stronger_side.value}")
    total = sum(scores) / len(scores)
    print(f"  conversion_score={total:.2f}")
    return scores


def run_responsiveness_check(config: SearchConfig) -> SearchResult:
    result = AlphaBetaAI(1_800, config).choose_move(Game().state)
    print(
        "\nresponsiveness "
        f"config={config.label} depth={result.depth} nodes={result.nodes} elapsed_ms={result.elapsed_ms:.0f}"
    )
    return result


def print_summary(
    baseline: ConfigStats,
    medium: ConfigStats,
    hard: ConfigStats,
    opening_scores: list[float],
    conversion_scores: list[float],
    responsive: SearchResult,
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
    opening_score = sum(opening_scores) / len(opening_scores)
    conversion_score = sum(conversion_scores) / len(conversion_scores)
    print(f"  hard_paired_opening_score={opening_score:.2f}")
    print(f"  hard_conversion_score={conversion_score:.2f}")
    print(f"  hard_combined_match_score={combined_match_score(opening_scores, conversion_scores):.2f}")
    print(f"  hard_response_depth={responsive.depth}")
    print(f"  hard_response_elapsed_ms={responsive.elapsed_ms:.0f}")


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
    opening_scores = run_paired_openings(hard_config, baseline_config)
    conversion_scores = run_conversion_games(hard_config, baseline_config)
    responsive = run_responsiveness_check(hard_config)
    print_summary(baseline, medium, hard, opening_scores, conversion_scores, responsive)
    validate_benchmark(hard, opening_scores, conversion_scores, responsive)


if __name__ == "__main__":
    main()
