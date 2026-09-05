from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "src" / "jungle" / "ui" / "assets"
CELL = 72
BOARD_W = CELL * 7
BOARD_H = CELL * 9
PIECE = 96


SIDE_COLORS = {
    "blue": ("#2c77ff", "#0f3ea8"),
    "red": ("#e84848", "#9c1515"),
}
ANIMALS = [
    "rat",
    "cat",
    "dog",
    "wolf",
    "leopard",
    "tiger",
    "lion",
    "elephant",
]


def ensure_dir() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)


def save(img: Image.Image, name: str) -> None:
    img.save(ASSET_DIR / name)


def vertical_gradient(size: tuple[int, int], top: str, bottom: str) -> Image.Image:
    width, height = size
    base = Image.new("RGBA", size)
    draw = ImageDraw.Draw(base)
    tr, tg, tb = tuple(int(top[i : i + 2], 16) for i in (1, 3, 5))
    br, bg, bb = tuple(int(bottom[i : i + 2], 16) for i in (1, 3, 5))
    for y in range(height):
        t = y / max(1, height - 1)
        color = (
            int(tr * (1 - t) + br * t),
            int(tg * (1 - t) + bg * t),
            int(tb * (1 - t) + bb * t),
            255,
        )
        draw.line((0, y, width, y), fill=color)
    return base


def add_noise_lines(img: Image.Image, color: str, count: int, alpha: int = 70) -> None:
    draw = ImageDraw.Draw(img)
    rgba = tuple(int(color[i : i + 2], 16) for i in (1, 3, 5)) + (alpha,)
    width, height = img.size
    for i in range(count):
        x1 = (i * 37) % width
        y1 = (i * 53) % height
        x2 = min(width, x1 + 18 + (i % 11) * 3)
        y2 = min(height, y1 + 4 + (i % 7) * 3)
        draw.arc((x1, y1, x2, y2), start=0, end=180, fill=rgba, width=1)


