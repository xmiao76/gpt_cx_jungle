from __future__ import annotations

import math
import time
from dataclasses import dataclass

from jungle.domain import (
    BLUE_DEN,
    RED_DEN,
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


PIECE_VALUES = {
    PieceType.RAT: 100,
    PieceType.CAT: 220,
    PieceType.DOG: 300,
    PieceType.WOLF: 380,
    PieceType.LEOPARD: 460,
    PieceType.TIGER: 700,
    PieceType.LION: 780,
    PieceType.ELEPHANT: 900,
}


@dataclass(slots=True)
class SearchResult:
    move: Move | None
    score: int
    depth: int
    nodes: int
    elapsed_ms: float


class AlphaBetaAI:
    def __init__(self, time_limit_ms: int = 1000) -> None:
        self.time_limit_ms = time_limit_ms
        self.deadline = 0.0
        self.nodes = 0
        self.tt: dict[tuple, tuple[int, int]] = {}

    def choose_move(self, state: GameState) -> SearchResult:
        self.deadline = time.perf_counter() + self.time_limit_ms / 1000.0
        self.nodes = 0
        best_move: Move | None = None
        best_score = -math.inf
        completed_depth = 0
        start = time.perf_counter()

        for depth in range(1, 7):
            if time.perf_counter() >= self.deadline:
                break
            score, move = self._search_root(state, depth)
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

    def _search_root(self, state: GameState, depth: int) -> tuple[int, Move | None]:
        best_score = -math.inf
        best_move: Move | None = None
        moves = self.order_moves(state, legal_moves(state))
        for move in moves:
            score = -self._alphabeta(self.apply(state, move), depth - 1, -math.inf, math.inf, state.side_to_move.opponent)
            if score > best_score:
                best_score = score
                best_move = move
            if time.perf_counter() >= self.deadline:
                break
        return int(best_score), best_move

    def _alphabeta(self, state: GameState, depth: int, alpha: float, beta: float, perspective: Side) -> int:
        if time.perf_counter() >= self.deadline:
            return self.evaluate(state, perspective)
        self.nodes += 1
        key = self._hash_state(state, depth, perspective)
        if key in self.tt:
            return self.tt[key][0]
        if depth <= 0 or state.result_reason:
            score = self.evaluate(state, perspective)
            self.tt[key] = (score, depth)
            return score
        moves = legal_moves(state)
        if not moves:
            score = self.evaluate(state, perspective)
            self.tt[key] = (score, depth)
            return score
        value = -math.inf
        for move in self.order_moves(state, moves):
            child = self.apply(state, move)
            score = -self._alphabeta(child, depth - 1, -beta, -alpha, perspective.opponent)
            value = max(value, score)
            alpha = max(alpha, score)
            if alpha >= beta:
                break
        self.tt[key] = (int(value), depth)
        return int(value)

    def order_moves(self, state: GameState, moves: list[Move]) -> list[Move]:
        target_den = RED_DEN if state.side_to_move is Side.BLUE else BLUE_DEN
        return sorted(
            moves,
            key=lambda move: (
                move.captured is not None,
                PIECE_VALUES.get(move.captured.kind, 0) if move.captured else 0,
                -Position.from_index(move.destination).manhattan_distance(Position.from_index(target_den)),
                move.is_jump,
            ),
            reverse=True,
        )

    def evaluate(self, state: GameState, perspective: Side) -> int:
        if state.winner is perspective:
            return 100_000
        if state.winner is perspective.opponent:
            return -100_000
        score = 0
        target_den = RED_DEN if perspective is Side.BLUE else BLUE_DEN
        own_den = BLUE_DEN if perspective is Side.BLUE else RED_DEN
        moves = legal_moves(state)
        mobility = len(moves) * 3 if state.side_to_move is perspective else -len(moves) * 3
        score += mobility
        for index, piece in enumerate(state.board):
            if piece is None:
                continue
            piece_score = PIECE_VALUES[piece.kind]
            distance_to_target = Position.from_index(index).manhattan_distance(Position.from_index(target_den if piece.side is perspective else own_den))
            pressure = 18 - distance_to_target
            trap_penalty = -120 if TRAP_OWNER.get(index) is piece.side.opponent else 0
            local = piece_score + pressure * 8 + trap_penalty
            if piece.side is perspective:
                score += local
            else:
                score -= local
        return score

    def apply(self, state: GameState, move: Move) -> GameState:
        game = Game(state)
        game.apply_move(move)
        return game.state.copy()

    def _hash_state(self, state: GameState, depth: int, perspective: Side) -> tuple:
        board_key = tuple(None if piece is None else (piece.side.value, piece.kind.name) for piece in state.board)
        return board_key, state.side_to_move.value, depth, perspective.value
