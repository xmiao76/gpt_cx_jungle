from __future__ import annotations

from dataclasses import dataclass

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
    Position,
    Side,
    neighbors,
)
from jungle.rules import legal_moves


TERMINAL_SCORE = 100_000

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


@dataclass(frozen=True, slots=True)
class EvaluationOptions:
    full: bool = False
    threat_weight: int = 0
    use_den_safety: bool = False
    use_den_race: bool = False
    repetition_penalty: int = 0


DEN_DISTANCE = {
    Side.BLUE: tuple(Position.from_index(index).manhattan_distance(Position.from_index(RED_DEN)) for index in range(63)),
    Side.RED: tuple(Position.from_index(index).manhattan_distance(Position.from_index(BLUE_DEN)) for index in range(63)),
}
OWN_DEN_DISTANCE = {
    Side.BLUE: tuple(Position.from_index(index).manhattan_distance(Position.from_index(BLUE_DEN)) for index in range(63)),
    Side.RED: tuple(Position.from_index(index).manhattan_distance(Position.from_index(RED_DEN)) for index in range(63)),
}


def evaluate_state(state: GameState, perspective: Side, options: EvaluationOptions) -> int:
    if state.winner is perspective:
        return TERMINAL_SCORE
    if state.winner is perspective.opponent:
        return -TERMINAL_SCORE

    moves = {Side.BLUE: [], Side.RED: []}
    if options.full:
        moves[Side.BLUE] = _moves_for(state, Side.BLUE)
        moves[Side.RED] = _moves_for(state, Side.RED)

    blue = _side_score(state, Side.BLUE, moves[Side.BLUE], options)
    red = _side_score(state, Side.RED, moves[Side.RED], options)
    score = blue - red
    return score if perspective is Side.BLUE else -score


def _moves_for(state: GameState, side: Side) -> list[Move]:
    if state.winner is not None:
        return []
    turn_state = state.copy()
    turn_state.side_to_move = side
    return legal_moves(turn_state)


def _side_score(state: GameState, side: Side, moves: list[Move], options: EvaluationOptions) -> int:
    pieces = [(index, piece) for index, piece in enumerate(state.board) if piece is not None and piece.side is side]
    score = sum(_piece_score(state, index, piece, options) for index, piece in pieces)
    if not options.full:
        return score

    score += len(moves) * 10
    score += _move_pressure_score(side, moves) * max(1, options.threat_weight)
    score += _defender_score(state, side)
    if options.use_den_safety:
        score += _den_safety_score(state, side)
    if options.use_den_race:
        score += _den_race_score(pieces, side)
    if options.repetition_penalty:
        score += _repetition_score(state, side, options.repetition_penalty)
    return score


def _piece_score(state: GameState, index: int, piece: Piece, options: EvaluationOptions) -> int:
    distance = DEN_DISTANCE[piece.side][index]
    own_distance = OWN_DEN_DISTANCE[piece.side][index]
    local = effective_material_value(state, index, piece) + (18 - distance) * 18
    if distance <= 2:
        local += (3 - distance) * 450
    elif options.threat_weight and distance <= 4:
        local += (5 - distance) * 140

    trap_owner = TRAP_OWNER.get(index)
    if trap_owner is piece.side.opponent:
        local += 380
    elif trap_owner is piece.side:
        local += 90
    if piece.kind is PieceType.RAT and index in WATER:
        local += 160
    if own_distance <= 2:
        local += (3 - own_distance) * 80
    return local


def effective_material_value(state: GameState, index: int, piece: Piece) -> int:
    if TRAP_OWNER.get(index) is piece.side.opponent:
        return PIECE_VALUES[piece.kind] // 2
    return PIECE_VALUES[piece.kind]


def _move_pressure_score(side: Side, moves: list[Move]) -> int:
    target_den = RED_DEN if side is Side.BLUE else BLUE_DEN
    target_traps = RED_TRAPS if side is Side.BLUE else BLUE_TRAPS
    score = 0
    for move in moves:
        if move.captured is not None:
            score += PIECE_VALUES[move.captured.kind] * 3
            if move.piece.kind is PieceType.RAT and move.captured.kind is PieceType.ELEPHANT:
                score += 1_200
        if move.destination == target_den:
            score += 35_000
        elif move.destination in target_traps:
            score += 900
        if move.is_jump:
            score += 120
    return score


def _defender_score(state: GameState, side: Side) -> int:
    score = 0
    for index, piece in enumerate(state.board):
        if piece is None or piece.side is not side:
            continue
        score += sum(
            24
            for adjacent in neighbors(index)
            if state.board[adjacent] is not None and state.board[adjacent].side is side
        )
    return score


def _den_safety_score(state: GameState, side: Side) -> int:
    own_distances = OWN_DEN_DISTANCE[side]
    score = 0
    own_traps = BLUE_TRAPS if side is Side.BLUE else RED_TRAPS
    for index, piece in enumerate(state.board):
        if piece is None or piece.side is side:
            continue
        distance = own_distances[index]
        if distance <= 3:
            score -= (4 - distance) * 650
        if index in own_traps:
            score -= 450
    return score


def _den_race_score(pieces: list[tuple[int, Piece]], side: Side) -> int:
    if not pieces:
        return -4_000
    distances = [DEN_DISTANCE[side][index] for index, _piece in pieces]
    closest = min(distances)
    score = (16 - closest) * 70
    if closest <= 3:
        score += (4 - closest) * 680
    score += sum((5 - distance) * 95 for distance in distances if distance <= 4)
    return score


def _repetition_score(state: GameState, side: Side, penalty: int) -> int:
    side_moves = [move for move in state.move_history if move.piece.side is side]
    if len(side_moves) < 2:
        return 0
    previous, latest = side_moves[-2], side_moves[-1]
    if previous.origin == latest.destination and previous.destination == latest.origin:
        return -penalty
    return 0
