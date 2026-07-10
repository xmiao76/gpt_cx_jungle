# Jungle Engine Search-Strength Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Hard AI reliably stronger while preserving its 1.8-second move budget, rules, UI, and existing public callers.

**Architecture:** Keep `AlphaBetaAI` as the public orchestrator, move bounded board evaluation and lightweight search transitions into focused private AI modules, and make iterative deepening abort incomplete work instead of accepting partial results. Validate strength with tactical positions, deterministic node-limited paired games, and a separate wall-clock responsiveness gate.

**Tech Stack:** Python 3.12, existing Jungle rules/domain modules, pytest, PyInstaller release workflow.

---

### Task 1: Search Limits and Lightweight Transitions

**Files:**
- Create: `src/jungle/ai/position.py`
- Modify: `src/jungle/ai/search.py`
- Test: `tests/unit/test_ai.py`
- Test: `tests/unit/test_ai_position.py`

- [x] Add failing tests proving incomplete iterations do not replace the last completed result and fallback moves are legal.
- [x] Add failing parity tests for lightweight board, turn, capture, history, den-win, and capture-all transitions.
- [x] Implement explicit deadline/node-limit abort handling and a bounded-history search transition.
- [x] Run focused tests and commit the passing checkpoint.

### Task 2: Efficient Strong Search

**Files:**
- Create: `src/jungle/ai/evaluation.py`
- Modify: `src/jungle/ai/search.py`
- Test: `tests/unit/test_ai.py`

- [x] Add failing tests for ply-aware wins, static ordering, PVS behavior, positional evaluation, and cycle avoidance.
- [x] Remove speculative tactical early returns and recursive search work from move ordering.
- [x] Implement principal-variation search, TT mate-score normalization, conservative LMR re-search, bounded quiescence, and path repetition handling.
- [x] Implement bounded Jungle evaluation for material, traps, den pressure/safety, mobility, rat roles, and jump lanes.
- [x] Run focused and full unit tests and commit the passing checkpoint.

### Task 3: Strength and Release Validation

**Files:**
- Modify: `tools/ai_benchmark.py`
- Modify: `README.md`
- Modify: `release/Jungle.zip`
- Test: `tests/unit/test_ai.py`
- Test: `tests/integration/test_packaging_smoke.py`

- [x] Replace duplicated deterministic games with varied legal paired openings and node-limited comparisons.
- [x] Gate all 11 tactical positions, a Hard score of at least 0.60 across match games, legal moves, and the two-second Hard response target.
- [x] Update benchmark documentation and run the complete test suite.
- [ ] Rebuild the release, run packaged smoke validation, review the diff, and commit the final checkpoint.
