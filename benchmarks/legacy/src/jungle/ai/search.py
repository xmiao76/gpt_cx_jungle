from __future__ import annotations

import math
import time
from collections import Counter
from dataclasses import dataclass
from enum import Enum

from jungle.domain import (
    BLUE_DEN,
    BLUE_TRAPS,
    RED_DEN,
    RED_TRAPS,
    GameState,
    Move,
    Position,
    Side,
)
from jungle.rules import legal_moves

from .evaluation import EvaluationOptions, PIECE_VALUES, TERMINAL_SCORE, evaluate_state
from .position import apply_search_move, position_key, recent_position_counts


MAX_DEPTH = 8
EXACT = "exact"
LOWER = "lower"
UPPER = "upper"
MATE_SCORE_THRESHOLD = TERMINAL_SCORE - 1_000


class _SearchAborted(Exception):
    pass


class SearchProfile(Enum):
    FAST = "fast"
    FULL = "full"


@dataclass(slots=True)
class SearchResult:
    move: Move | None
    score: int
    depth: int
    nodes: int
    elapsed_ms: float
    principal_variation: tuple[Move, ...] = ()
    nodes_per_second: int = 0
    tt_hits: int = 0
    tablebase_hits: int = 0


@dataclass(frozen=True, slots=True)
class SearchConfig:
    label: str = "baseline"
    max_depth: int = MAX_DEPTH
    use_threat_score: bool = False
    use_quiescence: bool = False
    use_enhanced_ordering: bool = False
    use_killer_moves: bool = False
    use_history_heuristic: bool = False
    use_static_capture_ordering: bool = False
    use_den_safety: bool = False
    force_full_evaluation: bool = False
    use_aspiration_windows: bool = False
    use_late_move_reductions: bool = False
    use_repetition_penalty: bool = False
    use_den_race_score: bool = False
    aspiration_window: int = 650
    lmr_min_depth: int = 3
    lmr_move_threshold: int = 4
    repetition_penalty: int = 320
    quiescence_max_depth: int = 0
    quiescence_candidate_limit: int = 0
    threat_weight: int = 0
    use_principal_variation_search: bool = False
    use_cycle_detection: bool = False
    use_compact_core: bool = False
    transposition_table_size: int = 262_144

    @staticmethod
    def baseline() -> "SearchConfig":
        return SearchConfig()

    @staticmethod
    def candidate() -> "SearchConfig":
        return SearchConfig.hard()

    @staticmethod
    def hard() -> "SearchConfig":
        return SearchConfig(
            label="hard",
            max_depth=10,
            use_threat_score=True,
            use_quiescence=True,
            use_enhanced_ordering=True,
            use_killer_moves=True,
            use_history_heuristic=True,
            use_static_capture_ordering=True,
            use_den_safety=True,
            force_full_evaluation=True,
            use_aspiration_windows=True,
            use_late_move_reductions=True,
            use_repetition_penalty=True,
            use_den_race_score=True,
            quiescence_max_depth=2,
            quiescence_candidate_limit=6,
            threat_weight=1,
            use_principal_variation_search=True,
            use_cycle_detection=True,
            use_compact_core=True,
            aspiration_window=160,
        )


@dataclass(slots=True)
class TTEntry:
    depth: int
    score: int
    flag: str
    best_move: tuple[int, int] | None


