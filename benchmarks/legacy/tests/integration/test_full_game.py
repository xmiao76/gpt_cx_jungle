from __future__ import annotations

from jungle.ai import AlphaBetaAI
from jungle.engine import Game
from jungle.domain import Side


def test_ai_self_play_finishes_without_illegal_moves() -> None:
    game = Game()
    blue_ai = AlphaBetaAI(30)
    red_ai = AlphaBetaAI(30)

    for _ in range(160):
        if game.state.winner is not None:
            break
        ai = blue_ai if game.state.side_to_move is Side.BLUE else red_ai
        result = ai.choose_move(game.state)
        assert result.move is not None
        game.apply_move(result.move)

    assert len(game.state.move_history) > 0
    assert game.state.winner is not None or len(game.state.move_history) == 160
