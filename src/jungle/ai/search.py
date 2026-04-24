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
)
from jungle.engine import Game
from jungle.rules import legal_moves


TERMINAL_SCORE = 100_000
MAX_DEPTH = 8
EXACT = "exact"
LOWER = "lower"
UPPER = "upper"

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


@dataclass(slots=True)
class TTEntry:
    depth: int
    score: int
    flag: str
    best_move: tuple[int, int] | None


class AlphaBetaAI:
    def __init__(self, time_limit_ms: int = 1000) -> None:
        self.time_limit_ms = time_limit_ms
        self.profile = SearchProfile.FAST if time_limit_ms <= 350 else SearchProfile.FULL
        self.deadline = 0.0
        self.nodes = 0
        self.tt: dict[tuple, TTEntry] = {}

    def choose_move(self, state: GameState) -> SearchResult:
        self.deadline = time.perf_counter() + self.time_limit_ms / 1000.0
        self.nodes = 0
        self.tt.clear()
        best_move: Move | None = None
        best_score = -math.inf
        completed_depth = 0
        start = time.perf_counter()

        tactical = self.find_forced_tactical_move(state)
        if tactical is not None:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return SearchResult(tactical, self.evaluate(self.apply(state, tactical), state.side_to_move), 1, self.nodes, elapsed_ms)

        for depth in range(1, MAX_DEPTH + 1):
            if time.perf_counter() >= self.deadline:
                break
            score, move = self._search_root(state, depth, best_move)
            if move is not None:
                best_move = move
                best_score = score
                completed_depth = depth
        elapsed_ms = (time.perf_counter() - start) * 1000
        if best_move is None:
            moves = legal_moves(state)
            best_move = moves[0] if moves else None
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

    def find_immediate_win(self, state: GameState, side: Side) -> Move | None:
        turn_state = self.with_side_to_move(state, side)
        for move in legal_moves(turn_state):
            child = self.apply(turn_state, move)
            if child.winner is side:
                return move
        return None

    def _search_root(self, state: GameState, depth: int, preferred_move: Move | None) -> tuple[int, Move | None]:
        best_score = -math.inf
        best_move: Move | None = None
        alpha = -math.inf
        moves = self.order_moves(state, legal_moves(state), preferred_move=preferred_move, tactical=True)
        for move in moves:
            score = -self._alphabeta(self.apply(state, move), depth - 1, -math.inf, -alpha)
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)
            if time.perf_counter() >= self.deadline:
                break
        return int(best_score), best_move

    def _alphabeta(self, state: GameState, depth: int, alpha: float, beta: float) -> int:
        if time.perf_counter() >= self.deadline:
            return self.evaluate(state, state.side_to_move)
        self.nodes += 1

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

        if depth <= 0 or state.result_reason:
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
        for move in self.order_moves(state, moves, preferred_move=preferred):
            child = self.apply(state, move)
            score = -self._alphabeta(child, depth - 1, -beta, -alpha)
            if score > value:
                value = score
                best_move_key = (move.origin, move.destination)
            alpha = max(alpha, score)
            if alpha >= beta:
                break

        flag = EXACT
        if value <= alpha_original:
            flag = UPPER
        elif value >= beta:
            flag = LOWER
        entry_score = int(value)
        self.tt[key] = TTEntry(depth, entry_score, flag, best_move_key)
        return entry_score

    def order_moves(
        self,
        state: GameState,
        moves: list[Move],
        preferred_move: Move | None = None,
        tactical: bool = False,
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
            return score

        return sorted(moves, key=move_score, reverse=True)

    def evaluate(self, state: GameState, perspective: Side) -> int:
        if state.winner is perspective:
            return TERMINAL_SCORE
        if state.winner is perspective.opponent:
            return -TERMINAL_SCORE

        if self.profile is SearchProfile.FAST:
            return self.fast_evaluate(state, perspective)

        score = self.fast_evaluate(state, perspective)
        score += self.mobility_score(state, perspective)
        score -= self.mobility_score(state, perspective.opponent)
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
        game = Game(state)
        game.apply_move(move)
        return game.state.copy()

    def _hash_state(self, state: GameState) -> tuple:
        board_key = tuple(None if piece is None else (piece.side.value, piece.kind.name) for piece in state.board)
        return board_key, state.side_to_move.value, state.result.value, state.winner.value if state.winner else None
