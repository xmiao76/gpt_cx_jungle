from __future__ import annotations

import hashlib
import json
import struct
import sys
import time
from array import array
from collections import deque
from dataclasses import dataclass
from enum import IntEnum
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Callable

from jungle.domain import (
    BLUE_DEN,
    BLUE_TRAPS,
    RED_DEN,
    RED_TRAPS,
    TRAP_OWNER,
    WATER,
    GameState,
    Move,
    Piece,
    PieceType,
    ResultType,
    Side,
)
from jungle.rules import generate_piece_moves, legal_moves
from jungle.rules.logic import JUMPERS, TIGER_JUMP_WATER_SPAN


ASSET_NAME = "two_piece_v1.jgtb"
MAGIC = b"JGTB2P\0\0"
FORMAT_VERSION = 1
ENTRY_SIZE = 2
ENTRY_COUNT = 8 * 8 * 63 * 63 * 2

_HEADER = struct.Struct("<8sHHII32s32s")
_DISTANCE_MASK = 0x3FFF
_DRAW_CODE = 0x4000
_WIN_CODE = 0x8000
_LOSS_CODE = 0xC000
_UNKNOWN = 2


class WDL(IntEnum):
    """An exact outcome from the side-to-move's point of view."""

    LOSS = -1
    DRAW = 0
    WIN = 1


@dataclass(frozen=True, slots=True)
class TablebaseEntry:
    wdl: WDL
    distance: int | None


@dataclass(frozen=True, slots=True)
class TablebaseMove:
    move: Move
    wdl: WDL
    distance: int | None


@dataclass(frozen=True, slots=True)
class GenerationStats:
    valid_positions: int
    wins: int
    draws: int
    losses: int
    edges: int
    max_distance: int
    elapsed_seconds: float


class TablebaseError(RuntimeError):
    """Raised when a tablebase asset is malformed or incompatible."""


def _rules_manifest() -> bytes:
    """Return the stable rules description bound to the generated asset.

    The semantic version is deliberately explicit: if a capture or terminal rule
    changes, it must be bumped even when the board constants stay unchanged.
    """

    manifest = {
        "semantic_rules_version": 2,
        "board": [9, 7],
        "blue_den": BLUE_DEN,
        "red_den": RED_DEN,
        "blue_traps": sorted(BLUE_TRAPS),
        "red_traps": sorted(RED_TRAPS),
        "trap_owners": sorted((index, side.value) for index, side in TRAP_OWNER.items()),
        "water": sorted(WATER),
        "jumpers": sorted(int(kind) for kind in JUMPERS),
        "tiger_jump_water_span": TIGER_JUMP_WATER_SPAN,
        "movement": {
            "orthogonal_steps": True,
            "only_rat_enters_water": True,
            "own_den_forbidden": True,
            "rat_blocks_river_jump": True,
        },
        "capture": {
            "equal_or_lower_effective_rank": True,
            "enemy_trap_rank": 0,
            "land_rat_captures_elephant": True,
            "elephant_captures_trapped_rat": True,
            "elephant_cannot_capture_untrapped_rat": True,
            "shore_capture_forbidden": True,
            "water_capture": "rat-versus-rat-only",
        },
        "terminal": ["opponent-den", "capture-all", "no-legal-moves"],
    }
    return json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("ascii")


RULES_HASH = hashlib.sha256(_rules_manifest()).digest()
RULES_HASH_HEX = RULES_HASH.hex()


def default_tablebase_path() -> Path:
    """Return the source/install path used for a filesystem package."""

    return Path(__file__).with_name("data") / ASSET_NAME


def _dense_index(
    blue_kind_index: int,
    red_kind_index: int,
    blue_position: int,
    red_position: int,
    side_index: int,
) -> int:
    value = blue_kind_index * 8 + red_kind_index
    value = value * 63 + blue_position
    value = value * 63 + red_position
    return value * 2 + side_index


def _decode_dense(index: int) -> tuple[int, int, int, int, int]:
    value, side_index = divmod(index, 2)
    value, red_position = divmod(value, 63)
    value, blue_position = divmod(value, 63)
    blue_kind_index, red_kind_index = divmod(value, 8)
    return blue_kind_index, red_kind_index, blue_position, red_position, side_index


