# Jungle AI Strength Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the built-in Jungle AI play stronger while preserving correct Dou Shou Qi rules, smooth local responsiveness, and the build/test/package workflow required by `prompt.md`.

**Architecture:** Keep the existing Python/Tkinter application and rules engine intact. Improve only the alpha-beta AI layer, add focused tactical regression tests, and make the benchmark enforce strength and responsiveness gates before claiming completion.

**Tech Stack:** Python 3, existing `jungle.ai.AlphaBetaAI`, pytest, the current `tools/ai_benchmark.py`, and the current PyInstaller packaging flow.

---

## Requirement Grounding

`prompt.md` requires a Windows desktop Jungle board game with a responsive built-in AI, automated tests throughout development, stable full-game play, support for human-vs-AI starts, correct rules, and tested packaging. This plan narrows the requested enhancement to the AI engine and its verification. It must not change Jungle rules, board-flip behavior, first-move selection behavior, UI assets, or packaging semantics except for documentation that explains the AI strength check.

The selected AI approach remains alpha-beta with iterative deepening because it already fits the local responsiveness requirement. The plan strengthens that approach with:

- A stronger default `SearchConfig` while retaining baseline for comparison.
- Tactical regression positions that encode known weak spots.
- Better move ordering through killer moves and history scores.
- Faster terminal-win scoring so the AI chooses shorter wins and slower losses.
- Positional evaluation for den lanes, trap pressure, rats, and exposed pieces.
- Benchmark gates so future tuning fails loudly when strength regresses.

## File Structure

- Modify: `src/jungle/ai/search.py`
  - Owns AI configuration, search, move ordering, evaluation, transposition table use, and helper scoring.
  - No rules changes belong here; it must call `jungle.rules.legal_moves`.
- Modify: `tests/unit/test_ai.py`
  - Keeps legacy/default-constructor compatibility checks and rule-sensitive AI smoke tests.
- Create: `tests/unit/test_ai_strength.py`
  - Owns tactical strength regression positions and short-time responsiveness checks.
- Modify: `tools/ai_benchmark.py`
  - Owns fixed-position and head-to-head AI gates used before completion.
- Create: `tests/integration/test_ai_strength_regression.py`
  - Owns a short default-AI play-through that catches severe responsiveness or legality regressions.
- Modify: `README.md`
  - Documents how to run the AI strength benchmark.

## Execution Notes

- Work from a non-`main` branch or isolated worktree before editing code.
- Keep commits frequent exactly as listed.
- Run each narrow test after its task before continuing.
- Do not replace the rules engine or introduce a new AI dependency.
- Do not change `prompt.md`; it already exists at repository root as required.

---

### Task 1: Add Tactical Strength Regression Tests

**Files:**
- Create: `tests/unit/test_ai_strength.py`
- No source changes in this task

- [ ] **Step 1: Create the failing tactical test module**

Create `tests/unit/test_ai_strength.py` with this full content:

