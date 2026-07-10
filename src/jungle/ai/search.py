from __future__ import annotations

import math
import time
from dataclasses import dataclass
from enum import Enum

from jungle.domain import (
    BLUE_DEN,
    BLUE_TRAPS,
    RED_DEN,
    RED_TRAPS,
    WATER,
    GameState,
    Move,
    Piece,
    PieceType,
    Position,
    Side,
    TRAP_OWNER,
    neighbors,
)
from jungle.rules import legal_moves

from .position import apply_search_move


TERMINAL_SCORE = 100_000
MAX_DEPTH = 8
EXACT = "exact"
LOWER = "lower"
UPPER = "upper"


class _SearchAborted(Exception):
    pass

PIECE_VALUES = {
    PieceType.RAT: 130,
    PieceType.CAT: 220,
    PieceType.DOG: 300,
    PieceType.WOLF: 390,
    PieceType.LEOPARD: 500,
    PieceType.TIGER: 760,
    PieceType.LION: 820,
    PieceType.ELEPHANT: 900,
}


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

    def choose_move(self, state: GameState) -> SearchResult:
        self.deadline = time.perf_counter() + self.time_limit_ms / 1000.0
        self.nodes = 0
        self.tt.clear()
        self.killer_moves.clear()
        self.history_scores.clear()
        best_move: Move | None = None
        best_score = -math.inf
        completed_depth = 0
        start = time.perf_counter()

        tactical = self.find_forced_tactical_move(state)
        if tactical is not None:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return SearchResult(tactical, self.evaluate(self.apply(state, tactical), state.side_to_move), 1, self.nodes, elapsed_ms)
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
        return SearchResult(best_move, int(best_score), completed_depth, self.nodes, elapsed_ms)

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

    def find_enhanced_tactical_move(self, state: GameState) -> Move | None:
        opponent = state.side_to_move.opponent
        target_den = RED_DEN if state.side_to_move is Side.BLUE else BLUE_DEN
        best_move: Move | None = None
        best_score = 0
        for move in legal_moves(state):
            child = self.apply(state, move)
            if child.winner is state.side_to_move:
                return move
            if self.find_immediate_win(child, opponent) is not None:
                continue

            score = 0
            if move.captured is not None:
                score += PIECE_VALUES[move.captured.kind] * 4 - PIECE_VALUES[move.piece.kind]
                if self.is_square_attacked(child, move.destination, opponent):
                    score -= PIECE_VALUES[move.piece.kind] * 3
            if move.destination in self.enemy_traps_for(state.side_to_move):
                score += 1_200
            if move.is_jump:
                score += 2_600
                if self.config.use_den_safety and move.captured is None and self.is_square_attacked(child, move.destination, opponent):
                    score -= PIECE_VALUES[move.piece.kind] * 5
            distance = Position.from_index(move.destination).manhattan_distance(Position.from_index(target_den))
            if distance <= 1:
                score += 2_400
            if self.find_immediate_win(child, state.side_to_move) is not None:
                score += 3_200
            if score > best_score:
                best_score = score
                best_move = move
        return best_move if best_score >= 1_600 else None

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
        moves = self.order_moves(state, legal_moves(state), preferred_move=preferred_move, tactical=True, ply=0)
        for move in moves:
            self._check_limits()
            child = self.apply(state, move)
            score = -self._alphabeta(child, depth - 1, -beta, -alpha, 1)
            if self.config.use_den_safety and self.is_unsafe_non_capture_jump(state, move, child):
                score -= PIECE_VALUES[move.piece.kind] * 48
            if score > best_score:
                best_score = score
                best_move = move
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
            if entry.flag == EXACT:
                return entry.score
            if entry.flag == LOWER:
                alpha = max(alpha, entry.score)
            elif entry.flag == UPPER:
                beta = min(beta, entry.score)
            if alpha >= beta:
                return entry.score

        if state.result_reason:
            score = self.evaluate(state, state.side_to_move)
            self.tt[key] = TTEntry(depth, score, EXACT, None)
            return score
        if depth <= 0:
            if self.config.use_quiescence:
                return self._quiescence(state, alpha, beta, 0)
            score = self.evaluate(state, state.side_to_move)
            self.tt[key] = TTEntry(depth, score, EXACT, None)
            return score

        moves = legal_moves(state)
        if not moves:
            score = self.evaluate(state, state.side_to_move)
            self.tt[key] = TTEntry(depth, score, EXACT, None)
            return score

        value = -math.inf
        best_move_key: tuple[int, int] | None = None
        preferred = self.move_from_key(moves, entry.best_move if entry is not None else None)
        for move_index, move in enumerate(self.order_moves(state, moves, preferred_move=preferred, ply=ply)):
            child = self.apply(state, move)
            if self.should_reduce_late_move(state, move, move_index, depth):
                reduced_depth = max(0, depth - 2)
                score = -self._alphabeta(child, reduced_depth, -alpha - 1, -alpha, ply + 1)
                if score > alpha:
                    score = -self._alphabeta(child, depth - 1, -beta, -alpha, ply + 1)
            else:
                score = -self._alphabeta(child, depth - 1, -beta, -alpha, ply + 1)
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
        self.tt[key] = TTEntry(depth, entry_score, flag, best_move_key)
        return entry_score

    def _quiescence(self, state: GameState, alpha: float, beta: float, extension_depth: int) -> int:
        self._visit_node()

        stand_pat = self.evaluate(state, state.side_to_move)
        if stand_pat >= beta:
            return int(beta)
        alpha = max(alpha, stand_pat)
        if extension_depth >= self.config.quiescence_max_depth or state.result_reason:
            return int(alpha)

        candidates = self.forcing_moves(state)
        if not candidates:
            return int(alpha)

        for move in self.order_moves(state, candidates, tactical=True)[: self.config.quiescence_candidate_limit]:
            self._check_limits()
            score = -self._quiescence(self.apply(state, move), -beta, -alpha, extension_depth + 1)
            if score >= beta:
                return int(beta)
            alpha = max(alpha, score)
        return int(alpha)

    def forcing_moves(self, state: GameState) -> list[Move]:
        target_den = RED_DEN if state.side_to_move is Side.BLUE else BLUE_DEN
        opponent = state.side_to_move.opponent
        forcing: list[Move] = []
        for move in legal_moves(state):
            if move.captured is not None or move.destination == target_den or move.destination in self.enemy_traps_for(state.side_to_move):
                forcing.append(move)
                continue
            child = self.apply(state, move)
            if child.winner is state.side_to_move or self.find_immediate_win(child, opponent) is None:
                if self.find_immediate_win(state, opponent) is not None:
                    forcing.append(move)
        return forcing

    def order_moves(
        self,
        state: GameState,
        moves: list[Move],
        preferred_move: Move | None = None,
        tactical: bool = False,
        ply: int = 0,
    ) -> list[Move]:
        target_den = RED_DEN if state.side_to_move is Side.BLUE else BLUE_DEN
        opponent = state.side_to_move.opponent

        def move_score(move: Move) -> int:
            score = 0
            if preferred_move is not None and move.origin == preferred_move.origin and move.destination == preferred_move.destination:
                score += 1_000_000
            child = self.apply(state, move)
            if child.winner is state.side_to_move:
                score += 900_000
            if move.captured is not None:
                score += 30_000 + PIECE_VALUES[move.captured.kind] * 20 - PIECE_VALUES[move.piece.kind]
                if self.config.use_static_capture_ordering:
                    score += self.static_exchange_score(state, move)
            if move.destination == target_den:
                score += 800_000
            if move.is_jump:
                score += 1_500
            distance = Position.from_index(move.destination).manhattan_distance(Position.from_index(target_den))
            score += (18 - distance) * 120
            if move.destination in self.enemy_traps_for(state.side_to_move):
                score += 2_200
            if tactical and self.is_square_attacked(child, move.destination, opponent) and child.winner is None:
                score -= PIECE_VALUES[move.piece.kind] * 16
            if tactical and self.find_immediate_win(child, opponent) is not None:
                score -= 80_000
            if self.config.use_enhanced_ordering:
                if self.find_immediate_win(child, state.side_to_move) is not None:
                    score += 18_000
                if self.is_square_attacked(child, move.destination, opponent) and child.winner is None:
                    score -= PIECE_VALUES[move.piece.kind] * 8
                if move.destination in self.own_traps_for(state.side_to_move):
                    score += 400
            if self.config.use_den_safety and move.is_jump and move.captured is None:
                if self.is_square_attacked(child, move.destination, opponent) and child.winner is None:
                    score -= PIECE_VALUES[move.piece.kind] * 24
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
        if state.winner is perspective:
            return TERMINAL_SCORE
        if state.winner is perspective.opponent:
            return -TERMINAL_SCORE

        if self.profile is SearchProfile.FAST and not self.config.force_full_evaluation:
            return self.fast_evaluate(state, perspective)

        score = self.fast_evaluate(state, perspective)
        score += self.mobility_score(state, perspective)
        score -= self.mobility_score(state, perspective.opponent)
        if self.config.use_threat_score:
            score += self.config.threat_weight * self.threat_score(state, perspective)
            score -= self.config.threat_weight * self.threat_score(state, perspective.opponent)
        if self.config.use_den_safety:
            score += self.den_safety_score(state, perspective)
            score -= self.den_safety_score(state, perspective.opponent)
        if self.config.use_den_race_score:
            score += self.den_race_score(state, perspective)
            score -= self.den_race_score(state, perspective.opponent)
        if self.config.use_repetition_penalty:
            score += self.repetition_score(state, perspective)
            score -= self.repetition_score(state, perspective.opponent)
        return score

    def fast_evaluate(self, state: GameState, perspective: Side) -> int:
        score = 0
        for index, piece in enumerate(state.board):
            if piece is None:
                continue
            local = self.piece_square_score(state, index, piece)
            if piece.side is perspective:
                score += local
            else:
                score -= local
        return score

    def piece_square_score(self, state: GameState, index: int, piece: Piece) -> int:
        target_den = RED_DEN if piece.side is Side.BLUE else BLUE_DEN
        own_den = BLUE_DEN if piece.side is Side.BLUE else RED_DEN
        position = Position.from_index(index)
        distance_to_target = position.manhattan_distance(Position.from_index(target_den))
        distance_to_own = position.manhattan_distance(Position.from_index(own_den))
        local = PIECE_VALUES[piece.kind]
        local += (18 - distance_to_target) * 18
        if distance_to_target <= 2:
            local += (3 - distance_to_target) * 450
        elif self.config.use_threat_score and distance_to_target <= 4:
            local += (5 - distance_to_target) * 140
        if index in self.enemy_traps_for(piece.side):
            local += 380
        if index in self.own_traps_for(piece.side):
            local += 90
        if TRAP_OWNER.get(index) is piece.side.opponent:
            local -= PIECE_VALUES[piece.kind] // 2
        if piece.kind is PieceType.RAT and index in WATER:
            local += 160
        if piece.kind in {PieceType.LION, PieceType.TIGER}:
            local += self.jump_lane_score(state, index, piece)
        if distance_to_own <= 2:
            local += (3 - distance_to_own) * 80
        return local

    def threat_score(self, state: GameState, side: Side) -> int:
        score = 0
        turn_state = self.with_side_to_move(state, side)
        target_den = RED_DEN if side is Side.BLUE else BLUE_DEN
        own_den = BLUE_DEN if side is Side.BLUE else RED_DEN
        for move in legal_moves(turn_state):
            child = self.apply(turn_state, move)
            if child.winner is side:
                score += 35_000
            if move.captured is not None:
                score += PIECE_VALUES[move.captured.kind] * 3
                if not self.is_square_attacked(child, move.destination, side.opponent):
                    score += PIECE_VALUES[move.captured.kind] * 2
            if move.destination in self.enemy_traps_for(side):
                score += 900
            distance = Position.from_index(move.destination).manhattan_distance(Position.from_index(target_den))
            if distance <= 2:
                score += (3 - distance) * 1_200
            own_distance = Position.from_index(move.destination).manhattan_distance(Position.from_index(own_den))
            if own_distance <= 2:
                score += (3 - own_distance) * 220
        return score

    def mobility_score(self, state: GameState, side: Side) -> int:
        turn_state = self.with_side_to_move(state, side)
        moves = legal_moves(turn_state)
        return len(moves) * 10

    def jump_lane_score(self, state: GameState, index: int, piece: Piece) -> int:
        turn_state = self.with_side_to_move(state, piece.side)
        score = 0
        for move in legal_moves(turn_state):
            if move.origin != index or not move.is_jump:
                continue
            score += 340
            if move.captured is not None:
                score += PIECE_VALUES[move.captured.kind]
        return score

    def den_safety_score(self, state: GameState, side: Side) -> int:
        own_den = BLUE_DEN if side is Side.BLUE else RED_DEN
        opponent = side.opponent
        score = 0
        for index, piece in enumerate(state.board):
            if piece is None or piece.side is not opponent:
                continue
            distance = Position.from_index(index).manhattan_distance(Position.from_index(own_den))
            if distance <= 3:
                score -= (4 - distance) * 520
            if index in self.own_traps_for(side):
                score -= 420
        return score

    def den_race_score(self, state: GameState, side: Side) -> int:
        target_den = RED_DEN if side is Side.BLUE else BLUE_DEN
        pieces = [(index, piece) for index, piece in enumerate(state.board) if piece is not None and piece.side is side]
        if not pieces:
            return -4_000

        score = len(pieces) * 20
        closest_distance = min(
            Position.from_index(index).manhattan_distance(Position.from_index(target_den))
            for index, _piece in pieces
        )
        score += (16 - closest_distance) * 70
        if closest_distance <= 3:
            score += (4 - closest_distance) * 680

        for index, piece in pieces:
            distance = Position.from_index(index).manhattan_distance(Position.from_index(target_den))
            if distance <= 4:
                score += (5 - distance) * 95
                score += self.defender_count(state, index, piece.side) * 90
            if index in self.enemy_traps_for(side):
                score += 360
        return score

    def defender_count(self, state: GameState, index: int, side: Side) -> int:
        count = 0
        for adjacent in neighbors(index):
            piece = state.board[adjacent]
            if piece is not None and piece.side is side:
                count += 1
        return count

    def repetition_score(self, state: GameState, side: Side) -> int:
        side_moves = [move for move in state.move_history if move.piece.side is side]
        if len(side_moves) < 2:
            return 0
        previous, latest = side_moves[-2], side_moves[-1]
        if previous.origin == latest.destination and previous.destination == latest.origin:
            return -self.config.repetition_penalty
        return 0

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

    def static_exchange_score(self, state: GameState, move: Move) -> int:
        if move.captured is None:
            return 0
        child = self.apply(state, move)
        score = PIECE_VALUES[move.captured.kind] - PIECE_VALUES[move.piece.kind]
        if self.is_square_attacked(child, move.destination, state.side_to_move.opponent):
            score -= PIECE_VALUES[move.piece.kind]
        else:
            score += PIECE_VALUES[move.captured.kind] // 2
        return score * 4

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
