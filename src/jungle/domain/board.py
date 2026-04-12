from __future__ import annotations

from jungle.domain.types import (
    BOARD_COLS,
    BOARD_ROWS,
    BOARD_SIZE,
    GameState,
    Piece,
    PieceType,
    Position,
    Side,
    Terrain,
)


BLUE_DEN = Position(8, 3).index
RED_DEN = Position(0, 3).index
BLUE_TRAPS = {Position(8, 2).index, Position(8, 4).index, Position(7, 3).index}
RED_TRAPS = {Position(0, 2).index, Position(0, 4).index, Position(1, 3).index}
WATER = {
    Position(3, 1).index,
    Position(3, 2).index,
    Position(4, 1).index,
    Position(4, 2).index,
    Position(5, 1).index,
    Position(5, 2).index,
    Position(3, 4).index,
    Position(3, 5).index,
    Position(4, 4).index,
    Position(4, 5).index,
    Position(5, 4).index,
    Position(5, 5).index,
}
DEN_OWNER = {BLUE_DEN: Side.BLUE, RED_DEN: Side.RED}
TRAP_OWNER = {index: Side.BLUE for index in BLUE_TRAPS} | {index: Side.RED for index in RED_TRAPS}


def in_bounds(row: int, col: int) -> bool:
    return 0 <= row < BOARD_ROWS and 0 <= col < BOARD_COLS


def terrain_at(index: int) -> Terrain:
    if index in WATER:
        return Terrain.WATER
    if index in DEN_OWNER:
        return Terrain.DEN
    if index in TRAP_OWNER:
        return Terrain.TRAP
    return Terrain.LAND


def neighbors(index: int) -> list[int]:
    pos = Position.from_index(index)
    values: list[int] = []
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        row = pos.row + dr
        col = pos.col + dc
        if in_bounds(row, col):
            values.append(Position(row, col).index)
    return values


def river_path(origin: int, destination: int) -> list[int]:
    a = Position.from_index(origin)
    b = Position.from_index(destination)
    path: list[int] = []
    if a.row == b.row:
        step = 1 if b.col > a.col else -1
        for col in range(a.col + step, b.col, step):
            idx = Position(a.row, col).index
            if idx in WATER:
                path.append(idx)
    elif a.col == b.col:
        step = 1 if b.row > a.row else -1
        for row in range(a.row + step, b.row, step):
            idx = Position(row, a.col).index
            if idx in WATER:
                path.append(idx)
    return path


INITIAL_PIECES: dict[int, Piece] = {
    Position(6, 0).index: Piece(Side.BLUE, PieceType.LION),
    Position(8, 6).index: Piece(Side.BLUE, PieceType.TIGER),
    Position(6, 2).index: Piece(Side.BLUE, PieceType.DOG),
    Position(6, 4).index: Piece(Side.BLUE, PieceType.CAT),
    Position(8, 0).index: Piece(Side.BLUE, PieceType.ELEPHANT),
    Position(8, 2).index: Piece(Side.BLUE, PieceType.WOLF),
    Position(8, 4).index: Piece(Side.BLUE, PieceType.LEOPARD),
    Position(6, 6).index: Piece(Side.BLUE, PieceType.RAT),
    Position(2, 6).index: Piece(Side.RED, PieceType.LION),
    Position(0, 0).index: Piece(Side.RED, PieceType.TIGER),
    Position(2, 4).index: Piece(Side.RED, PieceType.DOG),
    Position(2, 2).index: Piece(Side.RED, PieceType.CAT),
    Position(0, 6).index: Piece(Side.RED, PieceType.ELEPHANT),
    Position(0, 4).index: Piece(Side.RED, PieceType.WOLF),
    Position(0, 2).index: Piece(Side.RED, PieceType.LEOPARD),
    Position(2, 0).index: Piece(Side.RED, PieceType.RAT),
}


def initial_state() -> GameState:
    board: list[Piece | None] = [None] * BOARD_SIZE
    for index, piece in INITIAL_PIECES.items():
        board[index] = piece
    return GameState(board=board, side_to_move=Side.BLUE)