class AlphaBetaAI:
    def __init__(
        self,
        time_limit_ms: int = 1000,
        config: SearchConfig | None = None,
        *,
        node_limit: int | None = None,
    ) -> None:
        self.time_limit_ms = time_limit_ms
        self.config = SearchConfig.baseline() if config is None else config
        self.node_limit = node_limit
        self.profile = SearchProfile.FAST if time_limit_ms <= 350 else SearchProfile.FULL
        self.deadline = 0.0
        self.nodes = 0
        self.tt: dict[tuple, TTEntry] = {}
        self.killer_moves: dict[int, list[tuple[int, int]]] = {}
        self.history_scores: dict[tuple[int, int], int] = {}
        self.path_counts: Counter[tuple] = Counter()

    def choose_move(self, state: GameState) -> SearchResult:
        if self.config.use_compact_core:
            from .fast_search import CompactSearch

            return CompactSearch(self.time_limit_ms, self.config, self.node_limit).choose_move(state)
        self.deadline = time.perf_counter() + self.time_limit_ms / 1000.0
        self.nodes = 0
        self.tt.clear()
        self.killer_moves.clear()
        self.history_scores.clear()
        self.path_counts = recent_position_counts(state) if self.config.use_cycle_detection else Counter()
        best_move: Move | None = None
        best_score = -math.inf
        completed_depth = 0
        start = time.perf_counter()

        root_moves = legal_moves(state)
        if not root_moves:
            score = self.terminal_score(state, state.side_to_move, 0) if state.winner is not None else -TERMINAL_SCORE
            elapsed_ms = (time.perf_counter() - start) * 1000
            return SearchResult(None, score, 0, self.nodes, elapsed_ms)

        tactical = self.find_forced_tactical_move(state)
        if tactical is not None:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return SearchResult(
                tactical,
                self.evaluate(self.apply(state, tactical), state.side_to_move),
                1,
                self.nodes,
                elapsed_ms,
                principal_variation=(tactical,),
            )
        for depth in range(1, self.config.max_depth + 1):
            try:
                self._check_limits()
                if self.config.use_aspiration_windows and completed_depth > 0 and best_score not in {-math.inf, math.inf}:
                    window = self.config.aspiration_window
                    alpha = best_score - window
                    beta = best_score + window
                    score, move = self._search_root(state, depth, best_move, alpha, beta)
                    if score <= alpha or score >= beta:
                        score, move = self._search_root(state, depth, best_move)
                else:
                    score, move = self._search_root(state, depth, best_move)
            except _SearchAborted:
                break
            if move is not None:
                best_move = move
                best_score = score
                completed_depth = depth
        elapsed_ms = (time.perf_counter() - start) * 1000
        if best_move is None:
            moves = legal_moves(state)
            ordered = self.order_moves(state, moves) if moves else []
            best_move = ordered[0] if ordered else None
            best_score = self.evaluate(state, state.side_to_move)
        nps = int(self.nodes * 1_000 / elapsed_ms) if elapsed_ms > 0 else 0
        pv = () if best_move is None else (best_move,)
        return SearchResult(
            best_move,
            int(best_score),
            completed_depth,
            self.nodes,
            elapsed_ms,
            principal_variation=pv,
            nodes_per_second=nps,
        )

    def find_forced_tactical_move(self, state: GameState) -> Move | None:
        own_win = self.find_immediate_win(state, state.side_to_move)
        if own_win is not None:
            return own_win

        opponent_win = self.find_immediate_win(state, state.side_to_move.opponent)
        if opponent_win is None:
            return None

        candidates: list[Move] = []
        for move in legal_moves(state):
            child = self.apply(state, move)
            if child.winner is state.side_to_move:
                return move
            if self.find_immediate_win(child, state.side_to_move.opponent) is None:
                candidates.append(move)
        if not candidates:
            return None
        return self.order_moves(state, candidates, preferred_move=None)[0]

    def find_immediate_win(self, state: GameState, side: Side) -> Move | None:
        turn_state = self.with_side_to_move(state, side)
        for move in legal_moves(turn_state):
            child = self.apply(turn_state, move)
            if child.winner is side:
                return move
        return None

    def _search_root(
        self,
        state: GameState,
        depth: int,
        preferred_move: Move | None,
        alpha: float = -math.inf,
        beta: float = math.inf,
    ) -> tuple[int, Move | None]:
        best_score = -math.inf
        best_move: Move | None = None
        root_moves = legal_moves(state)
        static_order = self.order_moves(state, root_moves, tactical=True, ply=0)
        tie_rank = {(move.origin, move.destination): rank for rank, move in enumerate(static_order)}
        best_tie_rank = math.inf
        moves = self.order_moves(state, root_moves, preferred_move=preferred_move, tactical=True, ply=0)
        for move_index, move in enumerate(moves):
            self._check_limits()
            child = self.apply(state, move)
            score = self._search_child(child, depth - 1, alpha, beta, 1, move_index > 0)
            unsafe_penalty = 0
            if self.config.use_den_safety and self.is_unsafe_non_capture_jump(state, move, child):
                unsafe_penalty = PIECE_VALUES[move.piece.kind] * 48
                score -= unsafe_penalty
            move_tie_rank = tie_rank[(move.origin, move.destination)]
            if score == best_score and move_tie_rank < best_tie_rank:
                score = self._search_child(child, depth - 1, -math.inf, math.inf, 1, False) - unsafe_penalty
            if score > best_score or (score == best_score and move_tie_rank < best_tie_rank):
                best_score = score
                best_move = move
                best_tie_rank = move_tie_rank
            alpha = max(alpha, score)
            if alpha >= beta:
                self.record_cutoff(move, depth, 0)
                break
        return int(best_score), best_move

    def _alphabeta(self, state: GameState, depth: int, alpha: float, beta: float, ply: int = 0) -> int:
        self._visit_node()

        key = self._hash_state(state)
        alpha_original = alpha
        entry = self.tt.get(key)
        if entry is not None and entry.depth >= depth:
            entry_score = self.score_from_tt(entry.score, ply)
            if entry.flag == EXACT:
                return entry_score
            if entry.flag == LOWER:
                alpha = max(alpha, entry_score)
            elif entry.flag == UPPER:
                beta = min(beta, entry_score)
            if alpha >= beta:
                return entry_score

        if state.winner is not None:
            return self.terminal_score(state, state.side_to_move, ply)
        if depth <= 0:
            if self.config.use_quiescence:
                return self._quiescence(state, alpha, beta, 0, ply)
            score = self.evaluate(state, state.side_to_move)
            self.tt[key] = TTEntry(depth, self.score_to_tt(score, ply), EXACT, None)
            return score

        moves = legal_moves(state)
        if not moves:
            return -TERMINAL_SCORE + ply

        value = -math.inf
        best_move_key: tuple[int, int] | None = None
        preferred = self.move_from_key(moves, entry.best_move if entry is not None else None)
        for move_index, move in enumerate(self.order_moves(state, moves, preferred_move=preferred, ply=ply)):
            child = self.apply(state, move)
            if self.should_reduce_late_move(state, move, move_index, depth):
                reduced_depth = max(0, depth - 2)
                score = self._negamax_child(child, reduced_depth, alpha, alpha + 1, ply + 1)
                if score > alpha:
                    score = self._negamax_child(child, depth - 1, alpha, beta, ply + 1)
            else:
                score = self._search_child(child, depth - 1, alpha, beta, ply + 1, move_index > 0)
            if score > value:
                value = score
                best_move_key = (move.origin, move.destination)
            alpha = max(alpha, score)
            if alpha >= beta:
                self.record_cutoff(move, depth, ply)
                break

        flag = EXACT
        if value <= alpha_original:
            flag = UPPER
        elif value >= beta:
            flag = LOWER
        entry_score = int(value)
        self.tt[key] = TTEntry(depth, self.score_to_tt(entry_score, ply), flag, best_move_key)
        return entry_score

    def _search_child(
        self,
        child: GameState,
        depth: int,
        alpha: float,
        beta: float,
        ply: int,
        later_move: bool,
    ) -> int:
        if self.config.use_principal_variation_search and later_move and math.isfinite(alpha):
            score = self._negamax_child(child, depth, alpha, alpha + 1, ply)
            if alpha < score < beta:
                score = self._negamax_child(child, depth, alpha, beta, ply)
            return score
        return self._negamax_child(child, depth, alpha, beta, ply)

    def _negamax_child(
        self,
        child: GameState,
        depth: int,
        alpha: float,
        beta: float,
        ply: int,
    ) -> int:
        key = position_key(child)
        if self.config.use_cycle_detection and self.path_counts[key] > 0:
            return -self.config.repetition_penalty * 8
        if self.config.use_cycle_detection:
            self.path_counts[key] += 1
        try:
            return -self._alphabeta(child, depth, -beta, -alpha, ply)
        finally:
            if self.config.use_cycle_detection:
                self.path_counts[key] -= 1
                if self.path_counts[key] == 0:
                    del self.path_counts[key]

    def _quiescence(self, state: GameState, alpha: float, beta: float, extension_depth: int, ply: int) -> int:
        self._visit_node()

        if state.winner is not None:
            return self.terminal_score(state, state.side_to_move, ply)
        moves = legal_moves(state)
        if not moves:
            return -TERMINAL_SCORE + ply

        under_den_threat = self.has_immediate_den_threat(state)
        stand_pat = self.evaluate(state, state.side_to_move)
        if not under_den_threat:
            if stand_pat >= beta:
                return int(beta)
            alpha = max(alpha, stand_pat)
        if extension_depth >= self.config.quiescence_max_depth or state.result_reason:
            return int(stand_pat if under_den_threat else alpha)

        candidates = self.forcing_moves(state, moves, under_den_threat=under_den_threat)
        if not candidates:
            if under_den_threat:
                return -TERMINAL_SCORE + ply
            return int(alpha)

        for move in self.order_moves(state, candidates, tactical=True)[: self.config.quiescence_candidate_limit]:
            self._check_limits()
            score = -self._quiescence(self.apply(state, move), -beta, -alpha, extension_depth + 1, ply + 1)
            if score >= beta:
                return int(beta)
            alpha = max(alpha, score)
        return int(alpha)

    def forcing_moves(
        self,
        state: GameState,
        moves: list[Move] | None = None,
        *,
        under_den_threat: bool | None = None,
    ) -> list[Move]:
        target_den = RED_DEN if state.side_to_move is Side.BLUE else BLUE_DEN
        own_den = BLUE_DEN if state.side_to_move is Side.BLUE else RED_DEN
        moves = legal_moves(state) if moves is None else moves
        forcing = [
            move
            for move in moves
            if move.captured is not None or move.destination == target_den or move.destination in self.enemy_traps_for(state.side_to_move)
        ]

        if under_den_threat is None:
            under_den_threat = self.has_immediate_den_threat(state)
        if not under_den_threat:
            return forcing

        defenses: list[Move] = []
        for move in moves:
            child = self.apply(state, move)
            if child.winner is state.side_to_move:
                defenses.append(move)
                continue
            reply_state = self.with_side_to_move(child, state.side_to_move.opponent)
            if not any(reply.destination == own_den for reply in legal_moves(reply_state)):
                defenses.append(move)
        return defenses

    def has_immediate_den_threat(self, state: GameState) -> bool:
        own_den = BLUE_DEN if state.side_to_move is Side.BLUE else RED_DEN
        opponent_state = self.with_side_to_move(state, state.side_to_move.opponent)
        return any(move.destination == own_den for move in legal_moves(opponent_state))

    def order_moves(
        self,
        state: GameState,
        moves: list[Move],
        preferred_move: Move | None = None,
        tactical: bool = False,
        ply: int = 0,
    ) -> list[Move]:
        target_den = RED_DEN if state.side_to_move is Side.BLUE else BLUE_DEN

        def move_score(move: Move) -> int:
            score = 0
            if preferred_move is not None and move.origin == preferred_move.origin and move.destination == preferred_move.destination:
                score += 1_000_000
            if move.destination == target_den:
                score += 900_000
            if move.captured is not None:
                score += 30_000 + PIECE_VALUES[move.captured.kind] * 20 - PIECE_VALUES[move.piece.kind]
                if self.config.use_static_capture_ordering:
                    score += (PIECE_VALUES[move.captured.kind] - PIECE_VALUES[move.piece.kind]) * 4
            if move.is_jump:
                score += 1_500
            distance = Position.from_index(move.destination).manhattan_distance(Position.from_index(target_den))
            score += (18 - distance) * 120
            if move.destination in self.enemy_traps_for(state.side_to_move):
                score += 2_200
            if self.config.use_enhanced_ordering:
                if move.destination in self.own_traps_for(state.side_to_move):
                    score += 400
            move_key = (move.origin, move.destination)
            if self.config.use_killer_moves and move.captured is None and move_key in self.killer_moves.get(ply, []):
                score += 16_000
            if self.config.use_history_heuristic and move.captured is None:
                score += self.history_scores.get(move_key, 0)
            if self.config.use_repetition_penalty and move.captured is None and self.is_recent_reversal(state, move):
                score -= self.config.repetition_penalty * 6
            return score

        return sorted(moves, key=move_score, reverse=True)

    def evaluate(self, state: GameState, perspective: Side) -> int:
        full = self.profile is SearchProfile.FULL or self.config.force_full_evaluation
        options = EvaluationOptions(
            full=full,
            threat_weight=self.config.threat_weight if self.config.use_threat_score else 0,
            use_den_safety=self.config.use_den_safety,
            use_den_race=self.config.use_den_race_score,
            repetition_penalty=self.config.repetition_penalty if self.config.use_repetition_penalty else 0,
        )
        return evaluate_state(state, perspective, options)

    def terminal_score(self, state: GameState, perspective: Side, ply: int) -> int:
        if state.winner is perspective:
            return TERMINAL_SCORE - ply
        if state.winner is perspective.opponent:
            return -TERMINAL_SCORE + ply
        return self.evaluate(state, perspective)

    def score_to_tt(self, score: int, ply: int) -> int:
        if score >= MATE_SCORE_THRESHOLD:
            return score + ply
        if score <= -MATE_SCORE_THRESHOLD:
            return score - ply
        return score

    def score_from_tt(self, score: int, ply: int) -> int:
        if score >= MATE_SCORE_THRESHOLD:
            return score - ply
        if score <= -MATE_SCORE_THRESHOLD:
            return score + ply
        return score

    def is_recent_reversal(self, state: GameState, move: Move) -> bool:
        for previous in reversed(state.move_history):
            if previous.piece.side is move.piece.side:
                return previous.origin == move.destination and previous.destination == move.origin
        return False

    def is_unsafe_non_capture_jump(self, state: GameState, move: Move, child: GameState | None = None) -> bool:
        if not move.is_jump or move.captured is not None:
            return False
        child_state = self.apply(state, move) if child is None else child
        return self.is_square_attacked(child_state, move.destination, state.side_to_move.opponent)

    def record_cutoff(self, move: Move, depth: int, ply: int) -> None:
        if move.captured is not None:
            return
        move_key = (move.origin, move.destination)
        if self.config.use_killer_moves:
            killers = self.killer_moves.setdefault(ply, [])
            if move_key not in killers:
                killers.insert(0, move_key)
                del killers[2:]
        if self.config.use_history_heuristic:
            self.history_scores[move_key] = self.history_scores.get(move_key, 0) + depth * depth

    def should_reduce_late_move(self, state: GameState, move: Move, move_index: int, depth: int) -> bool:
        if not self.config.use_late_move_reductions:
            return False
        if depth < self.config.lmr_min_depth or move_index < self.config.lmr_move_threshold:
            return False
        if not self.is_quiet_move(state, move):
            return False
        return True

    def is_quiet_move(self, state: GameState, move: Move) -> bool:
        if move.captured is not None or move.is_jump:
            return False
        target_den = RED_DEN if state.side_to_move is Side.BLUE else BLUE_DEN
        if move.destination == target_den or move.destination in self.enemy_traps_for(state.side_to_move):
            return False
        return True

    def is_square_attacked(self, state: GameState, index: int, by_side: Side) -> bool:
        if state.winner is not None:
            return False
        attack_state = self.with_side_to_move(state, by_side)
        return any(move.destination == index for move in legal_moves(attack_state))

    def enemy_traps_for(self, side: Side) -> set[int]:
        return RED_TRAPS if side is Side.BLUE else BLUE_TRAPS

    def own_traps_for(self, side: Side) -> set[int]:
        return BLUE_TRAPS if side is Side.BLUE else RED_TRAPS

    def with_side_to_move(self, state: GameState, side: Side) -> GameState:
        copy = state.copy()
        copy.side_to_move = side
        return copy

    def move_from_key(self, moves: list[Move], key: tuple[int, int] | None) -> Move | None:
        if key is None:
            return None
        for move in moves:
            if (move.origin, move.destination) == key:
                return move
        return None

    def apply(self, state: GameState, move: Move) -> GameState:
        return apply_search_move(state, move)

    def _check_limits(self) -> None:
        if time.perf_counter() >= self.deadline:
            raise _SearchAborted
        if self.node_limit is not None and self.nodes >= self.node_limit:
            raise _SearchAborted

    def _visit_node(self) -> None:
        self._check_limits()
        self.nodes += 1

    def _hash_state(self, state: GameState) -> tuple:
        board_key = tuple(None if piece is None else (piece.side.value, piece.kind.name) for piece in state.board)
        history_key = ()
        if self.config.use_repetition_penalty:
            history_key = tuple(
                (move.origin, move.destination, move.piece.side.value, move.piece.kind.name)
                for move in state.move_history[-4:]
            )
        return board_key, state.side_to_move.value, state.result.value, state.winner.value if state.winner else None, history_key
