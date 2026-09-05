from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import median
import sys
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jungle.ai import AlphaBetaAI, SearchConfig, SearchResult
from jungle.domain import GameState, Move, Piece, PieceType, Position, Side
from jungle.engine import Game


FIXED_TIME_MS = 80
MATCH_TIME_MS = 5_000
MATCH_NODE_LIMIT = 300
HARD_NODE_MULTIPLIER = 3
MATCH_PLY_CAP = 200
# Kept as a compatibility alias for callers of the original benchmark.
MATCH_TURN_CAP = MATCH_PLY_CAP

MIN_OPENING_SCORE = 0.60
MIN_TACTICAL_POSITIONS = 20
MIN_COLOR_SCORE = 0.50
MIN_DECISIVE_RATE = 0.25
MIN_CONVERSION_SCORE = 0.75
MIN_RESPONSIVENESS_DEPTH = 6
MAX_RESPONSIVENESS_MS = 2_000

THREEFOLD_REPETITION = "threefold_repetition"
PLY_CAP_REACHED = "ply_cap"
NO_LEGAL_MOVES = "no_legal_moves"


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


@dataclass(frozen=True, slots=True)
class GameOutcome:
    scenario_name: str
    suite: str
    stronger_side: Side
    score: float
    plies: int
    termination: str
    winner: Side | None


