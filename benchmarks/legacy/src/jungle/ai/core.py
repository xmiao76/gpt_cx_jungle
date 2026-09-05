from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from jungle.domain import (
    BLUE_DEN,
    BOARD_COLS,
    BOARD_ROWS,
    BOARD_SIZE,
    RED_DEN,
    TRAP_OWNER,
    WATER,
    GameState,
    Move,
    Piece,
    PieceType,
    ResultType,
    Side,
)


# Search-side and piece encodings.  Zero is deliberately reserved for an empty
# square, leaving the sixteen real pieces in one compact, contiguous range.
BLUE = 0
RED = 1
NO_SIDE = -1
EMPTY = 0
PIECE_TYPE_COUNT = 8
PIECE_CODE_COUNT = 17
RAT = int(PieceType.RAT)
TIGER = int(PieceType.TIGER)
LION = int(PieceType.LION)
ELEPHANT = int(PieceType.ELEPHANT)


PackedMove = int

_ORIGIN_MASK = 0x3F
_DESTINATION_SHIFT = 6
_DESTINATION_MASK = 0x3F
_CAPTURE_SHIFT = 12
_CAPTURE_MASK = 0x1F
_JUMP_SHIFT = 17
_JUMP_MASK = 1 << _JUMP_SHIFT


def pack_move(
    origin: int,
    destination: int,
    captured: int = EMPTY,
    is_jump: bool = False,
) -> PackedMove:
    """Pack the search-relevant parts of a move into one Python integer."""
    if not 0 <= origin < BOARD_SIZE:
        raise ValueError(f"Move origin out of bounds: {origin}")
    if not 0 <= destination < BOARD_SIZE:
        raise ValueError(f"Move destination out of bounds: {destination}")
    if not EMPTY <= captured < PIECE_CODE_COUNT:
        raise ValueError(f"Invalid captured piece code: {captured}")
    return (
        origin
        | (destination << _DESTINATION_SHIFT)
        | (captured << _CAPTURE_SHIFT)
        | (_JUMP_MASK if is_jump else 0)
    )


def move_origin(move: PackedMove) -> int:
    return move & _ORIGIN_MASK


def move_destination(move: PackedMove) -> int:
    return (move >> _DESTINATION_SHIFT) & _DESTINATION_MASK


def move_captured(move: PackedMove) -> int:
    return (move >> _CAPTURE_SHIFT) & _CAPTURE_MASK


def move_is_jump(move: PackedMove) -> bool:
    return bool(move & _JUMP_MASK)


def unpack_move(move: PackedMove) -> tuple[int, int, int, bool]:
    return move_origin(move), move_destination(move), move_captured(move), move_is_jump(move)


def encode_piece(side: int, kind: int | PieceType) -> int:
    kind_value = int(kind)
    if side not in (BLUE, RED):
        raise ValueError(f"Invalid side code: {side}")
    if not RAT <= kind_value <= ELEPHANT:
        raise ValueError(f"Invalid piece kind: {kind_value}")
    return side * PIECE_TYPE_COUNT + kind_value


def piece_side(piece: int) -> int:
    if not EMPTY < piece < PIECE_CODE_COUNT:
        raise ValueError(f"Invalid piece code: {piece}")
    return (piece - 1) // PIECE_TYPE_COUNT


def piece_kind(piece: int) -> int:
    if not EMPTY < piece < PIECE_CODE_COUNT:
        raise ValueError(f"Invalid piece code: {piece}")
    return (piece - 1) % PIECE_TYPE_COUNT + 1


def public_side(side: int) -> Side:
    if side == BLUE:
        return Side.BLUE
    if side == RED:
        return Side.RED
    raise ValueError(f"Invalid side code: {side}")


def compact_side(side: Side) -> int:
    return BLUE if side is Side.BLUE else RED


def public_piece(piece: int) -> Piece:
    return Piece(public_side(piece_side(piece)), PieceType(piece_kind(piece)))


