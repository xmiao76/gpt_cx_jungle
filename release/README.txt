Jungle

Launch
- Extract the full Jungle.zip archive, then double-click Jungle.exe to start the game.

Gameplay
- Blue is the human player and moves first.
- Win by entering the red den or by capturing every red piece.
- Rats may enter rivers.
- Lions may jump both river spans; tigers may jump only the 2-square span.
- Any rat on a river path blocks that jump.
- Enemy traps reduce the trapped piece to rank 0 while it remains in the trap.

Controls
- Click a blue piece to select it.
- Click a highlighted square to move.
- New Game starts a fresh match and lets you choose AI difficulty.
- AI Starts starts a new match where the computer moves first.
- Undo rewinds the last human/computer turn pair when available.
- Redo reapplies the undone move if available.
- Save and Load store or restore the current game state as JSON.
- Flip Board changes only the visual orientation. It does not change sides, turns, or game state.
- Diagnostics shows legal moves and effective ranks for the selected piece.
- AI vs AI toggles automatic play for both sides.

Important Notes
- This build follows the documented ruleset in docs/ruleset.md.
- The packaged build also supports Jungle.exe --smoke-test for release validation.
- The source prompt is preserved as prompt.md in the repository root.
- Windows Defender may pause first launch briefly while it scans the executable.
- Model used: GPT 5.6-Sol
- Reasoning effort: Ultra
- Code agent used: Codex
