from __future__ import annotations

from types import SimpleNamespace

from jungle.domain import Position, Side
from jungle.ui.app import (
    JungleApp,
    board_index_from_canvas_point,
    canvas_origin_for_index,
    orient_position,
)
from jungle.ui.theme import compute_window_metrics, select_window_metrics


def test_orient_position_flips_across_board_center() -> None:
    assert orient_position(Position(0, 0), False) == Position(0, 0)
    assert orient_position(Position(0, 0), True) == Position(8, 6)
    assert orient_position(Position(8, 6), True) == Position(0, 0)


def test_canvas_mapping_round_trips_for_both_orientations() -> None:
    for is_flipped in (False, True):
        x, y = canvas_origin_for_index(Position(2, 5).index, is_flipped)
        index = board_index_from_canvas_point(x + 10, y + 10, is_flipped)
        assert index == Position(2, 5).index


def test_canvas_mapping_round_trips_for_compact_metrics() -> None:
    metrics = select_window_metrics(1200, 640)
    for is_flipped in (False, True):
        x, y = canvas_origin_for_index(
            Position(2, 5).index,
            is_flipped,
            cell=metrics.cell,
            margin=metrics.margin,
        )
        index = board_index_from_canvas_point(
            x + max(4, metrics.cell // 5),
            y + max(4, metrics.cell // 5),
            is_flipped,
            cell=metrics.cell,
            margin=metrics.margin,
        )
        assert index == Position(2, 5).index


def test_toolbar_actions_include_flip_board() -> None:
    app = JungleApp.__new__(JungleApp)
    app.on_undo = lambda: None
    app.on_redo = lambda: None
    app.on_toggle_diagnostics = lambda: None
    app.on_ai_vs_ai = lambda: None
    app._ask_new_game = lambda: None
    app._save_game = lambda: None
    app._load_game = lambda: None
    app.toggle_board_orientation = lambda: None
    labels = [label for label, _ in JungleApp._toolbar_actions(app)]
    assert "Flip Board" in labels


def test_new_game_dialog_supports_starter_selection() -> None:
    assert JungleApp.STARTER_OPTIONS == (
        ("player", "Player starts"),
        ("ai", "AI starts"),
    )


def test_confirm_new_game_passes_difficulty_and_starter_choice() -> None:
    app = JungleApp.__new__(JungleApp)
    calls: list[tuple[str, bool]] = []
    app.on_new_game = lambda difficulty, human_starts: calls.append((difficulty, human_starts))
    dialog = SimpleNamespace(destroyed=False)
    dialog.destroy = lambda: setattr(dialog, "destroyed", True)
    difficulty = SimpleNamespace(get=lambda: "hard")
    starter = SimpleNamespace(get=lambda: "ai")

    JungleApp._confirm_new_game(app, dialog, difficulty, starter)

    assert calls == [("hard", False)]
    assert dialog.destroyed is True


def test_toggle_board_orientation_updates_state_and_rerenders() -> None:
    app = JungleApp.__new__(JungleApp)
    app.is_board_flipped = False
    renders: list[str] = []
    app._render_board = lambda: renders.append("render")

    JungleApp.toggle_board_orientation(app)

    assert app.is_board_flipped is True
    assert renders == ["render"]


def test_info_text_reports_human_and_computer_sides() -> None:
    app = JungleApp.__new__(JungleApp)
    app.human_side = Side.RED

    info = JungleApp._info_text(app)

    assert "You control: Red | Computer: Blue" in info


def test_compute_window_metrics_chooses_compact_startup_for_1366x768() -> None:
    metrics = compute_window_metrics(1366, 768)
    assert metrics.startup_width <= 1280
    assert metrics.startup_height <= 680
    assert metrics.min_width <= 1200
    assert metrics.min_height <= 640
    assert metrics.cell < 72


def test_select_window_metrics_compacts_board_and_panel_for_small_window() -> None:
    metrics = select_window_metrics(1200, 640)
    assert metrics.cell == 60
    assert metrics.history_height <= 10
    assert metrics.diagnostics_height <= 8
    assert metrics.wraplength <= 250
    assert metrics.diagnostics_collapsed is True
