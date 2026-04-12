from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from jungle.domain import GameState, Move, Piece, Side, initial_state
from jungle.rules import evaluate_result, find_legal_move, legal_moves


@dataclass(slots=True)
class AppliedMove:
    move: Move
    previous_state: GameState
    new_state: GameState


class Game:
    def __init__(self, state: GameState | None = None) -> None:
        self.state = state.copy() if state is not None else initial_state()
        self._undo_stack: list[GameState] = []
        self._redo_stack: list[GameState] = []

    def new_game(self) -> None:
        self.state = initial_state()
        self._undo_stack.clear()
        self._redo_stack.clear()

    def list_moves(self) -> list[Move]:
        return legal_moves(self.state)

    def apply_move(self, move: Move) -> AppliedMove:
        selected = find_legal_move(self.state, move.origin, move.destination)
        if selected is None:
            raise ValueError("Illegal move.")

        previous = self.state.copy()
        self._undo_stack.append(previous.copy())
        self._redo_stack.clear()

        board = self.state.board.copy()
        board[selected.origin] = None
        board[selected.destination] = selected.piece
        history = self.state.move_history + [selected]
        self.state = GameState(
            board=board,
            side_to_move=self.state.side_to_move.opponent,
            move_history=history,
        )
        result = evaluate_result(self.state)
        self.state.winner = result.winner
        self.state.result = result.status
        self.state.result_reason = result.reason
        return AppliedMove(move=selected, previous_state=previous, new_state=self.state.copy())

    def apply_coordinates(self, origin: int, destination: int) -> AppliedMove:
        piece = self.state.board[origin]
        if piece is None:
            raise ValueError("No piece at origin.")
        return self.apply_move(Move(origin=origin, destination=destination, piece=piece))

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self._redo_stack.append(self.state.copy())
        self.state = self._undo_stack.pop()
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._undo_stack.append(self.state.copy())
        self.state = self._redo_stack.pop()
        return True

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.state.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Game":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(GameState.from_dict(data))

    def move_log_lines(self) -> list[str]:
        lines: list[str] = []
        for index, move in enumerate(self.state.move_history, start=1):
            side = "Blue" if move.piece.side is Side.BLUE else "Red"
            action = f"{move.origin}->{move.destination}"
            suffix = ""
            if move.captured is not None:
                suffix = f" x {move.captured.kind.label}"
            if move.is_jump:
                suffix += " (jump)"
            lines.append(f"{index:02d}. {side} {move.piece.kind.label} {action}{suffix}")
        return lines
