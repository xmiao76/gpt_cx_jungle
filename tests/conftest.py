from __future__ import annotations

from jungle.domain import BOARD_SIZE, GameState, Piece, PieceType, Side


def make_state(pieces: dict[int, Piece], side_to_move: Side = Side.BLUE) -> GameState:
    board = [None] * BOARD_SIZE
    for index, piece in pieces.items():
        board[index] = piece
    return GameState(board=board, side_to_move=side_to_move)


def piece(side: Side, kind: PieceType) -> Piece:
    return Piece(side, kind)
