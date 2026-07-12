# Jungle

Desktop Jungle / Dou Shou Qi game for Windows with a Tkinter GUI, illustrated board, and built-in AI engine.

## Run

```powershell
python -m jungle
```

The human player controls Blue by default. Use **New Game** to choose AI difficulty and whether the player or AI starts. Hard uses a compact make/unmake search core, incremental Zobrist hashing, a fixed-size transposition table, bounded quiescence search, and an exact two-piece endgame tablebase.

## Gameplay

- Win by entering the opponent den or capturing every opposing piece.
- The rules interpretation is documented in `docs/ruleset.md`.
- The board shows land, river, trap, and den terrain with animal piece artwork.
- UI controls include New Game, AI Starts, Undo, Redo, Save, Load, Flip Board, Diagnostics, and AI vs AI.
- Flip Board changes only the display orientation. It does not swap sides, turns, saved state, or AI ownership.

## Develop

Install development tools:

```powershell
python -m pip install -e ".[dev]"
```

Run tests:

```powershell
python -m pytest
```

Compare AI strength across baseline, medium, and hard profiles. The benchmark gates 20 tactical/endgame positions, 24 paired opening games from 12 distinct openings, four conversion games, threefold-repetition adjudication, per-color results, decisiveness, and Hard's 1.8-second response depth. Match games use deterministic node budgets with a conservative 3:1 Hard-to-Baseline allocation to model the compact core's measured throughput advantage:

```powershell
python -m tools.ai_benchmark
```

The command exits nonzero if Hard drops below 20/20 tactical/endgame positions, 0.60 in paired openings, 0.50 with either color, a 0.25 decisive-game rate, 0.75 in conversion games, depth 6, or the two-second response ceiling.

Verify that the committed two-piece tablebase matches the engine rules and checksum:

```powershell
python -m tools.generate_tablebase --check
```

Regenerate UI assets:

```powershell
python -m tools.generate_ui_assets
```

## Package And Validate

Build the release folder, run the packaged smoke test, create `release/Jungle.zip`, and verify required artifacts:

```powershell
python -m tools.package_release
```

Run the packaged smoke test directly:

```powershell
release\Jungle.exe --smoke-test
```

The release folder must contain `Jungle.exe`, bundled runtime and tablebase files, `Jungle.zip`, and `README.txt`.

## Build Provenance

- `Model used: GPT 5.6-Sol`
- `Reasoning effort: Ultra`
- `Code agent used: Codex`

The same values are included in the generated release README.

Manual packaged-exe validation is tracked in `docs/release-validation.md`.
