from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from jungle.domain import (
    BOARD_COLS,
    BOARD_ROWS,
    BLUE_DEN,
    BLUE_TRAPS,
    RED_DEN,
    RED_TRAPS,
    WATER,
    PieceType,
    Position,
    Side,
)
from jungle.engine import Game
from jungle.rules import effective_rank, generate_piece_moves
from jungle.ui.assets import AssetLoader
from jungle.ui.theme import BOARD_HEIGHT, BOARD_WIDTH, CANVAS_HEIGHT, CANVAS_WIDTH, CELL, MARGIN, PALETTE


class JungleApp(tk.Tk):
    def __init__(
        self,
        game: Game,
        on_square: Callable[[int], None],
        on_new_game: Callable[[str], None],
        on_undo: Callable[[], None],
        on_redo: Callable[[], None],
        on_save: Callable[[str], None],
        on_load: Callable[[str], None],
        on_toggle_diagnostics: Callable[[], None],
        on_ai_vs_ai: Callable[[], None],
    ) -> None:
        super().__init__()
        self.title("Jungle")
        self.geometry("1160x810")
        self.minsize(1050, 760)
        self.configure(bg=PALETTE.app_bg)
        self.game = game
        self.on_square = on_square
        self.on_new_game = on_new_game
        self.on_undo = on_undo
        self.on_redo = on_redo
        self.on_save = on_save
        self.on_load = on_load
        self.on_toggle_diagnostics = on_toggle_diagnostics
        self.on_ai_vs_ai = on_ai_vs_ai
        self.assets = AssetLoader()
        self.selected_index: int | None = None
        self.legal_targets: set[int] = set()
        self.diagnostics_enabled = False
        self.status_var = tk.StringVar()
        self.ai_var = tk.StringVar(value="Difficulty: medium")
        self.info_var = tk.StringVar()
        self._build_styles()
        self._build()

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Panel.TFrame", background=PALETTE.panel_bg)
        style.configure("Card.TFrame", background=PALETTE.panel_card)
        style.configure("Title.TLabel", background=PALETTE.panel_bg, foreground="#f7efd9", font=("Georgia", 24, "bold"))
        style.configure("Subtle.TLabel", background=PALETTE.panel_bg, foreground="#ece2c4", font=("Segoe UI", 10))
        style.configure("Section.TLabel", background=PALETTE.panel_bg, foreground="#f7efd9", font=("Georgia", 13, "bold"))
        style.configure("CardTitle.TLabel", background=PALETTE.panel_card, foreground=PALETTE.panel_text, font=("Georgia", 12, "bold"))
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"))

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(0, weight=1)

        board_frame = tk.Frame(self, bg=PALETTE.app_bg, padx=18, pady=18)
        board_frame.grid(row=0, column=0, sticky="nsew")
        board_frame.columnconfigure(0, weight=1)
        board_frame.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            board_frame,
            width=CANVAS_WIDTH,
            height=CANVAS_HEIGHT,
            bg=PALETTE.app_bg,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        side = ttk.Frame(self, style="Panel.TFrame", padding=18)
        side.grid(row=0, column=1, sticky="ns")
        side.columnconfigure(0, weight=1)

        ttk.Label(side, text="Jungle", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(side, text="Illustrated board-game edition", style="Subtle.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 10))
        ttk.Label(side, textvariable=self.status_var, style="Subtle.TLabel", wraplength=290, justify="left").grid(row=2, column=0, sticky="w", pady=(0, 14))

        toolbar = ttk.Frame(side, style="Panel.TFrame")
        toolbar.grid(row=3, column=0, sticky="ew")
        for idx, (label, command) in enumerate(
            [
                ("New Game", self._ask_new_game),
                ("Undo", self.on_undo),
                ("Redo", self.on_redo),
                ("Save", self._save_game),
                ("Load", self._load_game),
                ("Diagnostics", self.on_toggle_diagnostics),
                ("AI vs AI", self.on_ai_vs_ai),
            ]
        ):
            ttk.Button(toolbar, text=label, command=command, style="Action.TButton").grid(
                row=idx // 2, column=idx % 2, sticky="ew", padx=4, pady=4
            )
        toolbar.columnconfigure(0, weight=1)
        toolbar.columnconfigure(1, weight=1)

        info_card = ttk.Frame(side, style="Card.TFrame", padding=12)
        info_card.grid(row=4, column=0, sticky="ew", pady=(14, 10))
        info_card.columnconfigure(0, weight=1)
        ttk.Label(info_card, text="Session", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        tk.Label(
            info_card,
            textvariable=self.ai_var,
            bg=PALETTE.panel_card,
            fg=PALETTE.panel_text,
            justify="left",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=1, column=0, sticky="w", pady=(8, 4))
        tk.Label(
            info_card,
            textvariable=self.info_var,
            bg=PALETTE.panel_card,
            fg=PALETTE.panel_text,
            wraplength=280,
            justify="left",
            font=("Segoe UI", 10),
        ).grid(row=2, column=0, sticky="w")

        ttk.Label(side, text="Move History", style="Section.TLabel").grid(row=5, column=0, sticky="w", pady=(8, 4))
        self.history = tk.Text(
            side,
            width=34,
            height=18,
            state="disabled",
            wrap="word",
            bg="#f1e7cb",
            fg=PALETTE.panel_text,
            relief="flat",
            font=("Consolas", 10),
            padx=10,
            pady=10,
        )
        self.history.grid(row=6, column=0, sticky="nsew")
        side.rowconfigure(6, weight=1)

        ttk.Label(side, text="Diagnostics", style="Section.TLabel").grid(row=7, column=0, sticky="w", pady=(14, 4))
        self.diagnostics = tk.Text(
            side,
            width=34,
            height=10,
            state="disabled",
            wrap="word",
            bg="#203123",
            fg="#e7efd8",
            relief="flat",
            font=("Consolas", 10),
            padx=10,
            pady=10,
        )
        self.diagnostics.grid(row=8, column=0, sticky="nsew")

    def _save_game(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            self.on_save(path)

    def _load_game(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            self.on_load(path)

    def _ask_new_game(self) -> None:
        dialog = tk.Toplevel(self, bg=PALETTE.panel_bg)
        dialog.title("New Game")
        dialog.transient(self)
        dialog.grab_set()
        tk.Label(
            dialog,
            text="Choose AI difficulty",
            bg=PALETTE.panel_bg,
            fg="#f7efd9",
            font=("Georgia", 14, "bold"),
        ).pack(padx=16, pady=(16, 6))
        value = tk.StringVar(value="medium")
        for option in ("easy", "medium", "hard"):
            tk.Radiobutton(
                dialog,
                text=option.title(),
                value=option,
                variable=value,
                bg=PALETTE.panel_bg,
                fg="#f7efd9",
                selectcolor="#294f39",
                activebackground=PALETTE.panel_bg,
                activeforeground="#ffffff",
                font=("Segoe UI", 11),
            ).pack(anchor="w", padx=16)

        def confirm() -> None:
            self.on_new_game(value.get())
            dialog.destroy()

        ttk.Button(dialog, text="Start", command=confirm, style="Action.TButton").pack(padx=16, pady=16)

    def _on_canvas_click(self, event: tk.Event) -> None:
        col = (event.x - MARGIN) // CELL
        row = (event.y - MARGIN) // CELL
        if not (0 <= col < BOARD_COLS and 0 <= row < BOARD_ROWS):
            return
        self.on_square(Position(row, col).index)

    def update_view(
        self,
        game: Game,
        selected_index: int | None,
        legal_targets: set[int],
        thinking: bool,
        diagnostics_enabled: bool,
        ai_message: str = "",
    ) -> None:
        self.game = game
        self.selected_index = selected_index
        self.legal_targets = legal_targets
        self.diagnostics_enabled = diagnostics_enabled
        self.ai_var.set(ai_message)
        self.status_var.set(self._status_text(thinking))
        self.info_var.set(self._info_text())
        self._render_board()
        self._render_history()
        self._render_diagnostics()

    def notify_error(self, message: str) -> None:
        messagebox.showerror("Jungle", message)

    def notify_info(self, message: str) -> None:
        messagebox.showinfo("Jungle", message)

    def _status_text(self, thinking: bool) -> str:
        state = self.game.state
        if state.winner is not None:
            return f"{state.winner.value.title()} wins. {state.result_reason}"
        if thinking:
            return f"{state.side_to_move.value.title()} to move. Computer is thinking..."
        return f"{state.side_to_move.value.title()} to move."

    def _info_text(self) -> str:
        return "\n".join(
            [
                "Goal: enter the opponent den or capture every opposing piece.",
                "Rat swims. Lion and tiger leap rivers unless any rat blocks the path.",
            ]
        )

    def _render_history(self) -> None:
        self.history.configure(state="normal")
        self.history.delete("1.0", "end")
        self.history.insert("1.0", "\n".join(self.game.move_log_lines()))
        self.history.configure(state="disabled")

    def _render_diagnostics(self) -> None:
        self.diagnostics.configure(state="normal")
        self.diagnostics.delete("1.0", "end")
        if self.diagnostics_enabled:
            state = self.game.state
            lines = [
                f"Side to move: {state.side_to_move.value}",
                f"Selected: {self.selected_index}",
                f"Legal targets: {sorted(self.legal_targets)}",
            ]
            if self.selected_index is not None and state.board[self.selected_index] is not None:
                piece = state.board[self.selected_index]
                assert piece is not None
                lines.append(f"Piece: {piece.side.value} {piece.kind.label}")
                lines.append(f"Effective rank: {effective_rank(state, self.selected_index)}")
                lines.append("Moves:")
                lines.extend(
                    f"  {move.origin}->{move.destination}{' jump' if move.is_jump else ''}"
                    for move in generate_piece_moves(state, self.selected_index)
                )
            self.diagnostics.insert("1.0", "\n".join(lines))
        else:
            self.diagnostics.insert("1.0", "Diagnostics are off.")
        self.diagnostics.configure(state="disabled")

    def _render_board(self) -> None:
        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT, fill=PALETTE.app_bg, outline="")
        self._draw_board_base()
        self._draw_terrain()
        self._draw_grid()
        self._draw_highlights()
        self._draw_pieces()
        self._draw_corner_badges()

    def _draw_board_base(self) -> None:
        self.canvas.create_image(MARGIN, MARGIN, image=self.assets.board("board_background"), anchor="nw")
        self.canvas.create_round_rectangle = None  # quiet type checkers in editors without changing runtime
        self.canvas.create_rectangle(
            MARGIN - 8,
            MARGIN - 8,
            MARGIN + BOARD_WIDTH + 8,
            MARGIN + BOARD_HEIGHT + 8,
            outline="#d6b36d",
            width=4,
        )

    def _draw_terrain(self) -> None:
        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                index = Position(row, col).index
                filename = "land_tile"
                if index in WATER:
                    filename = "river_tile"
                elif index in BLUE_TRAPS:
                    filename = "blue_trap_tile"
                elif index in RED_TRAPS:
                    filename = "red_trap_tile"
                elif index == BLUE_DEN:
                    filename = "blue_den_tile"
                elif index == RED_DEN:
                    filename = "red_den_tile"
                x = MARGIN + col * CELL
                y = MARGIN + row * CELL
                self.canvas.create_image(x, y, image=self.assets.board(filename), anchor="nw")

    def _draw_grid(self) -> None:
        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                x1 = MARGIN + col * CELL
                y1 = MARGIN + row * CELL
                x2 = x1 + CELL
                y2 = y1 + CELL
                self.canvas.create_rectangle(x1, y1, x2, y2, outline=PALETTE.grid, width=2)

    def _draw_highlights(self) -> None:
        if self.selected_index is not None:
            self._halo(self.selected_index, PALETTE.selected, width=5)
        for target in self.legal_targets:
            is_capture = self.game.state.board[target] is not None
            color = PALETTE.legal_capture if is_capture else PALETTE.legal_move
            self._target_marker(target, color)

    def _draw_pieces(self) -> None:
        for index, piece in enumerate(self.game.state.board):
            if piece is None:
                continue
            pos = Position.from_index(index)
            x = MARGIN + pos.col * CELL + CELL / 2
            y = MARGIN + pos.row * CELL + CELL / 2 + 2
            self.canvas.create_oval(x - 24, y + 18, x + 24, y + 30, fill="#000000", stipple="gray50", outline="")
            self.canvas.create_image(x, y, image=self.assets.piece(piece.side, piece.kind), anchor="center")

    def _draw_corner_badges(self) -> None:
        corners = [
            (BLUE_DEN, "Blue Den"),
            (RED_DEN, "Red Den"),
        ]
        for index, label in corners:
            pos = Position.from_index(index)
            x = MARGIN + pos.col * CELL + CELL / 2
            y = MARGIN + pos.row * CELL + 10
            self.canvas.create_text(x, y, text=label, fill="#fff4cf", font=("Georgia", 10, "bold"))

    def _halo(self, index: int, color: str, width: int) -> None:
        pos = Position.from_index(index)
        x1 = MARGIN + pos.col * CELL + 5
        y1 = MARGIN + pos.row * CELL + 5
        x2 = x1 + CELL - 10
        y2 = y1 + CELL - 10
        self.canvas.create_oval(x1, y1, x2, y2, outline=color, width=width)

    def _target_marker(self, index: int, color: str) -> None:
        pos = Position.from_index(index)
        cx = MARGIN + pos.col * CELL + CELL / 2
        cy = MARGIN + pos.row * CELL + CELL / 2
        if self.game.state.board[index] is None:
            self.canvas.create_oval(cx - 9, cy - 9, cx + 9, cy + 9, fill=color, outline="#ffffff", width=2)
        else:
            self.canvas.create_oval(cx - 28, cy - 28, cx + 28, cy + 28, outline=color, width=4)