```python
from __future__ import annotations

from jungle.ai import AlphaBetaAI, SearchConfig
from jungle.ai.search import TERMINAL_SCORE
from jungle.domain import GameState, Move, Piece, PieceType, Position, ResultType, Side


def make_state(pieces: dict[int, Piece], side_to_move: Side = Side.BLUE) -> GameState:
    board = [None] * 63
    for index, piece in pieces.items():
        board[index] = piece
    return GameState(board=board, side_to_move=side_to_move)


def choose(state: GameState, time_ms: int = 120) -> Move:
    result = AlphaBetaAI(time_ms, SearchConfig.candidate()).choose_move(state)
    assert result.move is not None
    assert result.elapsed_ms <= time_ms + 40
    return result.move


def test_candidate_rat_takes_elephant_from_right() -> None:
    state = make_state(
        {
            Position(2, 2).index: Piece(Side.BLUE, PieceType.RAT),
            Position(2, 1).index: Piece(Side.RED, PieceType.ELEPHANT),
            Position(8, 6).index: Piece(Side.RED, PieceType.LION),
        }
    )

    move = choose(state)

    assert move.origin == Position(2, 2).index
    assert move.destination == Position(2, 1).index


def test_candidate_rat_takes_elephant_from_above() -> None:
    state = make_state(
        {
            Position(1, 1).index: Piece(Side.BLUE, PieceType.RAT),
            Position(2, 1).index: Piece(Side.RED, PieceType.ELEPHANT),
            Position(8, 6).index: Piece(Side.RED, PieceType.LION),
        }
    )

    move = choose(state)

    assert move.origin == Position(1, 1).index
    assert move.destination == Position(2, 1).index


def test_candidate_prefers_tiger_two_square_river_jump() -> None:
    state = make_state(
        {
            Position(3, 0).index: Piece(Side.BLUE, PieceType.TIGER),
            Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
        }
    )

    move = choose(state)

    assert move.origin == Position(3, 0).index
    assert move.destination == Position(3, 3).index
    assert move.is_jump


def test_candidate_avoids_losing_piece_after_bad_capture() -> None:
    blue_cat = Position(6, 2).index
    red_rat = Position(5, 2).index
    safer_step = Position(6, 1).index
    state = make_state(
        {
            blue_cat: Piece(Side.BLUE, PieceType.CAT),
            red_rat: Piece(Side.RED, PieceType.RAT),
            Position(5, 3).index: Piece(Side.RED, PieceType.DOG),
            Position(8, 6).index: Piece(Side.RED, PieceType.LION),
        }
    )

    move = choose(state, time_ms=180)

    assert move.destination in {safer_step, Position(7, 2).index, Position(6, 3).index}
    assert move.destination != red_rat


def test_ai_prefers_fastest_den_entry_path() -> None:
    near_den_cat = Position(1, 3).index
    slower_lion = Position(3, 0).index
    state = make_state(
        {
            near_den_cat: Piece(Side.BLUE, PieceType.CAT),
            slower_lion: Piece(Side.BLUE, PieceType.LION),
            Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
        }
    )

    move = choose(state, time_ms=120)

    assert move.origin == near_den_cat
    assert move.destination == Position(0, 3).index


def test_terminal_scores_are_not_reused_across_different_plies() -> None:
    state = make_state(
        {
            Position(0, 3).index: Piece(Side.BLUE, PieceType.CAT),
            Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
        },
        side_to_move=Side.RED,
    )
    state.winner = Side.BLUE
    state.result = ResultType.DEN_ENTRY
    state.result_reason = "Blue entered red den"
    ai = AlphaBetaAI(120, SearchConfig.candidate())
    ai.deadline = float("inf")

    first_score = ai._alphabeta(state, depth=0, alpha=-1_000_000, beta=1_000_000, ply=1)
    second_score = ai._alphabeta(state, depth=0, alpha=-1_000_000, beta=1_000_000, ply=5)

    assert first_score == -TERMINAL_SCORE + 1
    assert second_score == -TERMINAL_SCORE + 5


def test_default_ai_reaches_search_depth_under_short_time_limit() -> None:
    state = make_state(
        {
            Position(6, 0).index: Piece(Side.BLUE, PieceType.ELEPHANT),
            Position(6, 2).index: Piece(Side.BLUE, PieceType.WOLF),
            Position(6, 4).index: Piece(Side.BLUE, PieceType.LEOPARD),
            Position(6, 6).index: Piece(Side.BLUE, PieceType.RAT),
            Position(7, 1).index: Piece(Side.BLUE, PieceType.CAT),
            Position(7, 5).index: Piece(Side.BLUE, PieceType.DOG),
            Position(8, 0).index: Piece(Side.BLUE, PieceType.TIGER),
            Position(8, 6).index: Piece(Side.BLUE, PieceType.LION),
            Position(2, 0).index: Piece(Side.RED, PieceType.RAT),
            Position(2, 2).index: Piece(Side.RED, PieceType.LEOPARD),
            Position(2, 4).index: Piece(Side.RED, PieceType.WOLF),
            Position(2, 6).index: Piece(Side.RED, PieceType.ELEPHANT),
            Position(1, 1).index: Piece(Side.RED, PieceType.DOG),
            Position(1, 5).index: Piece(Side.RED, PieceType.CAT),
            Position(0, 0).index: Piece(Side.RED, PieceType.LION),
            Position(0, 6).index: Piece(Side.RED, PieceType.TIGER),
        }
    )

    result = AlphaBetaAI(180).choose_move(state)

    assert result.move is not None
    assert result.depth >= 2
    assert result.elapsed_ms <= 230


def test_ai_values_entering_enemy_trap_near_den() -> None:
    cat = Position(2, 3).index
    trap = Position(1, 3).index
    state = make_state(
        {
            cat: Piece(Side.BLUE, PieceType.CAT),
            Position(8, 6).index: Piece(Side.RED, PieceType.RAT),
        }
    )

    move = choose(state, time_ms=120)

    assert move.origin == cat
    assert move.destination == trap


def test_ai_does_not_walk_high_value_piece_into_simple_capture() -> None:
    blue_elephant = Position(6, 0).index
    state = make_state(
        {
            blue_elephant: Piece(Side.BLUE, PieceType.ELEPHANT),
            Position(5, 1).index: Piece(Side.RED, PieceType.RAT),
            Position(8, 6).index: Piece(Side.RED, PieceType.LION),
        }
    )

    move = choose(state, time_ms=180)

    assert move.origin == blue_elephant
    assert move.destination != Position(6, 1).index
```

