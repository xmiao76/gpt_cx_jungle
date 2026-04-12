from __future__ import annotations

import argparse
import queue
import threading
from pathlib import Path

from jungle.ai import AlphaBetaAI
from jungle.domain import Move, Side
from jungle.engine import Game
from jungle.ui import JungleApp


DIFFICULTY_LIMITS = {
    "easy": 300,
    "medium": 900,
    "hard": 1800,
}


class AppController:
    def __init__(self, difficulty: str = "medium") -> None:
        self.game = Game()
        self.difficulty = difficulty
        self.ai = AlphaBetaAI(DIFFICULTY_LIMITS[difficulty])
        self.selected_index: int | None = None
        self.legal_targets: set[int] = set()
        self.diagnostics_enabled = False
        self.thinking = False
        self.ai_queue: queue.Queue[tuple[Move | None, str]] = queue.Queue()
        self.ai_vs_ai_enabled = False
        self.app = JungleApp(
            game=self.game,
            on_square=self.handle_square,
            on_new_game=self.new_game,
            on_undo=self.undo,
            on_redo=self.redo,
            on_save=self.save,
            on_load=self.load,
            on_toggle_diagnostics=self.toggle_diagnostics,
            on_ai_vs_ai=self.toggle_ai_vs_ai,
        )
        self.refresh()
        self.app.after(120, self.poll_ai_queue)
        self.maybe_start_ai_turn()

    def run(self) -> None:
        self.app.mainloop()

    def new_game(self, difficulty: str) -> None:
        self.difficulty = difficulty
        self.ai = AlphaBetaAI(DIFFICULTY_LIMITS[difficulty])
        self.game.new_game()
        self.selected_index = None
        self.legal_targets.clear()
        self.ai_vs_ai_enabled = False
        self.refresh()
        self.maybe_start_ai_turn()

    def handle_square(self, index: int) -> None:
        if self.thinking or self.game.state.winner is not None:
            return
        piece = self.game.state.board[index]
        if self.selected_index is None:
            if piece is None or piece.side is not Side.BLUE:
                return
            self.selected_index = index
            self.legal_targets = {move.destination for move in self.game.list_moves() if move.origin == index}
            self.refresh()
            return

        if index == self.selected_index:
            self.selected_index = None
            self.legal_targets.clear()
            self.refresh()
            return

        try:
            self.game.apply_coordinates(self.selected_index, index)
        except ValueError:
            if piece is not None and piece.side is Side.BLUE:
                self.selected_index = index
                self.legal_targets = {move.destination for move in self.game.list_moves() if move.origin == index}
            else:
                self.app.notify_error("Illegal move.")
                self.selected_index = None
                self.legal_targets.clear()
            self.refresh()
            return

        self.selected_index = None
        self.legal_targets.clear()
        self.refresh()
        self.maybe_start_ai_turn()

    def maybe_start_ai_turn(self) -> None:
        if self.game.state.winner is not None:
            self.refresh()
            return
        if self.game.state.side_to_move is Side.RED or self.ai_vs_ai_enabled:
            self.start_ai_turn()

    def start_ai_turn(self) -> None:
        if self.thinking or self.game.state.winner is not None:
            return
        self.thinking = True
        state = self.game.state.copy()
        difficulty = self.difficulty

        def worker() -> None:
            ai = AlphaBetaAI(DIFFICULTY_LIMITS[difficulty])
            result = ai.choose_move(state)
            message = f"Difficulty: {difficulty} | depth {result.depth} | nodes {result.nodes} | {result.elapsed_ms:.0f} ms"
            self.ai_queue.put((result.move, message))

        threading.Thread(target=worker, daemon=True).start()
        self.refresh()

    def poll_ai_queue(self) -> None:
        try:
            while True:
                move, message = self.ai_queue.get_nowait()
                self.thinking = False
                if move is not None and self.game.state.winner is None:
                    self.game.apply_move(move)
                self.refresh(message)
                if self.ai_vs_ai_enabled and self.game.state.winner is None:
                    self.start_ai_turn()
        except queue.Empty:
            pass
        self.app.after(120, self.poll_ai_queue)

    def undo(self) -> None:
        if self.thinking:
            return
        if self.game.undo():
            if self.game.state.side_to_move is Side.RED and self.game.undo():
                pass
            self.selected_index = None
            self.legal_targets.clear()
            self.refresh()

    def redo(self) -> None:
        if self.thinking:
            return
        if self.game.redo():
            self.refresh()
            self.maybe_start_ai_turn()

    def save(self, path: str) -> None:
        self.game.save(path)
        self.refresh()

    def load(self, path: str) -> None:
        self.game = Game.load(path)
        self.selected_index = None
        self.legal_targets.clear()
        self.refresh()
        self.maybe_start_ai_turn()

    def toggle_diagnostics(self) -> None:
        self.diagnostics_enabled = not self.diagnostics_enabled
        self.refresh()

    def toggle_ai_vs_ai(self) -> None:
        self.ai_vs_ai_enabled = not self.ai_vs_ai_enabled
        self.refresh()
        if self.ai_vs_ai_enabled:
            self.maybe_start_ai_turn()

    def refresh(self, ai_message: str = "") -> None:
        self.app.update_view(
            self.game,
            self.selected_index,
            self.legal_targets,
            self.thinking,
            self.diagnostics_enabled,
            ai_message or f"Difficulty: {self.difficulty}",
        )


def run_smoke_validation() -> int:
    from jungle.ai import AlphaBetaAI
    from jungle.engine import Game

    game = Game()
    blue_ai = AlphaBetaAI(60)
    red_ai = AlphaBetaAI(60)
    turns = 0
    while game.state.winner is None and turns < 200:
        ai = blue_ai if game.state.side_to_move is Side.BLUE else red_ai
        result = ai.choose_move(game.state)
        if result.move is None:
            break
        game.apply_move(result.move)
        turns += 1
    output = Path("release_smoke_result.txt")
    output.write_text(
        "\n".join(
            [
                f"winner={game.state.winner.value if game.state.winner else 'none'}",
                f"result={game.state.result.value}",
                f"turns={turns}",
            ]
        ),
        encoding="utf-8",
    )
    return 0 if turns > 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Jungle desktop game")
    parser.add_argument("--smoke-test", action="store_true", help="Run a packaged smoke test without opening the GUI.")
    args = parser.parse_args()
    if args.smoke_test:
        raise SystemExit(run_smoke_validation())
    controller = AppController()
    controller.run()
