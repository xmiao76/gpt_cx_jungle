from __future__ import annotations

from types import SimpleNamespace

import jungle.app.controller as controller_module
from jungle.app.controller import AppController, HUMAN_SIDE, run_window_fit_probe
from jungle.domain import Position, Side
from jungle.engine import Game
from jungle.rules import find_legal_move


def make_controller(game: Game | None = None) -> AppController:
    controller = AppController.__new__(AppController)
    controller.game = game or Game()
    controller.difficulty = "medium"
    controller.selected_index = None
    controller.legal_targets = set()
    controller.diagnostics_enabled = False
    controller.thinking = False
    controller.ai_vs_ai_enabled = False
    controller.ai_queue = None
    controller.app = SimpleNamespace(notify_error=lambda *_: None)
    controller.refresh = lambda *args, **kwargs: None
    controller.start_ai_turn = lambda: None
    controller.maybe_start_ai_turn = lambda: None
    return controller


def test_maybe_start_ai_turn_uses_human_side_constant() -> None:
    controller = make_controller()
    started: list[str] = []
    controller.start_ai_turn = lambda: started.append("ai")

    controller.game.state.side_to_move = HUMAN_SIDE
    AppController.maybe_start_ai_turn(controller)
    assert started == []

    controller.game.state.side_to_move = HUMAN_SIDE.opponent
    AppController.maybe_start_ai_turn(controller)
    assert started == ["ai"]

    controller.ai_vs_ai_enabled = True
    controller.game.state.side_to_move = HUMAN_SIDE
    AppController.maybe_start_ai_turn(controller)
    assert started == ["ai", "ai"]


def test_handle_square_only_selects_human_side_pieces() -> None:
    controller = make_controller()
    refreshes: list[str] = []
    controller.refresh = lambda *args, **kwargs: refreshes.append("refresh")

    AppController.handle_square(controller, Position(2, 0).index)
    assert controller.selected_index is None
    assert refreshes == []

    AppController.handle_square(controller, Position(6, 6).index)
    assert controller.selected_index == Position(6, 6).index
    assert Position(5, 6).index in controller.legal_targets
    assert refreshes == ["refresh"]


def test_undo_rewinds_human_and_ai_turn_pair() -> None:
    game = Game()
    initial = game.state.to_dict()
    blue_move = find_legal_move(game.state, Position(6, 6).index, Position(5, 6).index)
    assert blue_move is not None
    game.apply_move(blue_move)
    red_move = find_legal_move(game.state, Position(2, 0).index, Position(3, 0).index)
    assert red_move is not None
    game.apply_move(red_move)

    controller = make_controller(game)
    AppController.undo(controller)

    assert controller.game.state.to_dict() == initial


def test_new_game_resets_runtime_state_and_rechecks_ai_turn() -> None:
    controller = make_controller()
    calls: list[str] = []
    controller.selected_index = 10
    controller.legal_targets = {11}
    controller.ai_vs_ai_enabled = True
    controller.refresh = lambda *args, **kwargs: calls.append("refresh")
    controller.maybe_start_ai_turn = lambda: calls.append("maybe")

    AppController.new_game(controller, "hard")

    assert controller.difficulty == "hard"
    assert controller.selected_index is None
    assert controller.legal_targets == set()
    assert controller.ai_vs_ai_enabled is False
    assert calls == ["refresh", "maybe"]


def test_load_resets_selection_and_rechecks_ai_turn(monkeypatch) -> None:
    controller = make_controller()
    loaded = Game()
    loaded.state.side_to_move = Side.RED
    calls: list[str] = []
    controller.selected_index = 5
    controller.legal_targets = {6}
    controller.refresh = lambda *args, **kwargs: calls.append("refresh")
    controller.maybe_start_ai_turn = lambda: calls.append("maybe")
    monkeypatch.setattr(Game, "load", classmethod(lambda cls, path: loaded))

    AppController.load(controller, "save.json")

    assert controller.game is loaded
    assert controller.selected_index is None
    assert controller.legal_targets == set()
    assert calls == ["refresh", "maybe"]


def test_run_window_fit_probe_checks_startup_and_resize(monkeypatch, capsys) -> None:
    class FakeApp:
        def __init__(self) -> None:
            self.probes = iter(
                [
                    {"window_width": 1280, "window_height": 680, "board_bottom_visible": True, "panel_bottom_visible": True, "click_mapping_ok": True, "fits": True},
                    {"window_width": 1200, "window_height": 640, "board_bottom_visible": True, "panel_bottom_visible": True, "click_mapping_ok": True, "fits": True},
                ]
            )
            self.geometries: list[str] = []
            self.destroyed = False

        def geometry(self, value: str) -> None:
            self.geometries.append(value)

        def update(self) -> None:
            return None

        def update_idletasks(self) -> None:
            return None

        def window_fit_probe(self):
            return next(self.probes)

        def destroy(self) -> None:
            self.destroyed = True

    fake_controller = SimpleNamespace(app=FakeApp())
    monkeypatch.setattr(controller_module, "AppController", lambda: fake_controller)

    result = run_window_fit_probe("1280x680", "1200x640")

    assert result == 0
    assert fake_controller.app.geometries == ["1280x680", "1200x640"]
    assert fake_controller.app.destroyed is True
    output = capsys.readouterr().out
    assert "startup_window=1280x680" in output
    assert "resized_window=1200x640" in output