def compact_piece(piece: Piece) -> int:
    return encode_piece(compact_side(piece.side), piece.kind)


def _precompute_neighbors() -> tuple[tuple[int, ...], ...]:
    result: list[tuple[int, ...]] = []
    # Preserve the authoritative generator's down, up, right, left ordering.
    for square in range(BOARD_SIZE):
        row, col = divmod(square, BOARD_COLS)
        adjacent: list[int] = []
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            next_row, next_col = row + dr, col + dc
            if 0 <= next_row < BOARD_ROWS and 0 <= next_col < BOARD_COLS:
                adjacent.append(next_row * BOARD_COLS + next_col)
        result.append(tuple(adjacent))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class RiverJump:
    destination: int
    path_mask: int
    tiger_allowed: bool


def _precompute_river_jumps() -> tuple[tuple[RiverJump, ...], ...]:
    result: list[tuple[RiverJump, ...]] = []
    for origin in range(BOARD_SIZE):
        row, col = divmod(origin, BOARD_COLS)
        jumps: list[RiverJump] = []
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            next_row, next_col = row + dr, col + dc
            if not (0 <= next_row < BOARD_ROWS and 0 <= next_col < BOARD_COLS):
                continue
            next_square = next_row * BOARD_COLS + next_col
            if next_square not in WATER:
                continue

            path_mask = 0
            path_length = 0
            landing_row, landing_col = next_row, next_col
            while (
                0 <= landing_row < BOARD_ROWS
                and 0 <= landing_col < BOARD_COLS
                and (landing_row * BOARD_COLS + landing_col) in WATER
            ):
                path_mask |= 1 << (landing_row * BOARD_COLS + landing_col)
                path_length += 1
                landing_row += dr
                landing_col += dc
            if not (0 <= landing_row < BOARD_ROWS and 0 <= landing_col < BOARD_COLS):
                continue
            jumps.append(
                RiverJump(
                    destination=landing_row * BOARD_COLS + landing_col,
                    path_mask=path_mask,
                    # This repository intentionally allows tiger jumps only
                    # across the two-square horizontal river span.
                    tiger_allowed=path_length == 2,
                )
            )
        result.append(tuple(jumps))
    return tuple(result)


NEIGHBORS = _precompute_neighbors()
RIVER_JUMPS = _precompute_river_jumps()
WATER_MASK = sum(1 << square for square in WATER)
OWN_DEN = (BLUE_DEN, RED_DEN)
OPPONENT_DEN = (RED_DEN, BLUE_DEN)

_TRAP_OWNER = [NO_SIDE] * BOARD_SIZE
for _square, _owner in TRAP_OWNER.items():
    _TRAP_OWNER[_square] = compact_side(_owner)


_MASK_64 = (1 << 64) - 1


def _splitmix64(value: int) -> tuple[int, int]:
    value = (value + 0x9E3779B97F4A7C15) & _MASK_64
    mixed = value
    mixed = ((mixed ^ (mixed >> 30)) * 0xBF58476D1CE4E5B9) & _MASK_64
    mixed = ((mixed ^ (mixed >> 27)) * 0x94D049BB133111EB) & _MASK_64
    return value, (mixed ^ (mixed >> 31)) & _MASK_64


def _build_zobrist() -> tuple[tuple[tuple[int, ...], ...], int]:
    seed = 0x4A554E474C455F31  # ASCII-ish "JUNGLE_1", fixed for reproducibility.
    rows: list[tuple[int, ...]] = []
    for _ in range(BOARD_SIZE):
        keys = [0]
        for _piece in range(1, PIECE_CODE_COUNT):
            seed, key = _splitmix64(seed)
            keys.append(key)
        rows.append(tuple(keys))
    seed, side_key = _splitmix64(seed)
    return tuple(rows), side_key


ZOBRIST_PIECES, ZOBRIST_SIDE = _build_zobrist()


@dataclass(frozen=True, slots=True)
class Undo:
    captured: int
    previous_winner: int


