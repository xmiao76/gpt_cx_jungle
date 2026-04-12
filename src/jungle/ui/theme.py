from __future__ import annotations

from dataclasses import dataclass


CELL = 72
MARGIN = 18
BOARD_WIDTH = CELL * 7
BOARD_HEIGHT = CELL * 9
CANVAS_WIDTH = BOARD_WIDTH + MARGIN * 2
CANVAS_HEIGHT = BOARD_HEIGHT + MARGIN * 2
PIECE_SIZE = 60
LAND_INSET = 2


@dataclass(frozen=True, slots=True)
class Palette:
    app_bg: str = "#10281c"
    panel_bg: str = "#1d3f2c"
    panel_card: str = "#e9dec0"
    panel_text: str = "#1f1d16"
    accent: str = "#f0b43a"
    selected: str = "#ffcc44"
    legal_move: str = "#7be07b"
    legal_capture: str = "#ff7b6b"
    grid: str = "#4f3418"
    shadow: str = "#000000"


PALETTE = Palette()