- [ ] **Step 2: Run the new tests to capture current failures**

Run:

```powershell
python -m pytest tests\unit\test_ai_strength.py -q
```

Expected before implementation: at least one test fails because `SearchConfig` has no `stronger()` profile, `_alphabeta` has no `ply` parameter, and the default AI is still baseline.

- [ ] **Step 3: Commit the failing tests**

```powershell
git add tests\unit\test_ai_strength.py
git commit -m "Add Jungle AI strength regression tests"
```

---

### Task 2: Make Stronger Search Config the Default

**Files:**
- Modify: `src/jungle/ai/search.py`
- Modify: `tests/unit/test_ai.py`

- [ ] **Step 1: Update `SearchConfig` with stronger profile flags**

In `src/jungle/ai/search.py`, replace the current `SearchConfig` class body with:

```python
@dataclass(frozen=True, slots=True)
class SearchConfig:
    label: str = "baseline"
    use_threat_score: bool = False
    use_quiescence: bool = False
    use_enhanced_ordering: bool = False
    quiescence_max_depth: int = 0
    quiescence_candidate_limit: int = 0
    threat_weight: int = 0
    use_killer_moves: bool = False
    use_history_ordering: bool = False

    @staticmethod
    def baseline() -> "SearchConfig":
        return SearchConfig()

    @staticmethod
    def candidate() -> "SearchConfig":
        return SearchConfig.stronger(label="candidate")

    @staticmethod
    def stronger(label: str = "stronger") -> "SearchConfig":
        return SearchConfig(
            label=label,
            use_threat_score=True,
            use_quiescence=True,
            use_enhanced_ordering=True,
            use_killer_moves=True,
            use_history_ordering=True,
            quiescence_max_depth=1,
            quiescence_candidate_limit=4,
            threat_weight=1,
        )
```

- [ ] **Step 2: Make the default constructor use the stronger profile**

In `AlphaBetaAI.__init__`, replace:

```python
self.config = SearchConfig.baseline() if config is None else config
```

with:

```python
self.config = SearchConfig.stronger() if config is None else config
```

- [ ] **Step 3: Add state containers used by ordering and attack caching**

In `AlphaBetaAI.__init__`, after `self.tt`, add:

