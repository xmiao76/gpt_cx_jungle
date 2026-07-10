# Jungle

Desktop Jungle / Dou Shou Qi game for Windows with a Tkinter GUI, illustrated board, and built-in AI engine.

## Run

```powershell
python -m jungle
```

The human player controls Blue by default. Use **New Game** to choose AI difficulty and whether the player or AI starts.

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

Compare AI strength across baseline, medium, and hard profiles. The benchmark gates 11 tactical positions, eight node-limited paired opening games, four conversion games, and Hard's 1.8-second response depth:

```powershell
python -m tools.ai_benchmark
```

The command exits nonzero if Hard drops below 11/11 tactical positions, 0.50 in paired openings, 0.60 across all match games, depth 4, or the two-second response ceiling.

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

The release folder must contain `Jungle.exe`, bundled runtime files, `Jungle.zip`, and `README.txt`. The release README includes:

- `Model used: gpt-5.5`
- `Code agent used: Codex`

Manual packaged-exe validation is tracked in `docs/release-validation.md`.
