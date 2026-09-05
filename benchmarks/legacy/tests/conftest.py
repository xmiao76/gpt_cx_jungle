from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from jungle.domain import BOARD_SIZE, GameState, Piece, PieceType, Side


def make_state(pieces: dict[int, Piece], side_to_move: Side = Side.BLUE) -> GameState:
    board = [None] * BOARD_SIZE
    for index, piece in pieces.items():
        board[index] = piece
    return GameState(board=board, side_to_move=side_to_move)


def piece(side: Side, kind: PieceType) -> Piece:
    return Piece(side, kind)


def load_tool_module(module_name: str):
    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    module_path = root / "tools" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"test_tools_{module_name}", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