```python
self.killer_moves: dict[int, list[tuple[int, int]]] = {}
self.history_scores: dict[tuple[Side, int, int], int] = {}
self.attack_cache: dict[tuple[tuple, int, Side], bool] = {}
```

- [ ] **Step 4: Clear the new per-search state**

In `choose_move`, after `self.tt.clear()`, add:

```python
self.killer_moves.clear()
self.history_scores.clear()
self.attack_cache.clear()
```

- [ ] **Step 5: Update default constructor tests**

In `tests/unit/test_ai.py`, replace `test_search_config_baseline_preserves_default_constructor` with:

```python
def test_search_config_stronger_is_default_constructor() -> None:
    game = Game()
    default = AlphaBetaAI(80).choose_move(game.state)
    stronger = AlphaBetaAI(80, SearchConfig.stronger()).choose_move(game.state)

    assert default.move is not None
    assert stronger.move is not None
    assert (default.move.origin, default.move.destination) == (stronger.move.origin, stronger.move.destination)
```

- [ ] **Step 6: Add compatibility coverage for positional construction**

Add this test immediately after the default constructor test:

```python
def test_search_config_legacy_positional_constructor_shape_is_preserved() -> None:
    config = SearchConfig("medium", True, False, True, 1, 4, 1)

    assert config.quiescence_max_depth == 1
    assert config.quiescence_candidate_limit == 4
    assert config.threat_weight == 1
    assert config.use_killer_moves is False
    assert config.use_history_ordering is False
```

- [ ] **Step 7: Run config-focused tests**

Run:

```powershell
python -m pytest tests\unit\test_ai.py::test_search_config_stronger_is_default_constructor tests\unit\test_ai.py::test_search_config_legacy_positional_constructor_shape_is_preserved -q
```

Expected:

```text
2 passed
```

- [ ] **Step 8: Commit**

```powershell
git add src\jungle\ai\search.py tests\unit\test_ai.py
git commit -m "Use stronger Jungle AI profile by default"
```

---

### Task 3: Prefer Faster Wins and Avoid Terminal Score Reuse Across Plies

**Files:**
- Modify: `src/jungle/ai/search.py`
- Test: `tests/unit/test_ai_strength.py`

- [ ] **Step 1: Change root search to pass ply**

In `_search_root`, replace:

```python
score = -self._alphabeta(self.apply(state, move), depth - 1, -math.inf, -alpha)
```

with:

```python
score = -self._alphabeta(self.apply(state, move), depth - 1, -math.inf, -alpha, 1)
```

- [ ] **Step 2: Change `_alphabeta` signature**

Replace:

```python
def _alphabeta(self, state: GameState, depth: int, alpha: float, beta: float) -> int:
```

with:

```python
def _alphabeta(self, state: GameState, depth: int, alpha: float, beta: float, ply: int) -> int:
```

- [ ] **Step 3: Return terminal scores before writing transposition entries**

Inside `_alphabeta`, replace:

```python
if state.result_reason:
    score = self.evaluate(state, state.side_to_move)
    self.tt[key] = TTEntry(depth, score, EXACT, None)
    return score
```

with:

```python
if state.result_reason:
    return self.terminal_score(state, state.side_to_move, ply)
```

- [ ] **Step 4: Propagate ply into recursive calls**

Inside `_alphabeta`, replace:

```python
score = -self._alphabeta(child, depth - 1, -beta, -alpha)
```

with:

```python
score = -self._alphabeta(child, depth - 1, -beta, -alpha, ply + 1)
```

- [ ] **Step 5: Add terminal scoring helper**

After `evaluate`, add:

```python
def terminal_score(self, state: GameState, perspective: Side, ply: int) -> int:
    if state.winner is perspective:
        return TERMINAL_SCORE - ply
    if state.winner is perspective.opponent:
        return -TERMINAL_SCORE + ply
    return self.evaluate(state, perspective)
```