def _piece_can_occupy(kind_index: int, position: int, side: Side) -> bool:
    if position == (BLUE_DEN if side is Side.BLUE else RED_DEN):
        return False
    kind = PieceType(kind_index + 1)
    return kind is PieceType.RAT or position not in WATER


def _valid_position(
    blue_kind_index: int,
    red_kind_index: int,
    blue_position: int,
    red_position: int,
) -> bool:
    if blue_position == red_position:
        return False
    if not _piece_can_occupy(blue_kind_index, blue_position, Side.BLUE):
        return False
    if not _piece_can_occupy(red_kind_index, red_position, Side.RED):
        return False
    # A game stops at the first den entry, so this double-win arrangement is
    # unreachable and has no well-defined winner.
    return not (blue_position == RED_DEN and red_position == BLUE_DEN)


def _terminal_winner(blue_position: int, red_position: int) -> Side | None:
    if blue_position == RED_DEN:
        return Side.BLUE
    if red_position == BLUE_DEN:
        return Side.RED
    return None


def _state_for(
    blue_kind_index: int,
    red_kind_index: int,
    blue_position: int,
    red_position: int,
    side_index: int,
) -> GameState:
    board: list[Piece | None] = [None] * 63
    board[blue_position] = Piece(Side.BLUE, PieceType(blue_kind_index + 1))
    board[red_position] = Piece(Side.RED, PieceType(red_kind_index + 1))
    return GameState(board=board, side_to_move=Side.BLUE if side_index == 0 else Side.RED)


def _encode_entry(wdl: WDL, distance: int | None) -> int:
    if wdl is WDL.DRAW:
        if distance is not None:
            raise ValueError("Draw entries cannot have a distance.")
        return _DRAW_CODE
    if distance is None or not 0 <= distance <= _DISTANCE_MASK:
        raise ValueError(f"Distance must be between 0 and {_DISTANCE_MASK}.")
    return (_WIN_CODE if wdl is WDL.WIN else _LOSS_CODE) | distance


def _decode_entry(value: int) -> TablebaseEntry | None:
    kind = value & 0xC000
    if kind == 0:
        return None
    if kind == _DRAW_CODE:
        return TablebaseEntry(WDL.DRAW, None)
    distance = value & _DISTANCE_MASK
    if kind == _WIN_CODE:
        return TablebaseEntry(WDL.WIN, distance)
    return TablebaseEntry(WDL.LOSS, distance)


def _little_endian_bytes(values: array[int]) -> bytes:
    if values.itemsize != ENTRY_SIZE:
        raise ValueError("Tablebase entries must be unsigned 16-bit values.")
    if sys.byteorder == "little":
        return values.tobytes()
    clone = array("H", values)
    clone.byteswap()
    return clone.tobytes()


def _pack_asset(entries: array[int], max_distance: int) -> bytes:
    if len(entries) != ENTRY_COUNT:
        raise ValueError(f"Expected {ENTRY_COUNT} entries, got {len(entries)}.")
    payload = _little_endian_bytes(entries)
    checksum = hashlib.sha256(payload).digest()
    header = _HEADER.pack(
        MAGIC,
        FORMAT_VERSION,
        ENTRY_SIZE,
        ENTRY_COUNT,
        max_distance,
        RULES_HASH,
        checksum,
    )
    return header + payload


def _unpack_asset(data: bytes) -> tuple[array[int], int]:
    if len(data) < _HEADER.size:
        raise TablebaseError("Tablebase header is truncated.")
    magic, version, entry_size, entry_count, max_distance, rules_hash, checksum = _HEADER.unpack_from(data)
    if magic != MAGIC:
        raise TablebaseError("Tablebase magic does not match.")
    if version != FORMAT_VERSION:
        raise TablebaseError(f"Unsupported tablebase version {version}.")
    if entry_size != ENTRY_SIZE:
        raise TablebaseError(f"Unsupported tablebase entry size {entry_size}.")
    if entry_count != ENTRY_COUNT:
        raise TablebaseError(f"Tablebase has {entry_count} entries; expected {ENTRY_COUNT}.")
    if rules_hash != RULES_HASH:
        raise TablebaseError("Tablebase rules hash is incompatible with this engine.")
    expected_size = _HEADER.size + entry_count * entry_size
    if len(data) != expected_size:
        raise TablebaseError(f"Tablebase has {len(data)} bytes; expected {expected_size}.")
    payload = data[_HEADER.size :]
    if hashlib.sha256(payload).digest() != checksum:
        raise TablebaseError("Tablebase payload checksum does not match.")
    entries = array("H")
    entries.frombytes(payload)
    if sys.byteorder != "little":
        entries.byteswap()
    if max_distance > _DISTANCE_MASK:
        raise TablebaseError("Tablebase maximum distance is not representable.")
    return entries, max_distance


