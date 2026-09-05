from __future__ import annotations

from jungle.domain import BLUE_DEN, BLUE_TRAPS, RED_DEN, RED_TRAPS, WATER

from .core import BLUE, EMPTY, RED, CompactPosition, NEIGHBORS


FAST_TERMINAL_SCORE = 100_000
TABLEBASE_SCORE = 90_000

# Values are deliberately non-linear.  A rat retains extra strategic value while
# an opposing elephant exists, while lion/tiger jump mobility is reflected below.
PIECE_VALUES = (0, 145, 235, 320, 405, 510, 755, 825, 900)

TARGET_DEN = (RED_DEN, BLUE_DEN)
OWN_DEN = (BLUE_DEN, RED_DEN)
ENEMY_TRAPS = (RED_TRAPS, BLUE_TRAPS)
OWN_TRAPS = (BLUE_TRAPS, RED_TRAPS)

DEN_DISTANCE = tuple(
    tuple(
        abs(square // 7 - target // 7) + abs(square % 7 - target % 7)
        for square in range(63)
    )
    for target in TARGET_DEN
)
OWN_DEN_DISTANCE = tuple(
    tuple(
        abs(square // 7 - target // 7) + abs(square % 7 - target % 7)
        for square in range(63)
    )
    for target in OWN_DEN
)


def piece_side(code: int) -> int:
    return BLUE if code <= 8 else RED


def piece_kind(code: int) -> int:
    return code if code <= 8 else code - 8


def _effective_rank(position: CompactPosition, square: int, code: int) -> int:
    side = piece_side(code)
    if square in ENEMY_TRAPS[side]:
        return 0
    return piece_kind(code)


def _can_capture(position: CompactPosition, attacker_square: int, defender_square: int) -> bool:
    attacker = position.board[attacker_square]
    defender = position.board[defender_square]
    if attacker == EMPTY or defender == EMPTY or piece_side(attacker) == piece_side(defender):
        return False
    attacker_kind = piece_kind(attacker)
    defender_kind = piece_kind(defender)
    attacker_water = attacker_square in WATER
    defender_water = defender_square in WATER
    if attacker_kind == 1 and defender_kind == 8:
        return not attacker_water and not defender_water
    if attacker_kind == 8 and defender_kind == 1:
        return _effective_rank(position, defender_square, defender) == 0
    if attacker_water or defender_water:
        return attacker_water and defender_water and attacker_kind == defender_kind == 1
    return _effective_rank(position, attacker_square, attacker) >= _effective_rank(
        position, defender_square, defender
    )


def _square_is_enterable(side: int, kind: int, square: int) -> bool:
    if square == OWN_DEN[side]:
        return False
    return square not in WATER or kind == 1


def evaluate_compact(position: CompactPosition) -> int:
    """Evaluate from the side-to-move perspective without allocating moves."""

    scores = [0, 0]
    closest = [99, 99]
    attacks = [set(), set()]
    defenders = [set(), set()]
    mobility = [0, 0]
    elephants = [position.piece_counts[8], position.piece_counts[16]]

    for square, code in enumerate(position.board):
        if code == EMPTY:
            continue
        side = piece_side(code)
        kind = piece_kind(code)
        value = PIECE_VALUES[kind]
        if square in ENEMY_TRAPS[side]:
            value //= 3
        scores[side] += value

        distance = DEN_DISTANCE[side][square]
        closest[side] = min(closest[side], distance)
        scores[side] += (18 - distance) * 15
        if distance <= 3:
            scores[side] += (4 - distance) * (250 + (16 - position.total_piece_count) * 22)
        own_distance = OWN_DEN_DISTANCE[side][square]
        if own_distance <= 2:
            scores[side] += (3 - own_distance) * 65
        if square in ENEMY_TRAPS[side]:
            scores[side] += 310
        elif square in OWN_TRAPS[side]:
            scores[side] += 55
        if kind == 1:
            if square in WATER:
                scores[side] += 130
            if elephants[side ^ 1]:
                scores[side] += 75
        elif kind in (6, 7):
            # Jumpers are most useful when developed toward a river bank.
            row = square // 7
            if 2 <= row <= 6:
                scores[side] += 55

        for destination in NEIGHBORS[square]:
            target = position.board[destination]
            if target == EMPTY:
                if _square_is_enterable(side, kind, destination):
                    mobility[side] += 1
                continue
            if piece_side(target) == side:
                defenders[side].add(destination)
            elif _can_capture(position, square, destination):
                attacks[side].add(destination)
                mobility[side] += 1

    phase = max(0, 16 - position.total_piece_count)
    for side in (BLUE, RED):
        scores[side] += mobility[side] * (7 + phase // 3)
        if closest[side] < 99:
            scores[side] += (14 - closest[side]) * (18 + phase * 4)
        for target in attacks[side]:
            victim = position.board[target]
            victim_value = PIECE_VALUES[piece_kind(victim)]
            if target in defenders[side ^ 1]:
                scores[side] += victim_value // 12
            else:
                scores[side] += victim_value // 4

        enemy_close = closest[side ^ 1]
        if enemy_close <= 3:
            scores[side] -= (4 - enemy_close) * (300 + phase * 25)

    absolute = scores[BLUE] - scores[RED]
    # A small tempo term breaks symmetric zeroes without overwhelming real terms.
    absolute += 12 if position.side_to_move == BLUE else -12
    return absolute if position.side_to_move == BLUE else -absolute