- [ ] **Step 6: Run terminal scoring test**

Run:

```powershell
python -m pytest tests\unit\test_ai_strength.py::test_terminal_scores_are_not_reused_across_different_plies -q
```

Expected:

```text
1 passed
```

- [ ] **Step 7: Commit**

```powershell
git add src\jungle\ai\search.py tests\unit\test_ai_strength.py
git commit -m "Prefer faster Jungle wins in search scoring"
```

---

### Task 4: Improve Move Ordering Without Changing Rules

**Files:**
- Modify: `src/jungle/ai/search.py`
- Test: `tests/unit/test_ai_strength.py`

- [ ] **Step 1: Gate expensive child analysis for large fast searches**

After `forcing_moves`, add:

```python
def use_deep_ordering(self, moves: list[Move]) -> bool:
    return self.profile is SearchProfile.FULL or len(moves) <= 12
```

- [ ] **Step 2: Pass ply into root ordering**

In `_search_root`, replace:

```python
moves = self.order_moves(state, legal_moves(state), preferred_move=preferred_move, tactical=True)
```

with:

```python
moves = self.order_moves(state, legal_moves(state), preferred_move=preferred_move, tactical=True, ply=0)
```

- [ ] **Step 3: Pass ply into recursive ordering**

Inside `_alphabeta`, replace:

```python
for move in self.order_moves(state, moves, preferred_move=preferred):
```

with:

```python
for move in self.order_moves(state, moves, preferred_move=preferred, ply=ply):
```

- [ ] **Step 4: Record cutoff moves**

Inside `_alphabeta`, replace:

```python
if alpha >= beta:
    break
```

with:

```python
if alpha >= beta:
    self.record_cutoff(state, move, depth, ply)
    break
```

- [ ] **Step 5: Update `order_moves` signature**

Replace the `order_moves` signature with:

```python
def order_moves(
    self,
    state: GameState,
    moves: list[Move],
    preferred_move: Move | None = None,
    tactical: bool = False,
    ply: int = 0,
) -> list[Move]:
```

- [ ] **Step 6: Replace the `move_score` implementation**

Inside `order_moves`, replace the current `move_score` function with:

```python
deep_ordering = self.use_deep_ordering(moves)

def move_score(move: Move) -> int:
    score = 0
    if preferred_move is not None and move.origin == preferred_move.origin and move.destination == preferred_move.destination:
        score += 1_000_000
    move_key = (move.origin, move.destination)
    if self.config.use_killer_moves and move_key in self.killer_moves.get(ply, []):
        score += 120_000
    if self.config.use_history_ordering:
        score += self.history_scores.get((state.side_to_move, move.origin, move.destination), 0)
    if move.captured is not None:
        score += 30_000 + PIECE_VALUES[move.captured.kind] * 20 - PIECE_VALUES[move.piece.kind]
    if move.destination == target_den:
        score += 800_000
    if move.is_jump:
        score += 1_500
    distance = Position.from_index(move.destination).manhattan_distance(Position.from_index(target_den))
    score += (18 - distance) * 120
    if move.destination in self.enemy_traps_for(state.side_to_move):
        score += 2_200
    if deep_ordering:
        child = self.apply(state, move)
        if child.winner is state.side_to_move:
            score += 900_000
        is_attacked = self.is_square_attacked(child, move.destination, opponent) and child.winner is None
        if tactical and is_attacked:
            score -= PIECE_VALUES[move.piece.kind] * 16
        if tactical and self.find_immediate_win(child, opponent) is not None:
            score -= 80_000
        if self.config.use_enhanced_ordering:
            if self.find_immediate_win(child, state.side_to_move) is not None:
                score += 18_000
            if is_attacked:
                score -= PIECE_VALUES[move.piece.kind] * 8
            if move.destination in self.own_traps_for(state.side_to_move):
                score += 400
    return score
```

- [ ] **Step 7: Add cutoff recording helper**

