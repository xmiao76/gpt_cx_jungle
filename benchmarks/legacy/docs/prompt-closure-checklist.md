# Prompt Closure Checklist

- `prompt.md` remains at the repository root.
- The app still supports a working human-vs-AI GUI game.
- A visible `Flip Board` control exists and only changes the board display orientation.
- Board flipping does not change game state, side ownership, turn order, save/load behavior, or AI ownership.
- Blue remains the human-controlled side in standard play.
- Automated tests cover orientation mapping, controller invariants, and release validation.
- `tools/package_release.py` runs packaged `release/Jungle.exe --smoke-test` before reporting success.
- `docs/release-validation.md` is used for packaged-exe manual gameplay validation.
- The release folder contains `Jungle.exe`, bundled runtime files, and a README with:
  - `Model used: GPT 5.6-Sol`
  - `Reasoning effort: Ultra`
  - `Code agent used: Codex`
