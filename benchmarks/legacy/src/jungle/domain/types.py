from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any


BOARD_COLS = 7
BOARD_ROWS = 9
BOARD_SIZE = BOARD_COLS * BOARD_ROWS


class Side(str, Enum):
    BLUE = "blue"
    RED = "red"

    @property
    def opponent(self) -> "Side":
        return Side.RED if self is Side.BLUE else Side.BLUE


class PieceType(IntEnum):
    RAT = 1
    CAT = 2
    DOG = 3
    WOLF = 4
    LEOPARD = 5
    TIGER = 6
    LION = 7
    ELEPHANT = 8

    @property
    def label(self) -> str:
        return self.name.title()

    @property
    def rank(self) -> int:
        return int(self.value)


class Terrain(str, Enum):
    LAND = "land"
    WATER = "water"
    TRAP = "trap"
    DEN = "den"


class ResultType(str, Enum):
    ONGOING = "ongoing"
    DEN_ENTRY = "den_entry"
    CAPTURE_ALL = "capture_all"
    NO_LEGAL_MOVES = "no_legal_moves"


@dataclass(frozen=True, slots=True)
class Position:
    row: int
    col: int

    @property
    def index(self) -> int:
        return self.row * BOARD_COLS + self.col

    @staticmethod
    def from_index(index: int) -> "Position":
        return Position(index // BOARD_COLS, index % BOARD_COLS)

    def manhattan_distance(self, other: "Position") -> int:
        return abs(self.row - other.row) + abs(self.col - other.col)


@dataclass(frozen=True, slots=True)
class Piece:
    side: Side
    kind: PieceType

    @property
    def symbol(self) -> str:
        blue = {
            PieceType.RAT: "r",
            PieceType.CAT: "c",
            PieceType.DOG: "d",
            PieceType.WOLF: "w",
            PieceType.LEOPARD: "p",
            PieceType.TIGER: "t",
            PieceType.LION: "l",
            PieceType.ELEPHANT: "e",
        }
        char = blue[self.kind]
        return char.upper() if self.side is Side.BLUE else char

    @property
    def rank(self) -> int:
        return self.kind.rank


@dataclass(frozen=True, slots=True)
class Move:
    origin: int
    destination: int
    piece: Piece
    captured: Piece | None = None
    is_jump: bool = False
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "piece": {"side": self.piece.side.value, "kind": self.piece.kind.name},
            "captured": None
            if self.captured is None
            else {"side": self.captured.side.value, "kind": self.captured.kind.name},
            "is_jump": self.is_jump,
            "note": self.note,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Move":
        piece = Piece(Side(data["piece"]["side"]), PieceType[data["piece"]["kind"]])
        captured_data = data.get("captured")
        captured = (
            None
            if captured_data is None
            else Piece(Side(captured_data["side"]), PieceType[captured_data["kind"]])
        )
        return Move(
            origin=data["origin"],
            destination=data["destination"],
            piece=piece,
            captured=captured,
            is_jump=data.get("is_jump", False),
            note=data.get("note", ""),
        )


@dataclass(frozen=True, slots=True)
class GameResult:
    status: ResultType = ResultType.ONGOING
    winner: Side | None = None
    reason: str = ""

    @property
    def is_over(self) -> bool:
        return self.status is not ResultType.ONGOING


@dataclass(slots=True)
class GameState:
    board: list[Piece | None]
    side_to_move: Side
    move_history: list[Move] = field(default_factory=list)
    winner: Side | None = None
    result: ResultType = ResultType.ONGOING
    result_reason: str = ""

    def copy(self) -> "GameState":
        return GameState(
            board=self.board.copy(),
            side_to_move=self.side_to_move,
            move_history=self.move_history.copy(),
            winner=self.winner,
            result=self.result,
            result_reason=self.result_reason,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "board": [
                None
                if piece is None
                else {"side": piece.side.value, "kind": piece.kind.name}
                for piece in self.board
            ],
            "side_to_move": self.side_to_move.value,
            "move_history": [move.to_dict() for move in self.move_history],
            "winner": None if self.winner is None else self.winner.value,
            "result": self.result.value,
            "result_reason": self.result_reason,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "GameState":
        board: list[Piece | None] = []
        for item in data["board"]:
            if item is None:
                board.append(None)
            else:
                board.append(Piece(Side(item["side"]), PieceType[item["kind"]]))
        return GameState(
            board=board,
            side_to_move=Side(data["side_to_move"]),
            move_history=[Move.from_dict(move) for move in data.get("move_history", [])],
            winner=None if data.get("winner") is None else Side(data["winner"]),
            result=ResultType(data.get("result", ResultType.ONGOING.value)),
            result_reason=data.get("result_reason", ""),
        )