After `move_from_key`, add:

```python
def record_cutoff(self, state: GameState, move: Move, depth: int, ply: int) -> None:
    if move.captured is not None:
        return
    move_key = (move.origin, move.destination)
    if self.config.use_killer_moves:
        killers = self.killer_moves.setdefault(ply, [])
        if move_key not in killers:
            killers.insert(0, move_key)
            del killers[2:]
    if self.config.use_history_ordering:
        history_key = (state.side_to_move, move.origin, move.destination)
        self.history_scores[history_key] = self.history_scores.get(history_key, 0) + depth * depth
```

- [ ] **Step 8: Avoid repeated opponent-win checks in `forcing_moves`**

In `forcing_moves`, add this after `opponent = state.side_to_move.opponent`:

```python
opponent_immediate_win = self.find_immediate_win(state, opponent)
```

Then replace the non-capture branch with:

```python
if opponent_immediate_win is None:
    continue
child = self.apply(state, move)
if child.winner is state.side_to_move or self.find_immediate_win(child, opponent) is None:
    forcing.append(move)
```

- [ ] **Step 9: Run move-ordering responsiveness test**

Run:

```powershell
python -m pytest tests\unit\test_ai_strength.py::test_default_ai_reaches_search_depth_under_short_time_limit -q
```

Expected:

```text
1 passed
```

- [ ] **Step 10: Commit**

```powershell
git add src\jungle\ai\search.py tests\unit\test_ai_strength.py
git commit -m "Improve Jungle AI move ordering"
```

---

### Task 5: Strengthen Positional Evaluation

**Files:**
- Modify: `src/jungle/ai/search.py`
- Test: `tests/unit/test_ai_strength.py`

- [ ] **Step 1: Add den-lane scoring**

After `jump_lane_score`, add:

```python
def den_lane_score(self, state: GameState, index: int, piece: Piece) -> int:
    target = Position.from_index(RED_DEN if piece.side is Side.BLUE else BLUE_DEN)
    current = Position.from_index(index)
    score = 0
    if current.col == target.col:
        score += 1
    if abs(current.col - target.col) == 1 and current.manhattan_distance(target) <= 3:
        score += 1
    if index in self.enemy_traps_for(piece.side):
        score += 1
    return score
```

- [ ] **Step 2: Add rat role scoring**

After `den_lane_score`, add:

```python
def rat_role_score(self, state: GameState, index: int, piece: Piece) -> int:
    if piece.kind is not PieceType.RAT:
        return 0
    score = 0
    if index in WATER:
        score += 180
    turn_state = self.with_side_to_move(state, piece.side)
    for move in legal_moves(turn_state):
        if move.origin != index:
            continue
        if move.captured is not None and move.captured.kind is PieceType.ELEPHANT:
            score += 900
    return score
```

- [ ] **Step 3: Use the new scoring in `piece_square_score`**

In `piece_square_score`, after the trap penalty block:

```python
if TRAP_OWNER.get(index) is piece.side.opponent:
    local -= PIECE_VALUES[piece.kind] // 2
```

add:

```python
if self.config.use_threat_score:
    local += self.den_lane_score(state, index, piece)
if self.config.use_threat_score:
    local += self.rat_role_score(state, index, piece)
```

- [ ] **Step 4: Penalize exposed pieces**

At the end of `piece_square_score`, before `return local`, add:

```python
if self.config.use_threat_score and self.is_square_attacked(state, index, piece.side.opponent):
    local -= PIECE_VALUES[piece.kind] // 3
```

- [ ] **Step 5: Cache attack checks**

Replace `is_square_attacked` with:

```python
def is_square_attacked(self, state: GameState, index: int, by_side: Side) -> bool:
    if state.winner is not None:
        return False
    key = (self._hash_state(state), index, by_side)
    cached = self.attack_cache.get(key)
    if cached is not None:
        return cached
    attack_state = self.with_side_to_move(state, by_side)
    attacked = any(move.destination == index for move in legal_moves(attack_state))
    self.attack_cache[key] = attacked
    return attacked
```

