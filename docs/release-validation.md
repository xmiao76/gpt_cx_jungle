# Release Validation

Use this checklist on the packaged executable before calling the prompt complete.

## Automated

- `python -m pytest` passes.
- `python -m tools.package_release` completes without errors.
- `release/Jungle.exe --smoke-test` exits with code 0.
- `release/release_smoke_result.txt` contains a valid `result` value and `turns` greater than 0.
- `release/Jungle.zip` contains `Jungle.exe`, `README.txt`, and bundled runtime files.
- `prompt.md` remains at the repository root.

## Manual Packaged-Exe Gameplay

- Launch `release/Jungle.exe` from the release folder.
- Start a player-first game and confirm Blue can select pieces and move to highlighted legal squares.
- Start an AI-first game and confirm the computer moves without freezing the window.
- Confirm river, trap, den, and land terrain are visually distinct.
- Confirm each animal piece is recognizable as an animal illustration rather than a plain letter.
- Capture a piece and confirm move history and board state update.
- Toggle Flip Board and confirm only the visual orientation changes.
- Save and load a game and confirm side to move, pieces, and history are preserved.
- Use Undo and Redo after a human/computer turn pair.
- Toggle Diagnostics and confirm selected-piece legal moves/effective rank are shown.
- Toggle AI vs AI and confirm both sides play automatically until stopped or game end.
- Confirm win/loss messaging appears after den entry or capture-all completion.

## Latest Evidence

- Automated tests: `108 passed` with `python -m pytest -q` on 2026-07-09.
- AI benchmark: Hard `11/11` tactical positions, `0.50` paired-opening score, `1.00` conversion score, `0.67` combined score, and depth 4 in 1800 ms.
- Packaged smoke: exit code 0, `winner=none`, `result=ongoing`, `turns=200` from `release/Jungle.exe --smoke-test`.
- Release archive: verified `Jungle.exe`, runtime DLLs, `README.txt`, `Capture.PNG`, and `knownIssue.txt` in `release/Jungle.zip`.
- Manual packaged-exe checklist: pending for each release candidate.
