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
from jungle.ui.theme import CANVAS_HEIGHT, CANVAS_WIDTH, CELL, MARGIN, PALETTE, WindowMetrics, compute_window_metrics, select_window_metrics


def orient_position(position: Position, is_flipped: bool) -> Position:
    if not is_flipped:
        return position
    return Position(BOARD_ROWS - 1 - position.row, BOARD_COLS - 1 - position.col)


def board_index_from_display(row: int, col: int, is_flipped: bool) -> int:
    return orient_position(Position(row, col), is_flipped).index


def board_index_from_canvas_point(
    x: int,
    y: int,
    is_flipped: bool,
    *,
    cell: int = CELL,
    margin: int = MARGIN,
) -> int | None:
    col = (x - margin) // cell
    row = (y - margin) // cell
    if not (0 <= col < BOARD_COLS and 0 <= row < BOARD_ROWS):
        return None
    return board_index_from_display(row, col, is_flipped)


def canvas_origin_for_index(
    index: int,
    is_flipped: bool,
    *,
    cell: int = CELL,
    margin: int = MARGIN,
) -> tuple[int, int]:
    position = orient_position(Position.from_index(index), is_flipped)
    return margin + position.col * cell, margin + position.row * cell


class JungleApp(tk.Tk):
    DIFFICULTY_OPTIONS = ("easy", "medium", "hard")
    STARTER_OPTIONS = (
        ("player", "Player starts"),
        ("ai", "AI starts"),
    )

    def __init__(
        self,
        game: Game,
        on_square: Callable[[int], None],
        on_new_game: Callable[[str, bool], None],
        on_ai_starts: Callable[[], None],
        on_undo: Callable[[], None],
        on_redo: Callable[[], None],
        on_save: Callable[[str], None],
        on_load: Callable[[str], None],
        on_toggle_diagnostics: Callable[[], None],
        on_ai_vs_ai: Callable[[], None],
    ) -> None:
        super().__init__()
        self.title("Jungle")
        self.metrics = compute_window_metrics(self.winfo_screenwidth(), self.winfo_screenheight())
        self.geometry(f"{self.metrics.startup_width}x{self.metrics.startup_height}")
        self.minsize(self.metrics.min_width, self.metrics.min_height)
        self.configure(bg=PALETTE.app_bg)
        self.game = game
        self.on_square = on_square
        self.on_new_game = on_new_game
        self.on_ai_starts = on_ai_starts
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
        self.is_board_flipped = False
        self.human_side = Side.BLUE
        self.status_var = tk.StringVar()
        self.ai_var = tk.StringVar(value="Difficulty: medium")
        self.info_var = tk.StringVar()
        self._applying_metrics = False
        self._build_styles()
        self._build()
        self._apply_window_metrics(self.metrics, rerender=False)
        self.bind("<Configure>", self._on_configure)

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

        self.board_frame = tk.Frame(self, bg=PALETTE.app_bg, padx=self.metrics.root_padding, pady=self.metrics.root_padding)
        self.board_frame.grid(row=0, column=0, sticky="nsew")
        self.board_frame.columnconfigure(0, weight=1)
        self.board_frame.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self.board_frame,
            width=CANVAS_WIDTH,
            height=CANVAS_HEIGHT,
            bg=PALETTE.app_bg,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        self.side = ttk.Frame(self, style="Panel.TFrame", padding=self.metrics.side_padding)
        self.side.grid(row=0, column=1, sticky="ns")
        self.side.columnconfigure(0, weight=1)

        self.title_label = ttk.Label(self.side, text="Jungle", style="Title.TLabel")
        self.title_label.grid(row=0, column=0, sticky="w")
        self.subtitle_label = ttk.Label(self.side, text="Illustrated board-game edition", style="Subtle.TLabel")
        self.subtitle_label.grid(row=1, column=0, sticky="w", pady=(2, 10))
        self.status_label = ttk.Label(self.side, textvariable=self.status_var, style="Subtle.TLabel", wraplength=self.metrics.wraplength, justify="left")
        self.status_label.grid(row=2, column=0, sticky="w", pady=(0, 14))

        self.toolbar = ttk.Frame(self.side, style="Panel.TFrame")
        self.toolbar.grid(row=3, column=0, sticky="ew")
        for idx, (label, command) in enumerate(self._toolbar_actions()):
            ttk.Button(self.toolbar, text=label, command=command, style="Action.TButton").grid(
                row=idx // 2, column=idx % 2, sticky="ew", padx=4, pady=4
            )
        self.toolbar.columnconfigure(0, weight=1)
        self.toolbar.columnconfigure(1, weight=1)

        self.info_card = ttk.Frame(self.side, style="Card.TFrame", padding=max(8, self.metrics.side_padding - 2))
        self.info_card.grid(row=4, column=0, sticky="ew", pady=(14, 10))
        self.info_card.columnconfigure(0, weight=1)
        ttk.Label(self.info_card, text="Session", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.ai_label = tk.Label(
            self.info_card,
            textvariable=self.ai_var,
            bg=PALETTE.panel_card,
            fg=PALETTE.panel_text,
            justify="left",
            font=("Segoe UI", 10, "bold"),
        )
        self.ai_label.grid(row=1, column=0, sticky="w", pady=(8, 4))
        self.info_label = tk.Label(
            self.info_card,
            textvariable=self.info_var,
            bg=PALETTE.panel_card,
            fg=PALETTE.panel_text,
            wraplength=max(180, self.metrics.wraplength - 10),
            justify="left",
            font=("Segoe UI", 10),
        )
        self.info_label.grid(row=2, column=0, sticky="w")

        self.history_section_label = ttk.Label(self.side, text="Move History", style="Section.TLabel")
        self.history_section_label.grid(row=5, column=0, sticky="w", pady=(8, 4))
        self.history = tk.Text(
            self.side,
            width=self.metrics.text_width,
            height=self.metrics.history_height,
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
        self.side.rowconfigure(6, weight=1)

        self.diagnostics_section_label = ttk.Label(self.side, text="Diagnostics", style="Section.TLabel")
        self.diagnostics_section_label.grid(row=7, column=0, sticky="w", pady=(14, 4))
        self.diagnostics = tk.Text(
            self.side,
            width=self.metrics.text_width,
            height=self.metrics.diagnostics_height,
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

    def _on_configure(self, event: tk.Event) -> None:
        if event.widget is not self or self._applying_metrics:
            return
        metrics = select_window_metrics(event.width, event.height)
        self._apply_window_metrics(metrics)

    def _apply_window_metrics(self, metrics: WindowMetrics, rerender: bool = True) -> None:
        if getattr(self, "metrics", None) == metrics and not rerender:
            return
        self._applying_metrics = True
        try:
            self.metrics = metrics
            self.board_frame.configure(padx=metrics.root_padding, pady=metrics.root_padding)
            self.side.configure(padding=metrics.side_padding)
            self.info_card.configure(padding=max(8, metrics.side_padding - 2))
            self.canvas.configure(width=metrics.canvas_width, height=metrics.canvas_height)
            self.status_label.configure(wraplength=metrics.wraplength)
            self.info_label.configure(wraplength=max(180, metrics.wraplength - 10))
            self.history.configure(width=metrics.text_width, height=metrics.history_height)
            self.diagnostics.configure(width=metrics.text_width, height=metrics.diagnostics_height)
            if metrics.diagnostics_collapsed and not self.diagnostics_enabled:
                self.diagnostics_section_label.grid_remove()
                self.diagnostics.grid_remove()
            else:
                self.diagnostics_section_label.grid()
                self.diagnostics.grid()
            if rerender:
                self._render_board()
                self._render_history()
                self._render_diagnostics()
        finally:
            self._applying_metrics = False

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
        for option in self.DIFFICULTY_OPTIONS:
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
        tk.Label(
            dialog,
            text="Who starts",
            bg=PALETTE.panel_bg,
            fg="#f7efd9",
            font=("Georgia", 14, "bold"),
        ).pack(padx=16, pady=(16, 6))
        starter = tk.StringVar(value="player")
        for option, label in self.STARTER_OPTIONS:
            tk.Radiobutton(
                dialog,
                text=label,
                value=option,
                variable=starter,
                bg=PALETTE.panel_bg,
                fg="#f7efd9",
                selectcolor="#294f39",
                activebackground=PALETTE.panel_bg,
                activeforeground="#ffffff",
                font=("Segoe UI", 11),
            ).pack(anchor="w", padx=16)

        ttk.Button(
            dialog,
            text="Start",
            command=lambda: self._confirm_new_game(dialog, value, starter),
            style="Action.TButton",
        ).pack(padx=16, pady=16)

    def _confirm_new_game(self, dialog: tk.Toplevel, difficulty: tk.StringVar, starter: tk.StringVar) -> None:
        self.on_new_game(difficulty.get(), starter.get() == "player")
        dialog.destroy()

    def _toolbar_actions(self) -> list[tuple[str, Callable[[], None]]]:
        return [
            ("New Game", self._ask_new_game),
            ("AI Starts", self.on_ai_starts),
            ("Undo", self.on_undo),
            ("Redo", self.on_redo),
            ("Save", self._save_game),
            ("Load", self._load_game),
            ("Flip Board", self.toggle_board_orientation),
            ("Diagnostics", self.on_toggle_diagnostics),
            ("AI vs AI", self.on_ai_vs_ai),
        ]

    def toggle_board_orientation(self) -> None:
        self.is_board_flipped = not self.is_board_flipped
        self._render_board()

    def _on_canvas_click(self, event: tk.Event) -> None:
        index = board_index_from_canvas_point(
            event.x,
            event.y,
            self.is_board_flipped,
            cell=self.metrics.cell,
            margin=self.metrics.margin,
        )
        if index is None:
            return
        self.on_square(index)

    def update_view(
        self,
        game: Game,
        selected_index: int | None,
        legal_targets: set[int],
        thinking: bool,
        diagnostics_enabled: bool,
        human_side: Side,
        ai_message: str = "",
    ) -> None:
        self.game = game
        self.selected_index = selected_index
        self.legal_targets = legal_targets
        self.diagnostics_enabled = diagnostics_enabled
        self.human_side = human_side
        self.ai_var.set(ai_message)
        self.status_var.set(self._status_text(thinking))
        self.info_var.set(self._info_text())
        self._apply_window_metrics(self.metrics)

    def notify_error(self, message: str) -> None:
        messagebox.showerror("Jungle", message)

    def notify_info(self, message: str) -> None:
        messagebox.showinfo("Jungle", message)

    def window_fit_probe(self) -> dict[str, bool | int]:
        self.update_idletasks()
        root_bottom = self.winfo_rooty() + self.winfo_height()
        canvas_bottom = self.canvas.winfo_rooty() + self.canvas.winfo_height()
        retained_widget = self.diagnostics if self.diagnostics.winfo_ismapped() else self.history
        retained_bottom = retained_widget.winfo_rooty() + retained_widget.winfo_height()
        target_index = Position(8, 6).index
        x0, y0 = canvas_origin_for_index(
            target_index,
            self.is_board_flipped,
            cell=self.metrics.cell,
            margin=self.metrics.margin,
        )
        click_probe = board_index_from_canvas_point(
            x0 + self.metrics.cell // 2,
            y0 + self.metrics.cell // 2,
            self.is_board_flipped,
            cell=self.metrics.cell,
            margin=self.metrics.margin,
        )
        return {
            "window_width": self.winfo_width(),
            "window_height": self.winfo_height(),
            "board_bottom_visible": canvas_bottom <= root_bottom,
            "panel_bottom_visible": retained_bottom <= root_bottom,
            "click_mapping_ok": click_probe == target_index,
            "fits": canvas_bottom <= root_bottom and retained_bottom <= root_bottom and click_probe == target_index,
        }

    def _status_text(self, thinking: bool) -> str:
        state = self.game.state
        if state.winner is not None:
            return f"{state.winner.value.title()} wins. {state.result_reason}"
        if thinking:
            return f"{state.side_to_move.value.title()} to move. Computer is thinking..."
        return f"{state.side_to_move.value.title()} to move."

    def _info_text(self) -> str:
        computer_side = self.human_side.opponent.value.title()
        return "\n".join(
            [
                f"You control: {self.human_side.value.title()} | Computer: {computer_side}",
                "Goal: enter the opponent den or capture every opposing piece.",
                "Rat swims. Lion leaps both river spans; tiger leaps only the 2-square span.",
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
        self.canvas.create_rectangle(0, 0, self.metrics.canvas_width, self.metrics.canvas_height, fill=PALETTE.app_bg, outline="")
        self._draw_board_base()
        self._draw_terrain()
        self._draw_grid()
        self._draw_highlights()
        self._draw_pieces()
        self._draw_corner_badges()

    def _draw_board_base(self) -> None:
        self.canvas.create_image(
            self.metrics.margin,
            self.metrics.margin,
            image=self.assets.board("board_background", self.metrics.scale_key),
            anchor="nw",
        )
        self.canvas.create_round_rectangle = None
        self.canvas.create_rectangle(
            self.metrics.margin - 8,
            self.metrics.margin - 8,
            self.metrics.margin + self.metrics.board_width + 8,
            self.metrics.margin + self.metrics.board_height + 8,
            outline="#d6b36d",
            width=max(2, self.metrics.cell // 18),
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
                x, y = canvas_origin_for_index(index, self.is_board_flipped, cell=self.metrics.cell, margin=self.metrics.margin)
                self.canvas.create_image(x, y, image=self.assets.board(filename, self.metrics.scale_key), anchor="nw")

    def _draw_grid(self) -> None:
        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                x1 = self.metrics.margin + col * self.metrics.cell
                y1 = self.metrics.margin + row * self.metrics.cell
                x2 = x1 + self.metrics.cell
                y2 = y1 + self.metrics.cell
                self.canvas.create_rectangle(x1, y1, x2, y2, outline=PALETTE.grid, width=max(1, self.metrics.cell // 28))

    def _draw_highlights(self) -> None:
        if self.selected_index is not None:
            self._halo(self.selected_index, PALETTE.selected, width=max(2, self.metrics.cell // 14))
        for target in self.legal_targets:
            is_capture = self.game.state.board[target] is not None
            color = PALETTE.legal_capture if is_capture else PALETTE.legal_move
            self._target_marker(target, color)

    def _draw_pieces(self) -> None:
        shadow_width = max(16, self.metrics.cell // 3)
        shadow_height = max(10, self.metrics.cell // 6)
        shadow_offset = max(10, self.metrics.cell // 4)
        for index, piece in enumerate(self.game.state.board):
            if piece is None:
                continue
            x0, y0 = canvas_origin_for_index(index, self.is_board_flipped, cell=self.metrics.cell, margin=self.metrics.margin)
            x = x0 + self.metrics.cell / 2
            y = y0 + self.metrics.cell / 2
            self.canvas.create_oval(
                x - shadow_width,
                y + shadow_offset,
                x + shadow_width,
                y + shadow_offset + shadow_height,
                fill="#000000",
                stipple="gray50",
                outline="",
            )
            self.canvas.create_image(x, y, image=self.assets.piece(piece.side, piece.kind, self.metrics.scale_key), anchor="center")

    def _draw_corner_badges(self) -> None:
        for index, label in ((BLUE_DEN, "Blue Den"), (RED_DEN, "Red Den")):
            x0, y0 = canvas_origin_for_index(index, self.is_board_flipped, cell=self.metrics.cell, margin=self.metrics.margin)
            self.canvas.create_text(
                x0 + self.metrics.cell / 2,
                y0 + max(10, self.metrics.cell // 7),
                text=label,
                fill="#fff4cf",
                font=("Georgia", max(8, self.metrics.cell // 6), "bold"),
            )

    def _halo(self, index: int, color: str, width: int) -> None:
        x0, y0 = canvas_origin_for_index(index, self.is_board_flipped, cell=self.metrics.cell, margin=self.metrics.margin)
        inset = max(4, self.metrics.cell // 14)
        self.canvas.create_oval(
            x0 + inset,
            y0 + inset,
            x0 + self.metrics.cell - inset,
            y0 + self.metrics.cell - inset,
            outline=color,
            width=width,
        )

    def _target_marker(self, index: int, color: str) -> None:
        x0, y0 = canvas_origin_for_index(index, self.is_board_flipped, cell=self.metrics.cell, margin=self.metrics.margin)
        cx = x0 + self.metrics.cell / 2
        cy = y0 + self.metrics.cell / 2
        if self.game.state.board[index] is None:
            radius = max(6, self.metrics.cell // 8)
            self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill=color, outline="#ffffff", width=2)
        else:
            radius = max(18, self.metrics.cell // 2 - 8)
            self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline=color, width=max(2, self.metrics.cell // 18))