class TwoPieceTablebase:
    """Loaded exact one-blue-animal versus one-red-animal tablebase."""

    __slots__ = ("_entries", "max_distance")

    def __init__(self, entries: array[int], max_distance: int) -> None:
        if entries.typecode != "H" or len(entries) != ENTRY_COUNT:
            raise ValueError("Tablebase entries must be a complete unsigned-short array.")
        self._entries = entries
        self.max_distance = max_distance

    @classmethod
    def from_bytes(cls, data: bytes) -> "TwoPieceTablebase":
        entries, max_distance = _unpack_asset(data)
        return cls(entries, max_distance)

    @classmethod
    def load(cls, path: str | Path | None = None) -> "TwoPieceTablebase":
        if path is not None:
            return cls.from_bytes(Path(path).read_bytes())
        resource = resources.files("jungle.ai").joinpath("data", ASSET_NAME)
        return cls.from_bytes(resource.read_bytes())

    @classmethod
    def try_load(cls, path: str | Path | None = None) -> "TwoPieceTablebase | None":
        try:
            return cls.load(path)
        except (OSError, TablebaseError):
            return None

    def probe(self, state: GameState) -> TablebaseEntry | None:
        """Probe a state, returning ``None`` outside the two-piece domain."""

        blue: tuple[int, Piece] | None = None
        red: tuple[int, Piece] | None = None
        for position, piece in enumerate(state.board):
            if piece is None:
                continue
            if piece.side is Side.BLUE:
                if blue is not None:
                    return None
                blue = position, piece
            else:
                if red is not None:
                    return None
                red = position, piece
        if blue is None or red is None:
            return None
        blue_position, blue_piece = blue
        red_position, red_piece = red
        return self.probe_codes(
            blue_piece.kind,
            blue_position,
            red_piece.kind,
            red_position,
            state.side_to_move,
        )

    def probe_codes(
        self,
        blue_kind: PieceType | int,
        blue_position: int,
        red_kind: PieceType | int,
        red_position: int,
        side_to_move: Side,
    ) -> TablebaseEntry | None:
        """Probe compact piece codes without allocating a :class:`GameState`.

        Kind integers use the public ``PieceType`` values (rat=1 through
        elephant=8), which also matches the optimized search position.
        """

        try:
            blue_piece_type = PieceType(blue_kind)
            red_piece_type = PieceType(red_kind)
        except ValueError:
            return None
        if not 0 <= blue_position < 63 or not 0 <= red_position < 63:
            return None
        if not isinstance(side_to_move, Side):
            return None
        index = _dense_index(
            int(blue_piece_type) - 1,
            int(red_piece_type) - 1,
            blue_position,
            red_position,
            0 if side_to_move is Side.BLUE else 1,
        )
        return _decode_entry(self._entries[index])

    def rank_moves(self, state: GameState) -> tuple[TablebaseMove, ...]:
        """Return legal moves in exact tablebase preference order.

        Forced wins minimize distance, draws outrank losses, and forced losses
        maximize resistance. Coordinate order makes equal choices deterministic.
        """

        current = self.probe(state)
        if current is None or current.distance == 0 or state.result is not ResultType.ONGOING:
            return ()
        ranked: list[TablebaseMove] = []
        for move in legal_moves(state):
            if move.captured is not None or move.destination == (RED_DEN if move.piece.side is Side.BLUE else BLUE_DEN):
                ranked.append(TablebaseMove(move, WDL.WIN, 1))
                continue
            board = state.board.copy()
            board[move.origin] = None
            board[move.destination] = move.piece
            child = GameState(board=board, side_to_move=state.side_to_move.opponent)
            child_entry = self.probe(child)
            if child_entry is None:
                raise TablebaseError("A legal two-piece successor is absent from the tablebase.")
            parent_wdl = WDL(-int(child_entry.wdl))
            distance = None if child_entry.distance is None else child_entry.distance + 1
            ranked.append(TablebaseMove(move, parent_wdl, distance))

        def preference(item: TablebaseMove) -> tuple[int, int, int, int]:
            if item.wdl is WDL.WIN:
                return 0, item.distance or 0, item.move.origin, item.move.destination
            if item.wdl is WDL.DRAW:
                return 1, 0, item.move.origin, item.move.destination
            return 2, -(item.distance or 0), item.move.origin, item.move.destination

        ranked.sort(key=preference)
        return tuple(ranked)

    def choose_move(self, state: GameState) -> Move | None:
        ranked = self.rank_moves(state)
        return None if not ranked else ranked[0].move


