from __future__ import annotations

import math
import time
from collections import Counter
from typing import TYPE_CHECKING

from jungle.domain import BLUE_DEN, BLUE_TRAPS, RED_DEN, RED_TRAPS, GameState, Move, Piece, PieceType, Side

from .core import (
    BLUE,
    EMPTY,
    NO_SIDE,
    NEIGHBORS,
    RED,
    CompactPosition,
    PackedMove,
    move_captured,
    move_destination,
    move_is_jump,
    move_origin,
)
from .fast_evaluation import FAST_TERMINAL_SCORE, PIECE_VALUES, TABLEBASE_SCORE, evaluate_compact, piece_kind
from .transposition import Bound, TranspositionTable

if TYPE_CHECKING:
    from .search import SearchConfig, SearchResult


MATE_THRESHOLD = FAST_TERMINAL_SCORE - 1_000


class CompactSearchAborted(Exception):
    pass


class CompactSearch:
    def __init__(self, time_limit_ms: int, config: SearchConfig, node_limit: int | None = None) -> None:
        self.time_limit_ms = time_limit_ms
        self.config = config
        self.node_limit = node_limit
        self.deadline = 0.0
        self.nodes = 0
        self.table = TranspositionTable(config.transposition_table_size)
        self.killers: dict[int, list[PackedMove]] = {}
        self.history: dict[tuple[int, int], int] = {}
        self.path_counts: Counter[int] = Counter()
        self.root_history: tuple[Move, ...] = ()
        self.tablebase = self._load_tablebase()
        self.tablebase_hits = 0

    def choose_move(self, state: GameState) -> SearchResult:
        from .search import SearchResult

        started = time.perf_counter()
        self.deadline = started + self.time_limit_ms / 1_000.0
        self.nodes = 0
        self.killers.clear()
        self.history.clear()
        self.table.new_search()
        self.tablebase_hits = 0
        self.root_history = tuple(state.move_history[-8:])
        position = CompactPosition.from_game_state(state)
        self.path_counts = self._recent_hash_counts(state)
        self.path_counts[position.zobrist_hash] = max(1, self.path_counts[position.zobrist_hash])

        moves = position.generate_moves()
        winner = position.terminal_winner(moves)
        if not moves:
            score = -FAST_TERMINAL_SCORE
            return SearchResult(None, score, 0, 0, (time.perf_counter() - started) * 1_000)
        if winner is not None:
            score = FAST_TERMINAL_SCORE if winner == position.side_to_move else -FAST_TERMINAL_SCORE
            return SearchResult(None, score, 0, 0, (time.perf_counter() - started) * 1_000)

        winning = next((move for move in moves if move_destination(move) == self._enemy_den(position.side_to_move)), None)
        if winning is not None:
            public = position.to_public_move(winning)
            elapsed = (time.perf_counter() - started) * 1_000
            return SearchResult(public, FAST_TERMINAL_SCORE - 1, 1, 0, elapsed, (public,), 0, 0, 0)

        tb_move, tb_score = self._root_tablebase_move(position, moves)
        if tb_move is not None:
            public = position.to_public_move(tb_move)
            elapsed = (time.perf_counter() - started) * 1_000
            return SearchResult(
                public,
                tb_score,
                0,
                0,
                elapsed,
                (public,),
                0,
                self.table.hits,
                self.tablebase_hits,
            )

        ordered_fallback = self._order_moves(position, moves, 0, 0)
        best_move = ordered_fallback[0]
        best_score = evaluate_compact(position)
        completed_depth = 0
        previous_score = 0

        for depth in range(1, self.config.max_depth + 1):
            try:
                self._check_limits()
                if self.config.use_aspiration_windows and completed_depth:
                    window = max(50, self.config.aspiration_window)
                    alpha = previous_score - window
                    beta = previous_score + window
                    score, move = self._search_root(position, moves, depth, best_move, alpha, beta)
                    if score <= alpha or score >= beta:
                        score, move = self._search_root(position, moves, depth, best_move, -math.inf, math.inf)
                else:
                    score, move = self._search_root(position, moves, depth, best_move, -math.inf, math.inf)
            except CompactSearchAborted:
                break
            if move:
                best_move = move
                best_score = score
                previous_score = score
                completed_depth = depth

        elapsed = (time.perf_counter() - started) * 1_000
        public_move = position.to_public_move(best_move)
        public_pv = self._extract_public_pv(position, completed_depth) or (public_move,)
        nps = int(self.nodes * 1_000 / elapsed) if elapsed > 0 else 0
        return SearchResult(
            public_move,
            int(best_score),
            completed_depth,
            self.nodes,
            elapsed,
            public_pv,
            nps,
            self.table.hits,
            self.tablebase_hits,
        )

    def _search_root(
        self,
        position: CompactPosition,
        root_moves: list[PackedMove],
        depth: int,
        preferred: PackedMove,
        alpha: float,
        beta: float,
    ) -> tuple[int, PackedMove]:
        alpha_original = alpha
        beta_original = beta
        best_score = -math.inf
        best_move = preferred
        moves = self._order_moves(position, root_moves, preferred, 0)
        for index, move in enumerate(moves):
            self._check_limits()
            undo = position.make_move(move)
            try:
                score = self._score_child(position, depth - 1, alpha, beta, 1, index > 0, 0)
            finally:
                position.unmake_move(move, undo)
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)
            if alpha >= beta:
                self._record_cutoff(position.side_to_move, move, depth, 0)
                break
        bound = Bound.EXACT
        if best_score <= alpha_original:
            bound = Bound.UPPER
        elif best_score >= beta_original:
            bound = Bound.LOWER
        self.table.store(position.zobrist_hash, depth, self._score_to_tt(int(best_score), 0), bound, best_move)
        return int(best_score), best_move

    def _negamax(
        self,
        position: CompactPosition,
        depth: int,
        alpha: float,
        beta: float,
        ply: int,
        extensions_used: int,
    ) -> int:
        self._visit_node()
        if position.winner != NO_SIDE:
            return self._terminal_score(position, ply)

        tablebase_score = self._tablebase_score(position)
        if tablebase_score is not None:
            return tablebase_score

        alpha_original = alpha
        beta_original = beta
        entry = self.table.probe(position.zobrist_hash)
        preferred = 0
        if entry is not None:
            preferred = entry.move
            if entry.depth >= depth:
                score = self._score_from_tt(entry.score, ply)
                if entry.bound is Bound.EXACT:
                    return score
                if entry.bound is Bound.LOWER:
                    alpha = max(alpha, score)
                else:
                    beta = min(beta, score)
                if alpha >= beta:
                    return score

        moves = position.generate_moves()
        if not moves:
            return -FAST_TERMINAL_SCORE + ply
        if depth <= 0:
            if self.config.use_quiescence:
                score = self._quiescence(position, alpha, beta, ply, 0)
            else:
                score = evaluate_compact(position)
            bound = Bound.EXACT
            if score <= alpha_original:
                bound = Bound.UPPER
            elif score >= beta_original:
                bound = Bound.LOWER
            self.table.store(position.zobrist_hash, 0, self._score_to_tt(score, ply), bound, 0)
            return score

        best_score = -math.inf
        best_move = 0
        ordered = self._order_moves(position, moves, preferred, ply)
        for index, move in enumerate(ordered):
            extension = 0
            if extensions_used == 0 and self._is_den_pressure_move(position.side_to_move, move):
                extension = 1
            child_depth = depth - 1 + extension
            undo = position.make_move(move)
            try:
                if self._should_reduce(move, index, depth, ply):
                    score = self._score_child(
                        position, max(0, child_depth - 1), alpha, alpha + 1, ply + 1, True, extensions_used + extension
                    )
                    if score > alpha:
                        score = self._score_child(
                            position, child_depth, alpha, beta, ply + 1, index > 0, extensions_used + extension
                        )
                else:
                    score = self._score_child(
                        position, child_depth, alpha, beta, ply + 1, index > 0, extensions_used + extension
                    )
            finally:
                position.unmake_move(move, undo)
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)
            if alpha >= beta:
                self._record_cutoff(position.side_to_move, move, depth, ply)
                break

        bound = Bound.EXACT
        if best_score <= alpha_original:
            bound = Bound.UPPER
        elif best_score >= beta_original:
            bound = Bound.LOWER
        self.table.store(
            position.zobrist_hash,
            depth,
            self._score_to_tt(int(best_score), ply),
            bound,
            best_move,
        )
        return int(best_score)

    def _score_child(
        self,
        position: CompactPosition,
        depth: int,
        alpha: float,
        beta: float,
        ply: int,
        later_move: bool,
        extensions_used: int,
    ) -> int:
        key = position.zobrist_hash
        if self.path_counts[key] > 0:
            if ply == 1 and self.config.repetition_penalty:
                return -self.config.repetition_penalty * 4
            return 0
        self.path_counts[key] += 1
        try:
            if self.config.use_principal_variation_search and later_move and math.isfinite(alpha):
                score = -self._negamax(position, depth, -alpha - 1, -alpha, ply, extensions_used)
                if alpha < score < beta:
                    score = -self._negamax(position, depth, -beta, -alpha, ply, extensions_used)
                return score
            return -self._negamax(position, depth, -beta, -alpha, ply, extensions_used)
        finally:
            self.path_counts[key] -= 1
            if self.path_counts[key] == 0:
                del self.path_counts[key]

    def _quiescence(
        self,
        position: CompactPosition,
        alpha: float,
        beta: float,
        ply: int,
        qply: int,
    ) -> int:
        self._visit_node()
        if position.winner != NO_SIDE:
            return self._terminal_score(position, ply)
        tablebase_score = self._tablebase_score(position)
        if tablebase_score is not None:
            return tablebase_score

        moves = position.generate_moves()
        if not moves:
            return -FAST_TERMINAL_SCORE + ply
        under_threat = self._has_immediate_den_threat(position)
        stand_pat = evaluate_compact(position)
        if not under_threat:
            if stand_pat >= beta:
                return int(stand_pat)
            alpha = max(alpha, stand_pat)
        max_qply = max(1, min(6, self.config.quiescence_max_depth or 6))
        if qply >= max_qply:
            return int(stand_pat if under_threat else alpha)

        if under_threat:
            candidates = [move for move in moves if self._defends_den(position, move)]
            if not candidates:
                return -FAST_TERMINAL_SCORE + ply
        else:
            enemy_den = self._enemy_den(position.side_to_move)
            candidates = [
                move for move in moves if move_captured(move) != EMPTY or move_destination(move) == enemy_den
            ]
        if not candidates:
            return int(alpha)

        for move in self._order_moves(position, candidates, 0, ply):
            self._check_limits()
            undo = position.make_move(move)
            key = position.zobrist_hash
            try:
                if self.path_counts[key] > 0:
                    score = 0
                else:
                    self.path_counts[key] += 1
                    try:
                        score = -self._quiescence(position, -beta, -alpha, ply + 1, qply + 1)
                    finally:
                        self.path_counts[key] -= 1
                        if self.path_counts[key] == 0:
                            del self.path_counts[key]
            finally:
                position.unmake_move(move, undo)
            if score >= beta:
                return int(score)
            alpha = max(alpha, score)
        return int(alpha)

    def _order_moves(
        self,
        position: CompactPosition,
        moves: list[PackedMove],
        preferred: PackedMove,
        ply: int,
    ) -> list[PackedMove]:
        side = position.side_to_move
        target_den = self._enemy_den(side)
        target_traps = RED_TRAPS if side == BLUE else BLUE_TRAPS

        def score(move: PackedMove) -> int:
            value = 0
            if preferred and move == preferred:
                value += 2_000_000
            destination = move_destination(move)
            if destination == target_den:
                value += 1_500_000
            captured = move_captured(move)
            if captured:
                attacker = position.board[move_origin(move)]
                value += 200_000 + PIECE_VALUES[piece_kind(captured)] * 32 - PIECE_VALUES[piece_kind(attacker)]
            if destination in target_traps:
                value += 18_000
            if move_is_jump(move):
                value += 2_500
            if move in self.killers.get(ply, ()):
                value += 35_000
            value += self.history.get((side, move), 0)
            row, col = divmod(destination, 7)
            den_row, den_col = divmod(target_den, 7)
            value += (18 - abs(row - den_row) - abs(col - den_col)) * 100
            if ply == 0 and self._is_root_reversal(position, move):
                value -= 4_000
            return value

        return sorted(moves, key=score, reverse=True)

    def _record_cutoff(self, side: int, move: PackedMove, depth: int, ply: int) -> None:
        if move_captured(move):
            return
        killers = self.killers.setdefault(ply, [])
        if move not in killers:
            killers.insert(0, move)
            del killers[2:]
        self.history[(side, move)] = min(100_000, self.history.get((side, move), 0) + depth * depth)

    def _should_reduce(self, move: PackedMove, index: int, depth: int, ply: int) -> bool:
        if not self.config.use_late_move_reductions:
            return False
        if depth < max(4, self.config.lmr_min_depth) or index < max(5, self.config.lmr_move_threshold):
            return False
        if move_captured(move) or move_is_jump(move) or self._is_den_pressure_move_for_destination(move_destination(move)):
            return False
        return move not in self.killers.get(ply, ())

    def _has_immediate_den_threat(self, position: CompactPosition) -> bool:
        opponent = position.side_to_move ^ 1
        own_den = BLUE_DEN if position.side_to_move == BLUE else RED_DEN
        for square in NEIGHBORS[own_den]:
            piece = position.board[square]
            if piece and ((piece <= 8) == (opponent == BLUE)):
                return True
        return False

    def _defends_den(self, position: CompactPosition, move: PackedMove) -> bool:
        mover = position.side_to_move
        undo = position.make_move(move)
        try:
            if position.winner == mover:
                return True
            own_den = BLUE_DEN if mover == BLUE else RED_DEN
            return not any(move_destination(reply) == own_den for reply in position.generate_moves())
        finally:
            position.unmake_move(move, undo)

    def _is_den_pressure_move(self, side: int, move: PackedMove) -> bool:
        destination = move_destination(move)
        target = self._enemy_den(side)
        return destination in (RED_TRAPS if side == BLUE else BLUE_TRAPS) or destination == target

    @staticmethod
    def _is_den_pressure_move_for_destination(destination: int) -> bool:
        return destination in BLUE_TRAPS or destination in RED_TRAPS or destination in (BLUE_DEN, RED_DEN)

    def _is_root_reversal(self, position: CompactPosition, move: PackedMove) -> bool:
        if not self.root_history or move_captured(move):
            return False
        side = Side.BLUE if position.side_to_move == BLUE else Side.RED
        for previous in reversed(self.root_history):
            if previous.piece.side is side:
                return previous.origin == move_destination(move) and previous.destination == move_origin(move)
        return False

    def _recent_hash_counts(self, state: GameState) -> Counter[int]:
        counts: Counter[int] = Counter()
        board = state.board.copy()
        side = state.side_to_move
        snapshot = GameState(board.copy(), side)
        counts[CompactPosition.from_game_state(snapshot).zobrist_hash] += 1
        for move in reversed(state.move_history[-8:]):
            board[move.origin] = move.piece
            board[move.destination] = move.captured
            side = move.piece.side
            counts[CompactPosition.from_game_state(GameState(board.copy(), side)).zobrist_hash] += 1
        return counts

    def _extract_pv(self, position: CompactPosition, depth: int) -> list[PackedMove]:
        moves: list[PackedMove] = []
        undos: list[tuple[PackedMove, object]] = []
        seen: set[int] = set()
        try:
            for _ in range(depth):
                if position.zobrist_hash in seen:
                    break
                seen.add(position.zobrist_hash)
                entry = self.table.probe(position.zobrist_hash)
                if entry is None or not entry.move:
                    break
                legal = position.generate_moves()
                if entry.move not in legal:
                    break
                move = entry.move
                moves.append(move)
                undo = position.make_move(move)
                undos.append((move, undo))
                if position.winner != NO_SIDE:
                    break
        finally:
            for move, undo in reversed(undos):
                position.unmake_move(move, undo)
        return moves

    def _extract_public_pv(self, position: CompactPosition, depth: int) -> tuple[Move, ...]:
        result: list[Move] = []
        undos: list[tuple[PackedMove, object]] = []
        seen: set[int] = set()
        try:
            for _ in range(depth):
                if position.zobrist_hash in seen:
                    break
                seen.add(position.zobrist_hash)
                entry = self.table.probe(position.zobrist_hash)
                if entry is None or not entry.move or entry.move not in position.generate_moves():
                    break
                move = entry.move
                result.append(position.to_public_move(move))
                undo = position.make_move(move)
                undos.append((move, undo))
                if position.winner != NO_SIDE:
                    break
        finally:
            for move, undo in reversed(undos):
                position.unmake_move(move, undo)
        return tuple(result)

    def _root_tablebase_move(
        self, position: CompactPosition, moves: list[PackedMove]
    ) -> tuple[PackedMove | None, int]:
        if position.total_piece_count != 2 or self.tablebase is None:
            return None, 0
        ranked: list[tuple[int, int, PackedMove]] = []
        for move in moves:
            undo = position.make_move(move)
            try:
                child_score = self._tablebase_score(position)
                if position.winner != NO_SIDE:
                    child_score = -FAST_TERMINAL_SCORE + 1
            finally:
                position.unmake_move(move, undo)
            if child_score is not None:
                ranked.append((-child_score, -abs(child_score), move))
        if not ranked:
            return None, 0
        ranked.sort(reverse=True)
        return ranked[0][2], ranked[0][0]

    def _tablebase_score(self, position: CompactPosition) -> int | None:
        if position.total_piece_count != 2 or self.tablebase is None:
            return None
        try:
            blue_code = next(code for code in range(1, 9) if position.piece_counts[code])
            red_code = next(code for code in range(9, 17) if position.piece_counts[code])
            blue_mask = position.piece_squares[blue_code]
            red_mask = position.piece_squares[red_code]
            blue_square = (blue_mask & -blue_mask).bit_length() - 1
            red_square = (red_mask & -red_mask).bit_length() - 1
            entry = self.tablebase.probe_codes(
                blue_code,
                blue_square,
                red_code - 8,
                red_square,
                Side.BLUE if position.side_to_move == BLUE else Side.RED,
            )
        except (AttributeError, KeyError, StopIteration, ValueError):
            return None
        if entry is None:
            return None
        self.tablebase_hits += 1
        wdl = int(entry.wdl)
        if wdl > 0:
            return TABLEBASE_SCORE - (entry.distance or 0)
        if wdl < 0:
            return -TABLEBASE_SCORE + (entry.distance or 0)
        return 0

    @staticmethod
    def _load_tablebase():
        try:
            from .tablebase import load_default_tablebase

            return load_default_tablebase()
        except (ImportError, OSError, ValueError):
            return None

    def _terminal_score(self, position: CompactPosition, ply: int) -> int:
        if position.winner == NO_SIDE:
            return evaluate_compact(position)
        if position.winner == position.side_to_move:
            return FAST_TERMINAL_SCORE - ply
        return -FAST_TERMINAL_SCORE + ply

    @staticmethod
    def _enemy_den(side: int) -> int:
        return RED_DEN if side == BLUE else BLUE_DEN

    @staticmethod
    def _score_to_tt(score: int, ply: int) -> int:
        if score >= MATE_THRESHOLD:
            return score + ply
        if score <= -MATE_THRESHOLD:
            return score - ply
        return score

    @staticmethod
    def _score_from_tt(score: int, ply: int) -> int:
        if score >= MATE_THRESHOLD:
            return score - ply
        if score <= -MATE_THRESHOLD:
            return score + ply
        return score

    def _check_limits(self) -> None:
        if time.perf_counter() >= self.deadline:
            raise CompactSearchAborted
        if self.node_limit is not None and self.nodes >= self.node_limit:
            raise CompactSearchAborted

    def _visit_node(self) -> None:
        self._check_limits()
        self.nodes += 1
