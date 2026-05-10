from __future__ import annotations

from jungle.ai import AlphaBetaAI
from jungle.engine import Game


def test_default_ai_can_play_twenty_plies_responsively() -> None:
    game = Game()
    elapsed_total = 0.0

    for _ in range(20):
        result = AlphaBetaAI(120).choose_move(game.state)
        assert result.move is not None
        assert result.elapsed_ms <= 180
        elapsed_total += result.elapsed_ms
        game.apply_move(result.move)
        if game.state.winner is not None:
            break

    assert elapsed_total <= 3600
    assert len(game.state.move_history) >= 10
