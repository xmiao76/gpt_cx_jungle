from __future__ import annotations

from jungle.domain import (
    BLUE_DEN,
    DEN_OWNER,
    RED_DEN,
    TRAP_OWNER,
    WATER,
    GameResult,
    GameState,
    Move,
    Piece,
    PieceType,
    Position,
    ResultType,
    Side,
    neighbors,
    river_path,
    terrain_at,
)


JUMPERS = {PieceType.LION, PieceType.TIGER}


def effective_rank(state: GameState, index: int, piece: Piece | None = None) -> int:
    occupant = state.board[index] if piece is None else piece
    if occupant is None:
        return 0
    trap_owner = TRAP_OWNER.get(index)
    if trap_owner is not None and trap_owner is occupant.side.opponent:
        return 0
    return occupant.rank


def same_terrain_family(origin: int, destination: int) -> bool:
    return (origin in WATER) == (destination in WATER)


def can_capture(state: GameState, attacker_index: int, defender_index: int) -> bool:
    attacker = state.board[attacker_index]
    defender = state.board[defender_index]
    if attacker is None or defender is None or attacker.side is defender.side:
        return False

    attacker_in_water = attacker_index in WATER
    defender_in_water = defender_index in WATER

    if attacker.kind is PieceType.RAT and defender.kind is PieceType.ELEPHANT:
        return not attacker_in_water and not defender_in_water

    if attacker.kind is PieceType.ELEPHANT and defender.kind is PieceType.RAT:
        return False

    if attacker_in_water or defender_in_water:
        if not attacker_in_water or not defender_in_water:
            return False
        return attacker.kind is PieceType.RAT and defender.kind is PieceType.RAT

    return effective_rank(state, attacker_index, attacker) >= effective_rank(state, defender_index, defender)


def is_legal_step(piece: Piece, destination: int) -> bool:
    terrain = terrain_at(destination)
    if terrain.value == "water":
        return piece.kind is PieceType.RAT
    if destination in DEN_OWNER and DEN_OWNER[destination] is piece.side:
        return False
    return True


def generate_piece_moves(state: GameState, origin: int) -> list[Move]:
    piece = state.board[origin]
    if piece is None or piece.side is not state.side_to_move:
        return []

    moves: list[Move] = []
    for destination in neighbors(origin):
        if not is_legal_step(piece, destination):
            continue
        target = state.board[destination]
        if target is None:
            moves.append(Move(origin=origin, destination=destination, piece=piece))
            continue
        if target.side is piece.side:
            continue
        if can_capture(state, origin, destination):
            moves.append(Move(origin=origin, destination=destination, piece=piece, captured=target))

    if piece.kind in JUMPERS:
        moves.extend(generate_jump_moves(state, origin, piece))
    return moves


def generate_jump_moves(state: GameState, origin: int, piece: Piece) -> list[Move]:
    moves: list[Move] = []
    row, col = Position.from_index(origin).row, Position.from_index(origin).col
    directions = ((1, 0), (-1, 0), (0, 1), (0, -1))
    for dr, dc in directions:
        next_row = row + dr
        next_col = col + dc
        if not (0 <= next_row < 9 and 0 <= next_col < 7):
            continue
        next_index = Position(next_row, next_col).index
        if next_index not in WATER:
            continue
        landing_row = next_row
        landing_col = next_col
        while 0 <= landing_row < 9 and 0 <= landing_col < 7 and Position(landing_row, landing_col).index in WATER:
            landing_row += dr
            landing_col += dc
        if not (0 <= landing_row < 9 and 0 <= landing_col < 7):
            continue
        landing = Position(landing_row, landing_col).index
        if landing in DEN_OWNER and DEN_OWNER[landing] is piece.side:
            continue
        path = river_path(origin, landing)
        if not path:
            continue
        if any(state.board[idx] is not None and state.board[idx].kind is PieceType.RAT for idx in path):
            continue
        target = state.board[landing]
        if target is None:
            moves.append(Move(origin=origin, destination=landing, piece=piece, is_jump=True, note="jump"))
            continue
        if target.side is piece.side:
            continue
        if can_capture(state, origin, landing):
            moves.append(
                Move(
                    origin=origin,
                    destination=landing,
                    piece=piece,
                    captured=target,
                    is_jump=True,
                    note="jump-capture",
                )
            )
    return moves


def legal_moves(state: GameState) -> list[Move]:
    if state.result is not ResultType.ONGOING:
        return []
    moves: list[Move] = []
    for index, piece in enumerate(state.board):
        if piece is not None and piece.side is state.side_to_move:
            moves.extend(generate_piece_moves(state, index))
    return moves


def find_legal_move(state: GameState, origin: int, destination: int) -> Move | None:
    for move in generate_piece_moves(state, origin):
        if move.destination == destination:
            return move
    return None


def evaluate_result(state: GameState) -> GameResult:
    if state.board[RED_DEN] is not None and state.board[RED_DEN].side is Side.BLUE:
        return GameResult(ResultType.DEN_ENTRY, Side.BLUE, "Blue entered the red den.")
    if state.board[BLUE_DEN] is not None and state.board[BLUE_DEN].side is Side.RED:
        return GameResult(ResultType.DEN_ENTRY, Side.RED, "Red entered the blue den.")

    blue_alive = any(piece is not None and piece.side is Side.BLUE for piece in state.board)
    red_alive = any(piece is not None and piece.side is Side.RED for piece in state.board)
    if not blue_alive:
        return GameResult(ResultType.CAPTURE_ALL, Side.RED, "Red captured all blue pieces.")
    if not red_alive:
        return GameResult(ResultType.CAPTURE_ALL, Side.BLUE, "Blue captured all red pieces.")

    if not legal_moves(state):
        return GameResult(ResultType.NO_LEGAL_MOVES, state.side_to_move.opponent, "No legal moves remain.")
    return GameResult()
