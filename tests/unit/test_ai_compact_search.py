from __future__ import annotations

from jungle.ai import AlphaBetaAI, SearchConfig
from jungle.ai.tablebase import load_default_tablebase
from jungle.domain import GameState, Piece, PieceType, Position, Side
from jungle.engine import Game


def make_state(pieces: dict[int, Piece], side: Side = Side.BLUE) -> GameState:
    board = [None] * 63
    for square, piece in pieces.items():
        board[square] = piece
    return GameState(board, side)


def test_hard_search_uses_exact_two_piece_tablebase() -> None:
    state = make_state(
        {
            Position(4, 0).index: Piece(Side.BLUE, PieceType.CAT),
            Position(4, 6).index: Piece(Side.RED, PieceType.DOG),
        }
    )
    tablebase = load_default_tablebase()
    assert tablebase is not None

    result = AlphaBetaAI(300, SearchConfig.hard()).choose_move(state)

    assert result.move == tablebase.choose_move(state)
    assert result.tablebase_hits > 0
    assert result.depth == 0


def test_hard_search_returns_legal_principal_variation_and_diagnostics() -> None:
    game = Game()

    result = AlphaBetaAI(10_000, SearchConfig.hard(), node_limit=2_000).choose_move(game.state)

    assert result.move in game.list_moves()
    assert result.principal_variation
    replay = Game(game.state)
    for move in result.principal_variation:
        assert move in replay.list_moves()
        replay.apply_move(move)
    assert result.nodes_per_second > 0
    assert result.tt_hits > 0


def test_hard_search_falls_back_when_tablebase_is_unavailable(monkeypatch) -> None:
    import jungle.ai.tablebase as tablebase_module

    state = make_state(
        {
            Position(4, 0).index: Piece(Side.BLUE, PieceType.CAT),
            Position(4, 6).index: Piece(Side.RED, PieceType.DOG),
        }
    )
    tablebase_module.load_default_tablebase.cache_clear()
    monkeypatch.setattr(tablebase_module, "load_default_tablebase", lambda: None)

    result = AlphaBetaAI(80, SearchConfig.hard()).choose_move(state)

    assert result.move is not None
    assert result.tablebase_hits == 0