- [ ] **Step 6: Run positional tests**

Run:

```powershell
python -m pytest tests\unit\test_ai_strength.py::test_ai_values_entering_enemy_trap_near_den tests\unit\test_ai_strength.py::test_ai_does_not_walk_high_value_piece_into_simple_capture tests\unit\test_ai_strength.py::test_candidate_avoids_losing_piece_after_bad_capture -q
```

Expected:

```text
3 passed
```

- [ ] **Step 7: Run all AI unit tests**

Run:

```powershell
python -m pytest tests\unit\test_ai.py tests\unit\test_ai_strength.py -q
```

Expected:

```text
all selected tests passed
```

- [ ] **Step 8: Commit**

```powershell
git add src\jungle\ai\search.py tests\unit\test_ai_strength.py
git commit -m "Teach Jungle AI safer positional evaluation"
```

---

### Task 6: Enforce AI Strength Gates in the Benchmark

**Files:**
- Modify: `tools/ai_benchmark.py`
- Create: `tests/integration/test_ai_strength_regression.py`

- [ ] **Step 1: Update benchmark `main` to include stronger config gates**

At the bottom of `tools/ai_benchmark.py`, replace the current `main()` with:

```python
def main() -> None:
    baseline_config = SearchConfig.baseline()
    candidate_config = SearchConfig.candidate()
    stronger_config = SearchConfig.stronger()
    baseline = evaluate_fixed_positions(baseline_config)
    candidate = evaluate_fixed_positions(candidate_config)
    stronger = evaluate_fixed_positions(stronger_config)
    head_to_head_score = run_head_to_head(stronger_config, baseline_config)
    print_summary(baseline, stronger, head_to_head_score)

    if stronger.passed < stronger.total:
        raise SystemExit(f"stronger config failed fixed positions: {stronger.passed}/{stronger.total}")
    if stronger.passed < candidate.passed:
        raise SystemExit("stronger config regressed below candidate fixed-position score")
    if head_to_head_score < 0.50:
        raise SystemExit(f"stronger head-to-head score too low: {head_to_head_score:.2f}")
```

- [ ] **Step 2: Create default-AI integration regression test**

Create `tests/integration/test_ai_strength_regression.py` with:

```python
from __future__ import annotations

from jungle.ai import AlphaBetaAI
from jungle.engine import Game


def test_default_ai_can_play_twenty_plies_responsively() -> None:
    game = Game()
    elapsed_total = 0.0

    for _ in range(20):
        result = AlphaBetaAI(120).choose_move(game.state)
        assert result.move is not None
        assert result.elapsed_ms <= 180
        elapsed_total += result.elapsed_ms
        game.apply_move(result.move)
        if game.state.winner is not None:
            break

    assert elapsed_total <= 3600
    assert len(game.state.move_history) >= 10
```

- [ ] **Step 3: Run benchmark and integration test**

Run:

```powershell
python tools\ai_benchmark.py
python -m pytest tests\integration\test_ai_strength_regression.py -q
```

Expected benchmark acceptance:

```text
stronger: passed=10/10
candidate_head_to_head_score=0.50
```

The printed label may remain `candidate_head_to_head_score` because `print_summary` names that field generically. Accept the run only when the process exits with code `0`.

Expected pytest result:

```text
1 passed
```

- [ ] **Step 4: Commit**

```powershell
git add tools\ai_benchmark.py tests\integration\test_ai_strength_regression.py
git commit -m "Gate Jungle AI strength in benchmark validation"
```

---

### Task 7: Document and Verify Against `prompt.md`

**Files:**
- Modify: `README.md`
- No source changes unless verification finds a defect

- [ ] **Step 1: Add AI strength section to README**

Append this section after the existing test/run workflow in `README.md`:

````markdown
## AI strength checks

