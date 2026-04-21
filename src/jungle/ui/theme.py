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
SUPPORTED_ASSET_SCALES: tuple[tuple[int, int], ...] = ((1, 1), (5, 6), (3, 4), (2, 3))


@dataclass(frozen=True, slots=True)
class WindowMetrics:
    scale_key: tuple[int, int]
    cell: int
    margin: int
    board_width: int
    board_height: int
    canvas_width: int
    canvas_height: int
    startup_width: int
    startup_height: int
    min_width: int
    min_height: int
    side_panel_width: int
    history_height: int
    diagnostics_height: int
    wraplength: int
    text_width: int
    root_padding: int
    side_padding: int
    diagnostics_collapsed: bool


@dataclass(frozen=True, slots=True)
class ScaleProfile:
    scale_key: tuple[int, int]
    side_panel_width: int
    history_height: int
    diagnostics_height: int
    wraplength: int
    text_width: int
    root_padding: int
    side_padding: int
    diagnostics_collapsed: bool
    preferred_width: int
    preferred_height: int


PROFILE_SPECS: tuple[ScaleProfile, ...] = (
    ScaleProfile((1, 1), 320, 18, 10, 290, 34, 18, 18, False, 1160, 810),
    ScaleProfile((5, 6), 290, 10, 6, 230, 28, 14, 12, True, 1000, 700),
    ScaleProfile((3, 4), 280, 8, 4, 210, 26, 10, 12, True, 940, 660),
    ScaleProfile((2, 3), 260, 8, 4, 200, 26, 8, 10, True, 860, 600),
)


def scale_value(value: int, scale_key: tuple[int, int]) -> int:
    numerator, denominator = scale_key
    return max(1, round(value * numerator / denominator))


def profile_for_scale(scale_key: tuple[int, int]) -> ScaleProfile:
    for profile in PROFILE_SPECS:
        if profile.scale_key == scale_key:
            return profile
    raise KeyError(f"Unsupported scale key: {scale_key}")


def _estimate_side_panel_height(profile: ScaleProfile) -> int:
    base_height = 240
    diagnostics_height = 34 if profile.diagnostics_collapsed else profile.diagnostics_height * 18
    return base_height + profile.history_height * 18 + diagnostics_height + profile.side_padding * 2


def metrics_for_scale(scale_key: tuple[int, int]) -> WindowMetrics:
    profile = profile_for_scale(scale_key)
    cell = scale_value(CELL, scale_key)
    margin = scale_value(MARGIN, scale_key)
    board_width = cell * 7
    board_height = cell * 9
    canvas_width = board_width + margin * 2
    canvas_height = board_height + margin * 2
    required_width = canvas_width + profile.side_panel_width + profile.root_padding * 4
    required_height = max(canvas_height + profile.root_padding * 2, _estimate_side_panel_height(profile))
    startup_width = max(required_width, profile.preferred_width)
    startup_height = max(required_height, profile.preferred_height)
    return WindowMetrics(
        scale_key=scale_key,
        cell=cell,
        margin=margin,
        board_width=board_width,
        board_height=board_height,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        startup_width=startup_width,
        startup_height=startup_height,
        min_width=required_width,
        min_height=required_height,
        side_panel_width=profile.side_panel_width,
        history_height=profile.history_height,
        diagnostics_height=profile.diagnostics_height,
        wraplength=profile.wraplength,
        text_width=profile.text_width,
        root_padding=profile.root_padding,
        side_padding=profile.side_padding,
        diagnostics_collapsed=profile.diagnostics_collapsed,
    )


def select_window_metrics(window_width: int, window_height: int) -> WindowMetrics:
    for scale_key in SUPPORTED_ASSET_SCALES:
        metrics = metrics_for_scale(scale_key)
        if metrics.min_width <= window_width and metrics.min_height <= window_height:
            return metrics
    return metrics_for_scale(SUPPORTED_ASSET_SCALES[-1])


def compute_window_metrics(screen_width: int, screen_height: int) -> WindowMetrics:
    available_width = max(800, screen_width - 86)
    available_height = max(560, screen_height - 88)
    startup_metrics = select_window_metrics(available_width, available_height)
    minimum_metrics = metrics_for_scale(SUPPORTED_ASSET_SCALES[-1])
    return WindowMetrics(
        scale_key=startup_metrics.scale_key,
        cell=startup_metrics.cell,
        margin=startup_metrics.margin,
        board_width=startup_metrics.board_width,
        board_height=startup_metrics.board_height,
        canvas_width=startup_metrics.canvas_width,
        canvas_height=startup_metrics.canvas_height,
        startup_width=min(available_width, startup_metrics.startup_width),
        startup_height=min(available_height, startup_metrics.startup_height),
        min_width=minimum_metrics.min_width,
        min_height=minimum_metrics.min_height,
        side_panel_width=startup_metrics.side_panel_width,
        history_height=startup_metrics.history_height,
        diagnostics_height=startup_metrics.diagnostics_height,
        wraplength=startup_metrics.wraplength,
        text_width=startup_metrics.text_width,
        root_padding=startup_metrics.root_padding,
        side_padding=startup_metrics.side_padding,
        diagnostics_collapsed=startup_metrics.diagnostics_collapsed,
    )


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
