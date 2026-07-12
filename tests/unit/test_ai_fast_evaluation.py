from __future__ import annotations

from jungle.ai.core import CompactPosition
from jungle.ai.fast_evaluation import evaluate_compact
from jungle.domain import GameState, Piece, PieceType, Position, Side


def make_state(pieces: dict[int, Piece], side: Side = Side.BLUE) -> GameState:
    board = [None] * 63
    for square, piece in pieces.items():
        board[square] = piece
    return GameState(board, side)


def test_compact_evaluation_rewards_material() -> None:
    state = make_state(
        {
            Position(6, 0).index: Piece(Side.BLUE, PieceType.ELEPHANT),
            Position(2, 6).index: Piece(Side.RED, PieceType.CAT),
        }
    )

    assert evaluate_compact(CompactPosition.from_game_state(state)) > 0


def test_compact_evaluation_changes_perspective_with_turn() -> None:
    pieces = {
        Position(6, 0).index: Piece(Side.BLUE, PieceType.ELEPHANT),
        Position(2, 6).index: Piece(Side.RED, PieceType.CAT),
    }
    blue = CompactPosition.from_game_state(make_state(pieces, Side.BLUE))
    red = CompactPosition.from_game_state(make_state(pieces, Side.RED))

    # Tempo belongs to the mover, so removing it leaves exact antisymmetry.
    assert evaluate_compact(blue) - 12 == -(evaluate_compact(red) - 12)
