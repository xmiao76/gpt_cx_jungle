from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

from jungle.domain import PieceType, Side
from jungle.ui.theme import SUPPORTED_ASSET_SCALES


ASSET_DIRNAME = "assets"
BOARD_ASSETS = {
    "board_background": "board_background.png",
    "land_tile": "land_tile.png",
    "river_tile": "river_tile.png",
    "blue_trap_tile": "blue_trap_tile.png",
    "red_trap_tile": "red_trap_tile.png",
    "blue_den_tile": "blue_den_tile.png",
    "red_den_tile": "red_den_tile.png",
}
PIECE_ASSETS = {
    (Side.BLUE, PieceType.RAT): "blue_rat.png",
    (Side.BLUE, PieceType.CAT): "blue_cat.png",
    (Side.BLUE, PieceType.DOG): "blue_dog.png",
    (Side.BLUE, PieceType.WOLF): "blue_wolf.png",
    (Side.BLUE, PieceType.LEOPARD): "blue_leopard.png",
    (Side.BLUE, PieceType.TIGER): "blue_tiger.png",
    (Side.BLUE, PieceType.LION): "blue_lion.png",
    (Side.BLUE, PieceType.ELEPHANT): "blue_elephant.png",
    (Side.RED, PieceType.RAT): "red_rat.png",
    (Side.RED, PieceType.CAT): "red_cat.png",
    (Side.RED, PieceType.DOG): "red_dog.png",
    (Side.RED, PieceType.WOLF): "red_wolf.png",
    (Side.RED, PieceType.LEOPARD): "red_leopard.png",
    (Side.RED, PieceType.TIGER): "red_tiger.png",
    (Side.RED, PieceType.LION): "red_lion.png",
    (Side.RED, PieceType.ELEPHANT): "red_elephant.png",
}


def asset_base_path() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "jungle" / "ui" / ASSET_DIRNAME
    return Path(__file__).resolve().parent / ASSET_DIRNAME


def required_asset_paths() -> list[Path]:
    base = asset_base_path()
    names = list(BOARD_ASSETS.values()) + list(PIECE_ASSETS.values())
    return [base / name for name in names]


class AssetLoader:
    def __init__(self) -> None:
        self.base_path = asset_base_path()
        self._base_cache: dict[str, tk.PhotoImage] = {}
        self._scaled_cache: dict[tuple[str, tuple[int, int]], tk.PhotoImage] = {}

    def path_for(self, filename: str) -> Path:
        return self.base_path / filename

    def _base_image(self, filename: str) -> tk.PhotoImage:
        if filename not in self._base_cache:
            path = self.path_for(filename)
            if not path.exists():
                raise FileNotFoundError(f"Missing UI asset: {path}")
            self._base_cache[filename] = tk.PhotoImage(file=str(path))
        return self._base_cache[filename]

    def image(self, filename: str, scale_key: tuple[int, int] = (1, 1)) -> tk.PhotoImage:
        cache_key = (filename, scale_key)
        if cache_key not in self._scaled_cache:
            base_image = self._base_image(filename)
            self._scaled_cache[cache_key] = scale_image(base_image, scale_key)
        return self._scaled_cache[cache_key]

    def board(self, name: str, scale_key: tuple[int, int] = (1, 1)) -> tk.PhotoImage:
        return self.image(BOARD_ASSETS[name], scale_key)

    def piece(self, side: Side, kind: PieceType, scale_key: tuple[int, int] = (1, 1)) -> tk.PhotoImage:
        return self.image(PIECE_ASSETS[(side, kind)], scale_key)


def scale_image(image: tk.PhotoImage, scale_key: tuple[int, int]) -> tk.PhotoImage:
    if scale_key not in SUPPORTED_ASSET_SCALES:
        raise ValueError(f"Unsupported asset scale: {scale_key}")
    numerator, denominator = scale_key
    if numerator == denominator:
        return image
    return image.zoom(numerator, numerator).subsample(denominator, denominator)
