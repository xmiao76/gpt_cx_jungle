"""Benchmark-only adapter for the pre-refactor opponent; never shipped."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks" / "legacy" / "src"))
from jungle.domain import GameState, Move, Piece, PieceType, Side
from jungle.ai.search import AlphaBetaAI, SearchConfig

def piece(code):
    return None if code == 0 else Piece(Side.BLUE if code > 0 else Side.RED, PieceType(abs(code)))

for line in sys.stdin:
    try:
        request = json.loads(line)
        position = request["position"]
        history = [
            Move(origin=m["from"], destination=m["to"], piece=piece(m["piece"]),
                 captured=piece(m["capture"]), is_jump=m["jump"])
            for m in request.get("history", [])
        ]
        state = GameState(board=[piece(p) for p in position["board"]],
                          side_to_move=Side(position["side"]), move_history=history)
        options = request.get("options", {})
        start = time.perf_counter()
        result = AlphaBetaAI(time_limit_ms=options.get("time_ms", 1950),
                             config=SearchConfig.hard()).choose_move(state)
        move = result.move
        print(json.dumps({
            "best_move": None if move is None else {
                "from": move.origin, "to": move.destination,
                "capture": 0 if move.captured is None else move.captured.rank * (1 if move.captured.side is Side.BLUE else -1),
                "jump": move.is_jump,
            },
            "depth": result.depth, "nodes": result.nodes,
            "elapsed_ms": (time.perf_counter() - start) * 1000,
        }), flush=True)
    except Exception as error:
        print(json.dumps({"error": str(error)}), flush=True)