class CompactPosition:
    """Mutable make/unmake position used only by the search implementation."""

    __slots__ = (
        "board",
        "piece_squares",
        "piece_counts",
        "side_counts",
        "side_to_move",
        "total_piece_count",
        "winner",
        "zobrist_hash",
    )

    def __init__(
        self,
        board: list[int],
        side_to_move: int,
        piece_squares: list[int],
        piece_counts: list[int],
        side_counts: list[int],
        total_piece_count: int,
        winner: int = NO_SIDE,
        zobrist_hash: int | None = None,
    ) -> None:
        self.board = board
        self.side_to_move = side_to_move
        self.piece_squares = piece_squares
        self.piece_counts = piece_counts
        self.side_counts = side_counts
        self.total_piece_count = total_piece_count
        self.winner = winner
        self.zobrist_hash = self.recompute_zobrist() if zobrist_hash is None else zobrist_hash

    @classmethod
    def from_game_state(cls, state: GameState) -> "CompactPosition":
        if len(state.board) != BOARD_SIZE:
            raise ValueError(f"Expected a {BOARD_SIZE}-square board, got {len(state.board)}")

        board = [EMPTY] * BOARD_SIZE
        piece_squares = [0] * PIECE_CODE_COUNT
        piece_counts = [0] * PIECE_CODE_COUNT
        side_counts = [0, 0]
        for square, item in enumerate(state.board):
            if item is None:
                continue
            code = compact_piece(item)
            side = piece_side(code)
            board[square] = code
            piece_squares[code] |= 1 << square
            piece_counts[code] += 1
            side_counts[side] += 1

        winner = NO_SIDE
        if state.winner is not None:
            winner = compact_side(state.winner)
        elif board[RED_DEN] and piece_side(board[RED_DEN]) == BLUE:
            winner = BLUE
        elif board[BLUE_DEN] and piece_side(board[BLUE_DEN]) == RED:
            winner = RED
        elif side_counts[BLUE] == 0:
            winner = RED
        elif side_counts[RED] == 0:
            winner = BLUE
        elif state.result is not ResultType.ONGOING:
            # All currently defined terminal results have a winner.  Rejecting
            # an inconsistent external state is safer than searching through it.
            raise ValueError("Terminal GameState does not identify a winner")

        return cls(
            board=board,
            side_to_move=compact_side(state.side_to_move),
            piece_squares=piece_squares,
            piece_counts=piece_counts,
            side_counts=side_counts,
            total_piece_count=sum(side_counts),
            winner=winner,
        )

    @property
    def squares(self) -> list[int]:
        return self.board

    @property
    def hash(self) -> int:
        return self.zobrist_hash

    def recompute_zobrist(self) -> int:
        value = ZOBRIST_SIDE if self.side_to_move == RED else 0
        for square, piece in enumerate(self.board):
            if piece:
                value ^= ZOBRIST_PIECES[square][piece]
        return value & _MASK_64

    def generate_moves(self, side: int | None = None) -> list[PackedMove]:
        moving_side = self.side_to_move if side is None else side
        if moving_side not in (BLUE, RED):
            raise ValueError(f"Invalid side code: {moving_side}")
        if self.winner != NO_SIDE:
            return []

        moves: list[PackedMove] = []
        rat_mask = (
            self.piece_squares[encode_piece(BLUE, RAT)]
            | self.piece_squares[encode_piece(RED, RAT)]
        )
        own_den = OWN_DEN[moving_side]
        code_start = 1 if moving_side == BLUE else 9
        own_mask = 0
        for piece in range(code_start, code_start + PIECE_TYPE_COUNT):
            own_mask |= self.piece_squares[piece]
        while own_mask:
            origin_bit = own_mask & -own_mask
            origin = origin_bit.bit_length() - 1
            own_mask ^= origin_bit
            piece = self.board[origin]
            kind = piece_kind(piece)
            for destination in NEIGHBORS[origin]:
                if destination == own_den:
                    continue
                if destination in WATER and kind != RAT:
                    continue
                target = self.board[destination]
                if target == EMPTY:
                    moves.append(pack_move(origin, destination))
                elif piece_side(target) != moving_side and self._can_capture(origin, destination):
                    moves.append(pack_move(origin, destination, target))

            if kind not in (TIGER, LION):
                continue
            for jump in RIVER_JUMPS[origin]:
                if kind == TIGER and not jump.tiger_allowed:
                    continue
                if jump.path_mask & rat_mask:
                    continue
                destination = jump.destination
                if destination == own_den:
                    continue
                target = self.board[destination]
                if target == EMPTY:
                    moves.append(pack_move(origin, destination, is_jump=True))
                elif piece_side(target) != moving_side and self._can_capture(origin, destination):
                    moves.append(pack_move(origin, destination, target, is_jump=True))
        return moves

    def generate_moves_for(self, side: int) -> list[PackedMove]:
        return self.generate_moves(side)

    def _can_capture(self, attacker_square: int, defender_square: int) -> bool:
        attacker = self.board[attacker_square]
        defender = self.board[defender_square]
        if attacker == EMPTY or defender == EMPTY or piece_side(attacker) == piece_side(defender):
            return False

        attacker_kind = piece_kind(attacker)
        defender_kind = piece_kind(defender)
        attacker_in_water = attacker_square in WATER
        defender_in_water = defender_square in WATER

        if attacker_kind == RAT and defender_kind == ELEPHANT:
            return not attacker_in_water and not defender_in_water
        if attacker_kind == ELEPHANT and defender_kind == RAT:
            return self._effective_rank(defender_square, defender) == 0
        if attacker_in_water or defender_in_water:
            return (
                attacker_in_water
                and defender_in_water
                and attacker_kind == RAT
                and defender_kind == RAT
            )

        attacker_rank = self._effective_rank(attacker_square, attacker)
        defender_rank = self._effective_rank(defender_square, defender)
        return attacker_rank >= defender_rank

    @staticmethod
    def _effective_rank(square: int, piece: int) -> int:
        side = piece_side(piece)
        return 0 if _TRAP_OWNER[square] == (side ^ 1) else piece_kind(piece)

    def make_move(self, move: PackedMove) -> Undo:
        origin = move_origin(move)
        destination = move_destination(move)
        captured = move_captured(move)
        piece = self.board[origin]
        if piece == EMPTY:
            raise ValueError("Cannot move from an empty square")
        if piece_side(piece) != self.side_to_move:
            raise ValueError("Cannot move a piece belonging to the other side")
        if self.board[destination] != captured:
            raise ValueError("Packed captured piece does not match destination square")

        undo = Undo(captured=captured, previous_winner=self.winner)
        moving_side = self.side_to_move
        origin_mask = 1 << origin
        destination_mask = 1 << destination

        self.zobrist_hash ^= ZOBRIST_PIECES[origin][piece]
        self.zobrist_hash ^= ZOBRIST_PIECES[destination][piece]
        if captured:
            self.zobrist_hash ^= ZOBRIST_PIECES[destination][captured]
        self.zobrist_hash ^= ZOBRIST_SIDE

        self.board[origin] = EMPTY
        self.board[destination] = piece
        self.piece_squares[piece] ^= origin_mask | destination_mask
        if captured:
            captured_side = piece_side(captured)
            self.piece_squares[captured] ^= destination_mask
            self.piece_counts[captured] -= 1
            self.side_counts[captured_side] -= 1
            self.total_piece_count -= 1

        self.side_to_move ^= 1
        if destination == OPPONENT_DEN[moving_side]:
            self.winner = moving_side
        elif self.side_counts[moving_side ^ 1] == 0:
            self.winner = moving_side
        else:
            self.winner = NO_SIDE
        self.zobrist_hash &= _MASK_64
        return undo

    def unmake_move(self, move: PackedMove, undo: Undo) -> None:
        origin = move_origin(move)
        destination = move_destination(move)
        captured = undo.captured
        if captured != move_captured(move):
            raise ValueError("Undo capture does not match packed move")
        piece = self.board[destination]
        if piece == EMPTY:
            raise ValueError("Cannot unmake a move from an empty destination")

        origin_mask = 1 << origin
        destination_mask = 1 << destination
        self.side_to_move ^= 1

        self.zobrist_hash ^= ZOBRIST_SIDE
        self.zobrist_hash ^= ZOBRIST_PIECES[origin][piece]
        self.zobrist_hash ^= ZOBRIST_PIECES[destination][piece]
        if captured:
            self.zobrist_hash ^= ZOBRIST_PIECES[destination][captured]

        self.board[origin] = piece
        self.board[destination] = captured
        self.piece_squares[piece] ^= origin_mask | destination_mask
        if captured:
            captured_side = piece_side(captured)
            self.piece_squares[captured] ^= destination_mask
            self.piece_counts[captured] += 1
            self.side_counts[captured_side] += 1
            self.total_piece_count += 1
        self.winner = undo.previous_winner
        self.zobrist_hash &= _MASK_64

    def terminal_winner(self, moves: Sequence[PackedMove] | None = None) -> int | None:
        if self.winner != NO_SIDE:
            return self.winner
        available = self.generate_moves() if moves is None else moves
        return None if available else self.side_to_move ^ 1

    def is_terminal(self, moves: Sequence[PackedMove] | None = None) -> bool:
        return self.terminal_winner(moves) is not None

    def to_public_move(self, move: PackedMove) -> Move:
        origin = move_origin(move)
        destination = move_destination(move)
        piece_code = self.board[origin]
        if piece_code == EMPTY:
            raise ValueError("Convert a packed move before making it")
        captured_code = move_captured(move)
        is_jump = move_is_jump(move)
        return Move(
            origin=origin,
            destination=destination,
            piece=public_piece(piece_code),
            captured=None if captured_code == EMPTY else public_piece(captured_code),
            is_jump=is_jump,
            note=("jump-capture" if captured_code else "jump") if is_jump else "",
        )

    def assert_consistent(self) -> None:
        piece_squares = [0] * PIECE_CODE_COUNT
        piece_counts = [0] * PIECE_CODE_COUNT
        side_counts = [0, 0]
        for square, piece in enumerate(self.board):
            if piece:
                piece_squares[piece] |= 1 << square
                piece_counts[piece] += 1
                side_counts[piece_side(piece)] += 1
        if piece_squares != self.piece_squares:
            raise AssertionError("piece_squares is inconsistent with board")
        if piece_counts != self.piece_counts:
            raise AssertionError("piece_counts is inconsistent with board")
        if side_counts != self.side_counts:
            raise AssertionError("side_counts is inconsistent with board")
        if sum(side_counts) != self.total_piece_count:
            raise AssertionError("total_piece_count is inconsistent with board")
        if self.recompute_zobrist() != self.zobrist_hash:
            raise AssertionError("zobrist_hash is inconsistent with board")


# A descriptive alias is useful while downstream search code migrates.
CorePosition = CompactPosition


__all__ = [
    "BLUE",
    "RED",
    "NO_SIDE",
    "EMPTY",
    "RAT",
    "TIGER",
    "LION",
    "ELEPHANT",
    "PackedMove",
    "Undo",
    "RiverJump",
    "CompactPosition",
    "CorePosition",
    "NEIGHBORS",
    "RIVER_JUMPS",
    "WATER_MASK",
    "ZOBRIST_PIECES",
    "ZOBRIST_SIDE",
    "pack_move",
    "unpack_move",
    "move_origin",
    "move_destination",
    "move_captured",
    "move_is_jump",
    "encode_piece",
    "piece_side",
    "piece_kind",
    "public_side",
    "compact_side",
    "public_piece",
    "compact_piece",
]