@lru_cache(maxsize=1)
def load_default_tablebase() -> TwoPieceTablebase | None:
    """Load the bundled asset, returning ``None`` for a missing/corrupt asset."""

    return TwoPieceTablebase.try_load()


def _build_entries(progress: Callable[[str], None] | None = None) -> tuple[array[int], GenerationStats]:
    started = time.perf_counter()

    def report(message: str) -> None:
        if progress is not None:
            progress(message)

    report("enumerating legal two-piece positions")
    dense_to_compact = array("i", [-1]) * ENTRY_COUNT
    compact_to_dense = array("I")
    for blue_kind_index in range(8):
        for red_kind_index in range(8):
            for blue_position in range(63):
                for red_position in range(63):
                    if not _valid_position(blue_kind_index, red_kind_index, blue_position, red_position):
                        continue
                    for side_index in range(2):
                        dense = _dense_index(
                            blue_kind_index,
                            red_kind_index,
                            blue_position,
                            red_position,
                            side_index,
                        )
                        dense_to_compact[dense] = len(compact_to_dense)
                        compact_to_dense.append(dense)

    node_count = len(compact_to_dense)
    outcomes = array("b", [_UNKNOWN]) * node_count
    distances = array("H", [0]) * node_count
    outdegree = array("B", [0]) * node_count
    edge_sources = array("I")
    edge_children = array("I")

    report(f"generating moves for {node_count:,} legal positions")
    for compact, dense in enumerate(compact_to_dense):
        blue_kind_index, red_kind_index, blue_position, red_position, side_index = _decode_dense(dense)
        side = Side.BLUE if side_index == 0 else Side.RED
        winner = _terminal_winner(blue_position, red_position)
        if winner is not None:
            outcomes[compact] = int(WDL.WIN if winner is side else WDL.LOSS)
            continue

        state = _state_for(
            blue_kind_index,
            red_kind_index,
            blue_position,
            red_position,
            side_index,
        )
        mover_position = blue_position if side is Side.BLUE else red_position
        moves = generate_piece_moves(state, mover_position)
        if not moves:
            outcomes[compact] = int(WDL.LOSS)
            continue
        opponent_den = RED_DEN if side is Side.BLUE else BLUE_DEN
        if any(move.captured is not None or move.destination == opponent_den for move in moves):
            outcomes[compact] = int(WDL.WIN)
            distances[compact] = 1
            continue

        outdegree[compact] = len(moves)
        for move in moves:
            child_blue_position = move.destination if side is Side.BLUE else blue_position
            child_red_position = move.destination if side is Side.RED else red_position
            child_dense = _dense_index(
                blue_kind_index,
                red_kind_index,
                child_blue_position,
                child_red_position,
                1 - side_index,
            )
            child_compact = dense_to_compact[child_dense]
            if child_compact < 0:
                raise AssertionError("Legal move led outside the tablebase domain.")
            edge_sources.append(compact)
            edge_children.append(child_compact)

    report(f"building reverse graph for {len(edge_sources):,} edges")
    incoming = array("I", [0]) * node_count
    for child in edge_children:
        incoming[child] += 1
    offsets = array("I", [0]) * (node_count + 1)
    total = 0
    for node, count in enumerate(incoming):
        offsets[node] = total
        total += count
    offsets[node_count] = total
    predecessors = array("I", [0]) * total
    cursors = array("I", offsets[:-1])
    for source, child in zip(edge_sources, edge_children, strict=True):
        cursor = cursors[child]
        predecessors[cursor] = source
        cursors[child] = cursor + 1
    edge_count = len(edge_sources)
    del edge_sources, edge_children, incoming, cursors, dense_to_compact

    report("solving win/draw/loss and distance-to-mate")
    remaining = array("B", outdegree)
    longest_winning_child = array("H", [0]) * node_count
    queue: deque[int] = deque()
    # Distance-ordered FIFO processing ensures the first losing child gives a
    # winning predecessor its shortest possible conversion distance.
    for wanted_distance in (0, 1):
        for node, outcome in enumerate(outcomes):
            if outcome != _UNKNOWN and distances[node] == wanted_distance:
                queue.append(node)

    while queue:
        child = queue.popleft()
        child_outcome = outcomes[child]
        child_distance = distances[child]
        for offset in range(offsets[child], offsets[child + 1]):
            predecessor = predecessors[offset]
            if outcomes[predecessor] != _UNKNOWN:
                continue
            if child_outcome == int(WDL.LOSS):
                distance = child_distance + 1
                if distance > _DISTANCE_MASK:
                    raise OverflowError("Two-piece distance exceeds the binary format.")
                outcomes[predecessor] = int(WDL.WIN)
                distances[predecessor] = distance
                queue.append(predecessor)
            elif child_outcome == int(WDL.WIN):
                remaining[predecessor] -= 1
                if child_distance > longest_winning_child[predecessor]:
                    longest_winning_child[predecessor] = child_distance
                if remaining[predecessor] == 0:
                    distance = longest_winning_child[predecessor] + 1
                    if distance > _DISTANCE_MASK:
                        raise OverflowError("Two-piece distance exceeds the binary format.")
                    outcomes[predecessor] = int(WDL.LOSS)
                    distances[predecessor] = distance
                    queue.append(predecessor)

    entries = array("H", [0]) * ENTRY_COUNT
    wins = draws = losses = 0
    max_distance = 0
    for compact, dense in enumerate(compact_to_dense):
        outcome = outcomes[compact]
        if outcome == _UNKNOWN:
            wdl = WDL.DRAW
            distance: int | None = None
            draws += 1
        else:
            wdl = WDL(outcome)
            distance = distances[compact]
            max_distance = max(max_distance, distance)
            if wdl is WDL.WIN:
                wins += 1
            else:
                losses += 1
        entries[dense] = _encode_entry(wdl, distance)

    stats = GenerationStats(
        valid_positions=node_count,
        wins=wins,
        draws=draws,
        losses=losses,
        edges=edge_count,
        max_distance=max_distance,
        elapsed_seconds=time.perf_counter() - started,
    )
    return entries, stats


