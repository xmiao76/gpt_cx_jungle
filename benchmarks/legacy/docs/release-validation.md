# Release Validation

Use this checklist on the packaged executable before calling the prompt complete.

## Automated

- `python -m pytest` passes.
- `python -m tools.package_release` completes without errors.
- `release/Jungle.exe --smoke-test` exits with code 0.
- `release/release_smoke_result.txt` contains a valid `result` value and `turns` greater than 0.
- `release/Jungle.zip` contains `Jungle.exe`, `README.txt`, and bundled runtime files.
- The bundled `two_piece_v1.jgtb` passes its rules-hash and payload-checksum validation.
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

- Automated tests: `152 passed` with `python -m pytest -q` on 2026-07-20.
- AI benchmark: Hard `20/20` tactical/endgame positions, `0.812` paired-opening score (`0.708` Blue, `0.917` Red), `0.625` decisive rate, no match losses, `1.000` conversion score, and depth 6 / 34,979 nodes in 1800 ms.
- Packaged smoke: exit code 0, `winner=blue`, `result=den_entry`, `turns=45`, legal compact-Hard move, two successful bundled-tablebase probes, and a legal elephant capture of an enemy rat in its own trap from `release/Jungle.exe --smoke-test`.
- Packaged GUI probe: board/panel visibility and board click mapping passed at both `1180x760` startup and `1000x720` resized window dimensions.
- Release archive: verified `Jungle.exe`, runtime DLLs, `README.txt`, `Capture.PNG`, `knownIssue.txt`, and the checksummed two-piece tablebase in `release/Jungle.zip`.
- Manual packaged-exe checklist: pending for each release candidate.
