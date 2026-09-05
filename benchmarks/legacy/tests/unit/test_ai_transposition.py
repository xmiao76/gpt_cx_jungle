from __future__ import annotations

from jungle.ai.transposition import Bound, TranspositionTable


def test_transposition_table_round_trips_entries() -> None:
    table = TranspositionTable(8)
    table.store(0x1234, 5, 77, Bound.EXACT, 42)

    entry = table.probe(0x1234)

    assert entry is not None
    assert (entry.depth, entry.score, entry.bound, entry.move) == (5, 77, Bound.EXACT, 42)
    assert table.hits == 1


def test_transposition_table_prefers_deeper_current_generation_entry() -> None:
    table = TranspositionTable(2)
    first = 0x10
    collision = first + table.size
    table.store(first, 8, 80, Bound.LOWER, 1)

    table.store(collision, 3, 30, Bound.EXACT, 2)

    assert table.probe(first) is not None
    assert table.probe(collision) is None


def test_transposition_table_replaces_old_generation_collision() -> None:
    table = TranspositionTable(2)
    first = 0x10
    collision = first + table.size
    table.store(first, 8, 80, Bound.LOWER, 1)
    table.new_search()

    table.store(collision, 1, 10, Bound.UPPER, 2)

    assert table.probe(first) is None
    entry = table.probe(collision)
    assert entry is not None and entry.move == 2