def generate_tablebase_bytes(
    progress: Callable[[str], None] | None = None,
) -> tuple[bytes, GenerationStats]:
    entries, stats = _build_entries(progress)
    return _pack_asset(entries, stats.max_distance), stats


def generate_tablebase(
    path: str | Path = default_tablebase_path(),
    progress: Callable[[str], None] | None = None,
) -> GenerationStats:
    """Generate and atomically replace a deterministic tablebase asset."""

    destination = Path(path)
    data, stats = generate_tablebase_bytes(progress)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(destination)
    return stats


def verify_tablebase(
    path: str | Path = default_tablebase_path(),
    *,
    reproduce: bool = False,
    progress: Callable[[str], None] | None = None,
) -> GenerationStats | None:
    """Validate an asset and optionally reproduce it byte-for-byte."""

    existing = Path(path).read_bytes()
    _unpack_asset(existing)
    if not reproduce:
        return None
    generated, stats = generate_tablebase_bytes(progress)
    if generated != existing:
        raise TablebaseError("Tablebase is valid but is not reproducible from the current generator.")
    return stats


__all__ = [
    "ASSET_NAME",
    "ENTRY_COUNT",
    "FORMAT_VERSION",
    "GenerationStats",
    "RULES_HASH_HEX",
    "TablebaseEntry",
    "TablebaseError",
    "TablebaseMove",
    "TwoPieceTablebase",
    "WDL",
    "default_tablebase_path",
    "generate_tablebase",
    "generate_tablebase_bytes",
    "load_default_tablebase",
    "verify_tablebase",
]
