from __future__ import annotations

from collections import Counter

from jungle.domain import BLUE_DEN, RED_DEN, GameState, Move, ResultType, Side


SEARCH_HISTORY_LIMIT = 8


def apply_search_move(state: GameState, move: Move) -> GameState:
    """Apply an already-legal move without controller-oriented validation or undo state."""
    board = state.board.copy()
    board[move.origin] = None
    board[move.destination] = move.piece
    history = (state.move_history + [move])[-SEARCH_HISTORY_LIMIT:]
    child = GameState(
        board=board,
        side_to_move=state.side_to_move.opponent,
        move_history=history,
    )

    if move.destination == RED_DEN and move.piece.side is Side.BLUE:
        child.winner = Side.BLUE
        child.result = ResultType.DEN_ENTRY
        child.result_reason = "Blue entered the red den."
        return child
    if move.destination == BLUE_DEN and move.piece.side is Side.RED:
        child.winner = Side.RED
        child.result = ResultType.DEN_ENTRY
        child.result_reason = "Red entered the blue den."
        return child

    opponent = move.piece.side.opponent
    if move.captured is not None and not any(piece is not None and piece.side is opponent for piece in board):
        child.winner = move.piece.side
        child.result = ResultType.CAPTURE_ALL
        winner = "Blue" if move.piece.side is Side.BLUE else "Red"
        loser = "red" if move.piece.side is Side.BLUE else "blue"
        child.result_reason = f"{winner} captured all {loser} pieces."
    return child


def board_key(state: GameState) -> tuple:
    return tuple(None if piece is None else (piece.side.value, piece.kind.value) for piece in state.board)


def position_key(state: GameState) -> tuple:
    return board_key(state), state.side_to_move.value


def recent_position_counts(state: GameState) -> Counter[tuple]:
    counts: Counter[tuple] = Counter()
    board = state.board.copy()
    side_to_move = state.side_to_move
    counts[(tuple(None if piece is None else (piece.side.value, piece.kind.value) for piece in board), side_to_move.value)] += 1

    for move in reversed(state.move_history[-SEARCH_HISTORY_LIMIT:]):
        board[move.origin] = move.piece
        board[move.destination] = move.captured
        side_to_move = move.piece.side
        key = tuple(None if piece is None else (piece.side.value, piece.kind.value) for piece in board), side_to_move.value
        counts[key] += 1
    return counts
