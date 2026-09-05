"""Independent pre-rewrite rules oracle; benchmark/test only, never shipped."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks" / "legacy" / "src"))
from jungle.domain import GameState, Piece, PieceType, Side
from jungle.engine.game import Game
from jungle.rules import legal_moves, evaluate_result


def piece(code):
    return None if code == 0 else Piece(Side.BLUE if code > 0 else Side.RED, PieceType(abs(code)))


def code(animal):
    return 0 if animal is None else animal.rank * (1 if animal.side is Side.BLUE else -1)


rows = [json.loads(line)["expected"] for line in sys.stdin if line.strip()]
transitions = 0
for index, expected in enumerate(rows):
    position = expected["position"]
    state = GameState(board=[piece(value) for value in position["board"]], side_to_move=Side(position["side"]))
    result = evaluate_result(state)
    kind = result.status.value
    # The original rules oracle has no finite draw counter. Apply only the new,
    # explicitly specified adjudication after checking decisive outcomes first.
    if kind == "ongoing" and position["quiet"] >= 100:
        kind = "no_capture_draw"
    winner = None if result.winner is None else result.winner.value
    assert (kind, winner) == (expected["outcome"]["kind"], expected["outcome"]["winner"]), index
    moves = [] if kind != "ongoing" else legal_moves(state)
    actual = sorted((move.origin, move.destination, code(move.captured), move.is_jump) for move in moves)
    wanted = sorted((move["from"], move["to"], move["capture"], move["jump"]) for move in expected["moves"])
    assert actual == wanted, (index, actual, wanted)
    if kind == "ongoing" and index + 1 < len(rows):
        after = rows[index + 1]["position"]
        origin = next(square for square, value in enumerate(position["board"]) if value != 0 and after["board"][square] == 0)
        destination = next(square for square, value in enumerate(after["board"]) if value != 0 and value != position["board"][square])
        game = Game(state)
        applied = game.apply_coordinates(origin, destination)
        quiet = 0 if applied.move.captured else position["quiet"] + 1
        assert [code(value) for value in game.state.board] == after["board"], index
        assert (game.state.side_to_move.value, quiet) == (after["side"], after["quiet"]), index
        transitions += 1
print(json.dumps({"passed": True, "count": len(rows), "transitions": transitions, "oracle": "pre-rewrite Python rules plus explicit quiet-100 adjudication"}))