def generate_board_background() -> None:
    img = vertical_gradient((BOARD_W, BOARD_H), "#7d5d2d", "#3d2814")
    add_noise_lines(img, "#f6cf73", 200, alpha=36)
    draw = ImageDraw.Draw(img, "RGBA")
    for x in range(0, BOARD_W, CELL):
        draw.rectangle((x, 0, x + 2, BOARD_H), fill=(67, 42, 15, 100))
    for y in range(0, BOARD_H, CELL):
        draw.rectangle((0, y, BOARD_W, y + 2), fill=(67, 42, 15, 100))
    vignette = Image.new("RGBA", (BOARD_W, BOARD_H), (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette, "RGBA")
    for i in range(18):
        alpha = int(6 + i * 3)
        vdraw.rounded_rectangle((i * 2, i * 2, BOARD_W - i * 2, BOARD_H - i * 2), radius=18, outline=(0, 0, 0, alpha), width=3)
    img.alpha_composite(vignette)
    save(img, "board_background.png")


def generate_land_tile() -> None:
    img = vertical_gradient((CELL, CELL), "#ad8b4d", "#805e2d")
    add_noise_lines(img, "#ebd08a", 16, alpha=60)
    draw = ImageDraw.Draw(img, "RGBA")
    for y in (14, 34, 52):
        draw.arc((8, y - 6, 64, y + 10), start=0, end=180, fill=(77, 109, 38, 120), width=2)
    save(img, "land_tile.png")


def generate_river_tile() -> None:
    img = vertical_gradient((CELL, CELL), "#87d8ef", "#1c82c9")
    draw = ImageDraw.Draw(img, "RGBA")
    for y in range(8, CELL, 14):
        draw.arc((2, y, CELL - 2, y + 12), start=0, end=180, fill=(255, 255, 255, 90), width=3)
    for x in (8, 40):
        draw.ellipse((x, 8, x + 12, 20), fill=(227, 249, 255, 70))
    save(img, "river_tile.png")


def generate_trap_tile(name: str, ring: str, glow: str) -> None:
    img = vertical_gradient((CELL, CELL), "#83633a", "#5e4322")
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rounded_rectangle((6, 6, CELL - 6, CELL - 6), radius=10, fill=(48, 33, 18, 130), outline=ring, width=3)
    for i in range(4):
        inset = 12 + i * 4
        draw.rounded_rectangle((inset, inset, CELL - inset, CELL - inset), radius=8, outline=glow, width=2)
    draw.line((22, 22, CELL - 22, CELL - 22), fill=(255, 220, 150, 160), width=4)
    draw.line((CELL - 22, 22, 22, CELL - 22), fill=(255, 220, 150, 160), width=4)
    save(img, name)


def generate_den_tile(name: str, ring: str, fill_color: str) -> None:
    img = vertical_gradient((CELL, CELL), "#8a6a35", "#60431d")
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rounded_rectangle((6, 6, CELL - 6, CELL - 6), radius=12, fill=(0, 0, 0, 50), outline=ring, width=3)
    draw.ellipse((16, 18, CELL - 16, CELL - 18), fill=fill_color, outline=(255, 237, 195, 180), width=2)
    draw.polygon(((CELL / 2, 20), (CELL - 22, 44), (CELL / 2, CELL - 16), (22, 44)), fill=(255, 249, 220, 65))
    save(img, name)


def draw_face(draw: ImageDraw.ImageDraw, animal: str, colors: tuple[str, str]) -> None:
    fur, detail = colors
    outline = "#1f140d"
    draw.ellipse((20, 18, 76, 78), fill=fur, outline=outline, width=3)
    if animal in {"cat", "lion", "tiger", "wolf", "leopard"}:
        draw.polygon(((28, 24), (40, 6), (46, 28)), fill=fur, outline=outline)
        draw.polygon(((68, 24), (56, 6), (50, 28)), fill=fur, outline=outline)
    if animal == "dog":
        draw.ellipse((16, 24, 34, 52), fill=detail, outline=outline)
        draw.ellipse((62, 24, 80, 52), fill=detail, outline=outline)
    if animal == "elephant":
        draw.ellipse((24, 24, 40, 52), fill="#efddc6", outline=outline)
        draw.ellipse((56, 24, 72, 52), fill="#efddc6", outline=outline)
        draw.rounded_rectangle((42, 44, 54, 82), radius=6, fill=detail, outline=outline, width=2)
    if animal == "rat":
        draw.ellipse((24, 16, 42, 34), fill="#f2d6c8", outline=outline)
        draw.ellipse((54, 16, 72, 34), fill="#f2d6c8", outline=outline)
        draw.arc((68, 60, 96, 96), start=160, end=320, fill="#e6a2a8", width=3)
    if animal == "lion":
        draw.ellipse((10, 10, 86, 86), outline="#7c4a19", width=10)
    if animal == "tiger":
        for x in (28, 42, 56, 70):
            draw.line((x, 20, x - 6, 46), fill=detail, width=4)
    if animal == "leopard":
        for x, y in ((28, 26), (58, 24), (35, 46), (58, 50)):
            draw.ellipse((x, y, x + 8, y + 8), fill=detail)
    if animal == "wolf":
        draw.polygon(((22, 54), (30, 34), (48, 28), (66, 34), (74, 54), (48, 72)), outline=detail, width=3)
    eye_fill = "#1a120d"
    draw.ellipse((34, 40, 40, 46), fill=eye_fill)
    draw.ellipse((56, 40, 62, 46), fill=eye_fill)
    draw.ellipse((44, 50, 52, 58), fill=detail, outline=outline)
    draw.arc((36, 52, 60, 68), start=10, end=170, fill=outline, width=2)
    if animal == "cat":
        draw.line((30, 54, 18, 52), fill=outline, width=2)
        draw.line((30, 58, 16, 60), fill=outline, width=2)
        draw.line((66, 54, 78, 52), fill=outline, width=2)
        draw.line((66, 58, 80, 60), fill=outline, width=2)
    if animal in {"dog", "wolf"}:
        draw.arc((36, 54, 60, 72), start=0, end=180, fill=outline, width=2)


def piece_colors(animal: str) -> tuple[str, str]:
    mapping = {
        "rat": ("#b9b3c7", "#7f748e"),
        "cat": ("#d6c6ac", "#8f6e42"),
        "dog": ("#c79e6f", "#6f4c2d"),
        "wolf": ("#aeb4bb", "#5a6470"),
        "leopard": ("#edb45d", "#5d4121"),
        "tiger": ("#f39a33", "#3f2313"),
        "lion": ("#d8a44a", "#8f5e20"),
        "elephant": ("#9aa9b6", "#67798c"),
    }
    return mapping[animal]


def generate_piece(side: str, animal: str) -> None:
    img = Image.new("RGBA", (PIECE, PIECE), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (PIECE, PIECE), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow, "RGBA")
    sdraw.ellipse((14, 20, 88, 92), fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(6))
    img.alpha_composite(shadow)

    ring, ring_dark = SIDE_COLORS[side]
    draw = ImageDraw.Draw(img, "RGBA")
    draw.ellipse((14, 10, 82, 78), fill=(245, 237, 220, 255), outline=ring_dark, width=4)
    draw.ellipse((8, 4, 88, 84), outline=ring, width=8)
    draw.rounded_rectangle((28, 68, 68, 90), radius=10, fill=ring_dark, outline="#f4efe3", width=2)

    draw_face(draw, animal, piece_colors(animal))
    rank_map = {
        "rat": "1",
        "cat": "2",
        "dog": "3",
        "wolf": "4",
        "leopard": "5",
        "tiger": "6",
        "lion": "7",
        "elephant": "8",
    }
    draw.text((44, 70), rank_map[animal], anchor="mm", fill="#fff9ee")
    draw.text((48, 86), animal[:3].upper(), anchor="mm", fill="#fdf6e8")
    save(img, f"{side}_{animal}.png")


def main() -> None:
    ensure_dir()
    generate_board_background()
    generate_land_tile()
    generate_river_tile()
    generate_trap_tile("blue_trap_tile.png", "#8ed2ff", "#d8f5ff")
    generate_trap_tile("red_trap_tile.png", "#ff9a8f", "#ffe5dc")
    generate_den_tile("blue_den_tile.png", "#95d6ff", "#3d6ed1")
    generate_den_tile("red_den_tile.png", "#ff9c8e", "#c54836")
    for side in ("blue", "red"):
        for animal in ANIMALS:
            generate_piece(side, animal)


if __name__ == "__main__":
    main()