The default computer player uses the stronger alpha-beta profile in `src/jungle/ai/search.py`.
The baseline profile remains available for comparison, and strength is validated with:

```powershell
python tools\ai_benchmark.py
```

The benchmark must keep the stronger profile at `10/10` fixed tactical positions and at least an even score against the baseline head-to-head sample.
````

- [ ] **Step 2: Run the focused verification suite**

Run:

```powershell
python -m pytest tests\unit\test_ai.py tests\unit\test_ai_strength.py tests\integration\test_ai_strength_regression.py -q
python tools\ai_benchmark.py
```

Expected:

```text
all selected tests passed
stronger: passed=10/10
candidate_head_to_head_score=0.50
```

- [ ] **Step 3: Run full regression tests**

Run:

```powershell
python -m pytest -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 4: Run packaging smoke checks from the existing workflow**

Run:

```powershell
python tools\package_release.py
python tools\smoke_release.py
```

Expected:

```text
release package created
smoke release passed
```

If exact wording differs, accept only a zero exit code and verify `release\Jungle.exe`, `release\Jungle.zip`, and `release\README.txt` exist.

- [ ] **Step 5: Verify `prompt.md` release requirements still hold**

Run:

```powershell
Test-Path prompt.md
Test-Path release\README.txt
Select-String -Path release\README.txt -Pattern "model|code agent|Codex|GPT" -CaseSensitive:$false
```

Expected:

```text
True
True
at least one README line identifying the model and code agent
```

- [ ] **Step 6: Commit**

```powershell
git add README.md release\README.txt release\Jungle.zip
git commit -m "Document Jungle AI strength validation"
```

If packaging rebuilds `release\Jungle.exe`, add it only if the repository already tracks it. Do not force-add ignored binary artifacts.

---

## Final Verification Checklist

- [ ] `python -m pytest tests\unit\test_ai.py tests\unit\test_ai_strength.py tests\integration\test_ai_strength_regression.py -q`
- [ ] `python -m pytest -q`
- [ ] `python tools\ai_benchmark.py`
- [ ] `python tools\package_release.py`
- [ ] `python tools\smoke_release.py`
- [ ] `Test-Path prompt.md` returns `True`
- [ ] `release\README.txt` identifies the model and code agent as required by `prompt.md`
- [ ] Manual app launch still allows human first and AI first starts
- [ ] Manual app launch still keeps board flip display-only
- [ ] No tests in `tests\unit\test_rules.py` were changed to accommodate AI behavior

## Completion Criteria

This work is complete when:

- `AlphaBetaAI()` defaults to `SearchConfig.stronger()`.
- `SearchConfig.baseline()` remains available for benchmark comparison.
- Candidate and stronger profiles preserve the selected Jungle rules, including the prompt's lion/tiger river-jump clarification.
- Tactical AI tests pass under short time limits.
- The benchmark exits successfully and stronger fixed-position score is `10/10`.
- Stronger head-to-head score against baseline is at least `0.50`.
- Full pytest suite passes.
- Release packaging and smoke checks still pass.
- `prompt.md` remains at repository root.
- Release README still includes the required model/code-agent statement.

## Self-Review

- Spec coverage: The plan addresses `prompt.md` AI responsiveness, full-game stability, integrated automated tests, bug regression workflow, local benchmark validation, packaging verification, and preservation of the existing first-move/board-flip behavior. It deliberately does not change GUI or rules code because the request is to make the AI engine stronger.
- Placeholder scan: No placeholder-only steps are present. Every code-changing step includes exact code and every verification step includes exact commands and acceptance criteria.
- Type consistency: The plan uses existing types and modules: `AlphaBetaAI`, `SearchConfig`, `GameState`, `Move`, `Piece`, `PieceType`, `Position`, `ResultType`, `Side`, `Game`, `legal_moves`, and `TERMINAL_SCORE`. New helper signatures are introduced before later steps call them.
