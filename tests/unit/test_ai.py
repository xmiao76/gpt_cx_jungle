from __future__ import annotations

from jungle.ai import AlphaBetaAI
from jungle.domain import Piece, PieceType, Position, Side
from jungle.engine import Game


def make_state(pieces, side_to_move=Side.BLUE):
    from jungle.domain import GameState

    board = [None] * 63
    for index, piece in pieces.items():
        board[index] = piece
    return GameState(board=board, side_to_move=side_to_move)


def test_ai_returns_a_move_from_initial_position() -> None:
    game = Game()
    ai = AlphaBetaAI(80)
    result = ai.choose_move(game.state)
    assert result.move is not None


def test_ai_prefers_den_entry_when_available() -> None:
    blue_cat = Position(1, 3).index
    state = make_state(
        {
            blue_cat: Piece(Side.BLUE, PieceType.CAT),
            Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
        }
    )
    ai = AlphaBetaAI(80)
    result = ai.choose_move(state)
    assert result.move is not None
    assert result.move.destination == Position(0, 3).index
