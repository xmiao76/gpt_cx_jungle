from __future__ import annotations

from array import array
from dataclasses import dataclass
from enum import IntEnum


class Bound(IntEnum):
    EXACT = 1
    LOWER = 2
    UPPER = 3


@dataclass(frozen=True, slots=True)
class Probe:
    depth: int
    score: int
    bound: Bound
    move: int


class TranspositionTable:
    """Compact, fixed-size, generation-aged transposition table.

    The table deliberately uses primitive arrays rather than one Python object per
    entry.  A 262,144-entry table occupies roughly 5 MiB and has predictable
    replacement behaviour.
    """

    def __init__(self, requested_size: int = 262_144) -> None:
        if requested_size <= 0:
            raise ValueError("Transposition table size must be positive.")
        size = 1 << (requested_size.bit_length() - 1)
        self.size = size
        self.mask = size - 1
        self.keys = array("Q", [0]) * size
        self.scores = array("i", [0]) * size
        self.moves = array("I", [0]) * size
        self.depths = array("h", [-1]) * size
        self.bounds = bytearray(size)
        self.generations = bytearray(size)
        self.generation = 1
        self.hits = 0
        self.stores = 0

    def new_search(self) -> None:
        self.generation = (self.generation + 1) & 0xFF
        if self.generation == 0:
            self.generation = 1
            self.generations[:] = b"\x00" * self.size
        self.hits = 0
        self.stores = 0

    def probe(self, key: int) -> Probe | None:
        index = key & self.mask
        if self.depths[index] < 0 or self.keys[index] != (key & 0xFFFFFFFFFFFFFFFF):
            return None
        self.hits += 1
        return Probe(
            depth=self.depths[index],
            score=self.scores[index],
            bound=Bound(self.bounds[index]),
            move=self.moves[index],
        )

    def store(self, key: int, depth: int, score: int, bound: Bound, move: int = 0) -> None:
        index = key & self.mask
        same_key = self.depths[index] >= 0 and self.keys[index] == (key & 0xFFFFFFFFFFFFFFFF)
        current_generation = self.generations[index] == self.generation
        if current_generation and not same_key and self.depths[index] > depth:
            return
        if same_key and current_generation and self.depths[index] > depth and bound is not Bound.EXACT:
            return
        self.keys[index] = key & 0xFFFFFFFFFFFFFFFF
        self.scores[index] = int(score)
        self.moves[index] = move & 0xFFFFFFFF
        self.depths[index] = max(-1, min(32_767, depth))
        self.bounds[index] = int(bound)
        self.generations[index] = self.generation
        self.stores += 1