@dataclass(frozen=True, slots=True)
class MatchMetrics:
    games: int
    wins: int
    draws: int
    losses: int
    blue_games: int
    red_games: int
    score: float
    blue_score: float
    red_score: float
    decisive_rate: float


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
        BenchmarkPosition(
            "red_immediate_den_entry",
            make_state(
                {
                    Position(7, 3).index: Piece(Side.RED, PieceType.CAT),
                    Position(0, 6).index: Piece(Side.BLUE, PieceType.RAT),
                },
                Side.RED,
            ),
            frozenset({Position(8, 3).index}),
        ),
        BenchmarkPosition(
            "red_blocks_den_entry",
            make_state(
                {
                    Position(1, 3).index: Piece(Side.BLUE, PieceType.CAT),
                    Position(1, 2).index: Piece(Side.RED, PieceType.DOG),
                    Position(8, 6).index: Piece(Side.BLUE, PieceType.LION),
                },
                Side.RED,
            ),
            frozenset({Position(1, 3).index}),
        ),
        BenchmarkPosition(
            "lion_jump_capture",
            make_state(
                {
                    Position(3, 0).index: Piece(Side.BLUE, PieceType.LION),
                    Position(3, 3).index: Piece(Side.RED, PieceType.TIGER),
                    Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
                }
            ),
            frozenset({Position(3, 3).index}),
        ),
        BenchmarkPosition(
            "tiger_vertical_jump_capture",
            make_state(
                {
                    Position(3, 0).index: Piece(Side.BLUE, PieceType.TIGER),
                    Position(3, 3).index: Piece(Side.RED, PieceType.LEOPARD),
                    Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
                }
            ),
            frozenset({Position(3, 3).index}),
        ),
        BenchmarkPosition(
            "rat_blocks_lion_jump",
            make_state(
                {
                    Position(3, 0).index: Piece(Side.BLUE, PieceType.LION),
                    Position(3, 1).index: Piece(Side.RED, PieceType.RAT),
                    Position(8, 6).index: Piece(Side.RED, PieceType.CAT),
                }
            ),
            frozenset({Position(2, 0).index, Position(4, 0).index}),
        ),
        BenchmarkPosition(
            "avoid_poisoned_cat_capture",
            make_state(
                {
                    Position(2, 2).index: Piece(Side.BLUE, PieceType.DOG),
                    Position(2, 3).index: Piece(Side.RED, PieceType.CAT),
                    Position(2, 4).index: Piece(Side.RED, PieceType.ELEPHANT),
                    Position(6, 6).index: Piece(Side.BLUE, PieceType.RAT),
                }
            ),
            frozenset({Position(1, 2).index}),
            frozenset({Position(2, 2).index}),
        ),
        BenchmarkPosition(
            "prefer_den_entry_over_material",
            make_state(
                {
                    Position(1, 3).index: Piece(Side.BLUE, PieceType.CAT),
                    Position(2, 0).index: Piece(Side.BLUE, PieceType.RAT),
                    Position(2, 1).index: Piece(Side.RED, PieceType.ELEPHANT),
                    Position(8, 6).index: Piece(Side.RED, PieceType.LION),
                }
            ),
            frozenset({Position(0, 3).index}),
            frozenset({Position(1, 3).index}),
        ),
        BenchmarkPosition(
            "exact_cat_dog_endgame",
            make_state(
                {
                    Position(4, 0).index: Piece(Side.BLUE, PieceType.CAT),
                    Position(4, 6).index: Piece(Side.RED, PieceType.DOG),
                }
            ),
            frozenset({Position(3, 0).index}),
        ),
        BenchmarkPosition(
            "exact_lion_elephant_endgame",
            make_state(
                {
                    Position(6, 0).index: Piece(Side.BLUE, PieceType.LION),
                    Position(2, 6).index: Piece(Side.RED, PieceType.ELEPHANT),
                }
            ),
            frozenset({Position(6, 1).index}),
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
    """Return the committed, deterministic 12-position opening corpus."""
    square = lambda row, col: Position(row, col).index
    return [
        OpeningScenario(
            "flank_rats",
            (
                (square(6, 6), square(5, 6)),
                (square(2, 0), square(3, 0)),
                (square(7, 5), square(6, 5)),
                (square(1, 1), square(2, 1)),
            ),
        ),
        OpeningScenario(
            "center_wolves",
            (
                (square(6, 2), square(6, 3)),
                (square(2, 4), square(2, 3)),
                (square(6, 3), square(5, 3)),
                (square(2, 3), square(3, 3)),
            ),
        ),
        OpeningScenario(
            "heavy_wings",
            (
                (square(6, 0), square(5, 0)),
                (square(2, 6), square(3, 6)),
                (square(7, 1), square(6, 1)),
                (square(1, 5), square(2, 5)),
            ),
        ),
        OpeningScenario(
            "minor_development",
            (
                (square(7, 1), square(6, 1)),
                (square(1, 5), square(2, 5)),
                (square(7, 5), square(6, 5)),
                (square(1, 1), square(2, 1)),
            ),
        ),
        OpeningScenario(
            "center_leopards",
            (
                (square(6, 4), square(6, 3)),
                (square(2, 2), square(2, 3)),
                (square(6, 3), square(5, 3)),
                (square(2, 3), square(3, 3)),
            ),
        ),
        OpeningScenario(
            "open_tiger_files",
            (
                (square(6, 0), square(5, 0)),
                (square(2, 6), square(3, 6)),
                (square(8, 0), square(7, 0)),
                (square(0, 6), square(1, 6)),
            ),
        ),
        OpeningScenario(
            "open_lion_files",
            (
                (square(6, 6), square(5, 6)),
                (square(2, 0), square(3, 0)),
                (square(8, 6), square(7, 6)),
                (square(0, 0), square(1, 0)),
            ),
        ),
        OpeningScenario(
            "split_flanks",
            (
                (square(6, 0), square(5, 0)),
                (square(2, 0), square(3, 0)),
                (square(6, 6), square(5, 6)),
                (square(2, 6), square(3, 6)),
            ),
        ),
        OpeningScenario(
            "river_rat",
            (
                (square(6, 6), square(5, 6)),
                (square(2, 6), square(3, 6)),
                (square(5, 6), square(5, 5)),
                (square(3, 6), square(4, 6)),
            ),
        ),
        OpeningScenario(
            "center_vs_right",
            (
                (square(6, 4), square(6, 3)),
                (square(2, 6), square(3, 6)),
                (square(6, 3), square(5, 3)),
                (square(3, 6), square(4, 6)),
            ),
        ),
        OpeningScenario(
            "left_vs_center",
            (
                (square(6, 0), square(5, 0)),
                (square(2, 2), square(2, 3)),
                (square(5, 0), square(4, 0)),
                (square(2, 3), square(3, 3)),
            ),
        ),
        OpeningScenario(
            "balanced_majors",
            (
                (square(6, 0), square(5, 0)),
                (square(2, 6), square(3, 6)),
                (square(6, 4), square(6, 3)),
                (square(2, 2), square(2, 3)),
            ),
        ),
    ]


def build_opening_state(scenario: OpeningScenario) -> GameState:
    game = Game()
    for ply, (origin, destination) in enumerate(scenario.moves, start=1):
        try:
            game.apply_coordinates(origin, destination)
        except ValueError as exc:
            raise ValueError(
                f"Opening {scenario.name!r} has an illegal move at ply {ply}: "
                f"{origin}->{destination}."
            ) from exc
    if game.state.winner is not None:
        raise ValueError(f"Opening {scenario.name!r} is already terminal.")
    return game.state.copy()


def position_signature(state: GameState) -> tuple:
    """Hashable board/turn identity used only for benchmark adjudication."""
    board = tuple(
        None if piece is None else (piece.side.value, piece.kind.value)
        for piece in state.board
    )
    return board, state.side_to_move.value


def play_game(
    stronger_side: Side,
    stronger_config: SearchConfig,
    baseline_config: SearchConfig,
    initial_state: GameState | None = None,
    *,
    scenario_name: str = "game",
    suite: str = "match",
    node_limit: int = MATCH_NODE_LIMIT,
    stronger_node_multiplier: int = HARD_NODE_MULTIPLIER,
    ply_cap: int = MATCH_PLY_CAP,
    time_limit_ms: int = MATCH_TIME_MS,
) -> GameOutcome:
    if node_limit <= 0:
        raise ValueError("node_limit must be positive")
    if stronger_node_multiplier <= 0:
        raise ValueError("stronger_node_multiplier must be positive")
    if ply_cap <= 0:
        raise ValueError("ply_cap must be positive")

    game = Game(initial_state)
    position_counts: Counter[tuple] = Counter({position_signature(game.state): 1})
    stronger_ai = AlphaBetaAI(
        time_limit_ms,
        stronger_config,
        node_limit=node_limit * stronger_node_multiplier,
    )
    baseline_ai = AlphaBetaAI(time_limit_ms, baseline_config, node_limit=node_limit)
    winner = game.state.winner
    termination = game.state.result.value if winner is not None else PLY_CAP_REACHED
    plies = 0

    while winner is None and plies < ply_cap:
        moves = game.list_moves()
        if not moves:
            winner = game.state.side_to_move.opponent
            termination = NO_LEGAL_MOVES
            break

        ai = stronger_ai if game.state.side_to_move is stronger_side else baseline_ai
        result = ai.choose_move(game.state)
        if result.move is None:
            raise RuntimeError("AI returned no move for an ongoing game.")
        if result.move not in moves:
            raise RuntimeError(
                f"AI returned illegal move {result.move.origin}->{result.move.destination}."
            )

        game.apply_move(result.move)
        plies += 1
        winner = game.state.winner
        if winner is not None:
            termination = game.state.result.value
            break

        signature = position_signature(game.state)
        position_counts[signature] += 1
        if position_counts[signature] >= 3:
            termination = THREEFOLD_REPETITION
            break

    score = 0.5
    if winner is stronger_side:
        score = 1.0
    elif winner is stronger_side.opponent:
        score = 0.0
    return GameOutcome(
        scenario_name=scenario_name,
        suite=suite,
        stronger_side=stronger_side,
        score=score,
        plies=plies,
        termination=termination,
        winner=winner,
    )


def score_game(
    stronger_side: Side,
    stronger_config: SearchConfig,
    baseline_config: SearchConfig,
    initial_state: GameState | None = None,
    *,
    node_limit: int = MATCH_NODE_LIMIT,
    turn_cap: int = MATCH_PLY_CAP,
) -> float:
    """Compatibility wrapper returning only the stronger engine's score."""
    return play_game(
        stronger_side,
        stronger_config,
        baseline_config,
        initial_state,
        node_limit=node_limit,
        ply_cap=turn_cap,
    ).score


def calculate_match_metrics(outcomes: Sequence[GameOutcome]) -> MatchMetrics:
    games = len(outcomes)
    if games == 0:
        return MatchMetrics(0, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0)
    if any(outcome.score not in {0.0, 0.5, 1.0} for outcome in outcomes):
        raise ValueError("Game scores must be 0.0, 0.5, or 1.0.")

    wins = sum(outcome.score == 1.0 for outcome in outcomes)
    draws = sum(outcome.score == 0.5 for outcome in outcomes)
    losses = games - wins - draws
    blue = [outcome.score for outcome in outcomes if outcome.stronger_side is Side.BLUE]
    red = [outcome.score for outcome in outcomes if outcome.stronger_side is Side.RED]
    return MatchMetrics(
        games=games,
        wins=wins,
        draws=draws,
        losses=losses,
        blue_games=len(blue),
        red_games=len(red),
        score=sum(outcome.score for outcome in outcomes) / games,
        blue_score=sum(blue) / len(blue) if blue else 0.0,
        red_score=sum(red) / len(red) if red else 0.0,
        decisive_rate=(wins + losses) / games,
    )


def combined_match_score(opening_scores: list[float], conversion_scores: list[float]) -> float:
    """Legacy aggregate retained for diagnostics, not for the strength gate."""
    scores = opening_scores + conversion_scores
    return sum(scores) / len(scores) if scores else 0.0


def _print_metrics(label: str, metrics: MatchMetrics) -> None:
    print(
        f"  {label}: games={metrics.games} score={metrics.score:.3f} "
        f"blue={metrics.blue_score:.3f} red={metrics.red_score:.3f} "
        f"wins/draws/losses={metrics.wins}/{metrics.draws}/{metrics.losses} "
        f"decisive={metrics.decisive_rate:.3f}"
    )


def run_paired_openings(
    stronger_config: SearchConfig,
    baseline_config: SearchConfig,
    *,
    node_limit: int = MATCH_NODE_LIMIT,
    ply_cap: int = MATCH_PLY_CAP,
) -> list[GameOutcome]:
    outcomes: list[GameOutcome] = []
    print(
        "\npaired_openings "
        f"stronger={stronger_config.label} baseline={baseline_config.label} "
        f"baseline_nodes={node_limit} hard_nodes={node_limit * HARD_NODE_MULTIPLIER} "
        f"ply_cap={ply_cap}"
    )
    for scenario in opening_scenarios():
        state = build_opening_state(scenario)
        for stronger_side in (Side.BLUE, Side.RED):
            outcome = play_game(
                stronger_side,
                stronger_config,
                baseline_config,
                state,
                scenario_name=scenario.name,
                suite="opening",
                node_limit=node_limit,
                ply_cap=ply_cap,
            )
            outcomes.append(outcome)
            print(
                f"  {scenario.name}: score={outcome.score:.2f} "
                f"stronger_side={stronger_side.value} plies={outcome.plies} "
                f"termination={outcome.termination}"
            )
    _print_metrics("paired_opening", calculate_match_metrics(outcomes))
    return outcomes


def run_conversion_games(
    stronger_config: SearchConfig,
    baseline_config: SearchConfig,
    *,
    node_limit: int = MATCH_NODE_LIMIT,
    ply_cap: int = MATCH_PLY_CAP,
) -> list[GameOutcome]:
    outcomes: list[GameOutcome] = []
    print(
        "\nconversion_games "
        f"stronger={stronger_config.label} baseline={baseline_config.label} "
        f"baseline_nodes={node_limit} hard_nodes={node_limit * HARD_NODE_MULTIPLIER} "
        f"ply_cap={ply_cap}"
    )
    for scenario in head_to_head_scenarios():
        outcome = play_game(
            scenario.stronger_side,
            stronger_config,
            baseline_config,
            scenario.state,
            scenario_name=scenario.name,
            suite="conversion",
            node_limit=node_limit,
            ply_cap=ply_cap,
        )
        outcomes.append(outcome)
        print(
            f"  {scenario.name}: score={outcome.score:.2f} "
            f"stronger_side={scenario.stronger_side.value} plies={outcome.plies} "
            f"termination={outcome.termination}"
        )
    _print_metrics("conversion", calculate_match_metrics(outcomes))
    return outcomes


def run_responsiveness_check(config: SearchConfig) -> SearchResult:
    result = AlphaBetaAI(1_800, config).choose_move(Game().state)
    print(
        "\nresponsiveness "
        f"config={config.label} depth={result.depth} nodes={result.nodes} "
        f"elapsed_ms={result.elapsed_ms:.0f}"
    )
    return result


def validate_benchmark(
    hard: ConfigStats,
    opening_outcomes: Sequence[GameOutcome],
    conversion_outcomes: Sequence[GameOutcome],
    responsive: SearchResult,
) -> None:
    if hard.passed != hard.total:
        raise SystemExit(f"hard config failed fixed positions: {hard.passed}/{hard.total}")
    if hard.total < MIN_TACTICAL_POSITIONS:
        raise SystemExit(
            f"fixed-position corpus too small: {hard.total} < {MIN_TACTICAL_POSITIONS}"
        )

    opening = calculate_match_metrics(opening_outcomes)
    if opening.games == 0:
        raise SystemExit("paired opening corpus produced no games")
    if opening.blue_games == 0 or opening.blue_games != opening.red_games:
        raise SystemExit(
            "paired opening corpus must contain the same non-zero number of games for each color"
        )
    if opening.score < MIN_OPENING_SCORE:
        raise SystemExit(
            f"paired opening overall score too low: {opening.score:.3f} < {MIN_OPENING_SCORE:.2f}"
        )
    if opening.blue_score < MIN_COLOR_SCORE:
        raise SystemExit(
            f"paired opening blue score too low: {opening.blue_score:.3f} < {MIN_COLOR_SCORE:.2f}"
        )
    if opening.red_score < MIN_COLOR_SCORE:
        raise SystemExit(
            f"paired opening red score too low: {opening.red_score:.3f} < {MIN_COLOR_SCORE:.2f}"
        )
    if opening.decisive_rate < MIN_DECISIVE_RATE:
        raise SystemExit(
            "paired opening decisive rate too low: "
            f"{opening.decisive_rate:.3f} < {MIN_DECISIVE_RATE:.2f}"
        )

    conversion = calculate_match_metrics(conversion_outcomes)
    if conversion.games == 0 or conversion.score < MIN_CONVERSION_SCORE:
        raise SystemExit(
            f"conversion score too low: {conversion.score:.3f} < {MIN_CONVERSION_SCORE:.2f}"
        )
    if responsive.move not in Game().list_moves():
        raise SystemExit("hard responsiveness returned an illegal move")
    if responsive.depth < MIN_RESPONSIVENESS_DEPTH:
        raise SystemExit(
            f"hard responsiveness depth too low: {responsive.depth} < {MIN_RESPONSIVENESS_DEPTH}"
        )
    if responsive.elapsed_ms > MAX_RESPONSIVENESS_MS:
        raise SystemExit(
            f"hard responsiveness exceeded {MAX_RESPONSIVENESS_MS} ms: "
            f"{responsive.elapsed_ms:.0f}"
        )


def print_summary(
    baseline: ConfigStats,
    medium: ConfigStats,
    hard: ConfigStats,
    opening_outcomes: Sequence[GameOutcome],
    conversion_outcomes: Sequence[GameOutcome],
    responsive: SearchResult,
) -> None:
    print("\nsummary")
    for stats in (baseline, medium, hard):
        avg_depth = sum(stats.depths) / len(stats.depths) if stats.depths else 0.0
        avg_nodes = sum(stats.nodes) / len(stats.nodes) if stats.nodes else 0.0
        print(
            f"  {stats.label}: passed={stats.passed}/{stats.total} "
            f"median_ms={stats.median_elapsed:.0f} worst_ms={stats.worst_elapsed:.0f} "
            f"avg_depth={avg_depth:.1f} avg_nodes={avg_nodes:.0f}"
        )
    print(f"  hard_fixed_position_delta={hard.passed - baseline.passed}")
    _print_metrics("hard_paired_opening", calculate_match_metrics(opening_outcomes))
    _print_metrics("hard_conversion", calculate_match_metrics(conversion_outcomes))
    print(f"  hard_response_depth={responsive.depth}")
    print(f"  hard_response_elapsed_ms={responsive.elapsed_ms:.0f}")


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the deterministic Jungle AI strength gate.")
    parser.add_argument(
        "--node-limit",
        type=_positive_int,
        default=MATCH_NODE_LIMIT,
        help=(
            f"baseline search nodes per move (default: {MATCH_NODE_LIMIT}); "
            f"Hard receives a conservative {HARD_NODE_MULTIPLIER}x allocation to model its "
            "measured throughput advantage"
        ),
    )
    parser.add_argument(
        "--ply-cap",
        type=_positive_int,
        default=MATCH_PLY_CAP,
        help=f"maximum plies per match game (default: {MATCH_PLY_CAP})",
    )
    args = parser.parse_args(argv)

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
    opening_outcomes = run_paired_openings(
        hard_config,
        baseline_config,
        node_limit=args.node_limit,
        ply_cap=args.ply_cap,
    )
    conversion_outcomes = run_conversion_games(
        hard_config,
        baseline_config,
        node_limit=args.node_limit,
        ply_cap=args.ply_cap,
    )
    responsive = run_responsiveness_check(hard_config)
    print_summary(
        baseline,
        medium,
        hard,
        opening_outcomes,
        conversion_outcomes,
        responsive,
    )
    validate_benchmark(hard, opening_outcomes, conversion_outcomes, responsive)


if __name__ == "__main__":
    main()
