# Jungle Ruleset

This project follows the standard rules described on the Wikipedia Jungle / Dou Shou Qi page:
<https://en.wikipedia.org/wiki/Jungle_(board_game)>

## Core Rules

- Board size is 7 columns by 9 rows.
- Blue moves first.
- Pieces move orthogonally by one square unless a lion or tiger performs a legal river jump.
- A piece may not enter its own den.
- Entering the opponent's den wins immediately.
- Capturing all opponent pieces also wins.

## Terrain

- Water squares may only be occupied by rats.
- Lions may jump across a river to the next land square on the opposite edge across either 2 or 3 river squares.
- Tigers may jump only across the 2-river-square span to the next land square on the opposite edge.
- A lion or tiger jump is illegal if any river square on that jump path contains a rat of either side.
- Traps reduce the effective rank of an enemy piece inside that trap to 0.

## Capture Interpretation

The Wikipedia page notes several published variations. This project uses the following consistent baseline:

- A piece may capture an opposing piece of equal or lower effective rank.
- A rat may capture an elephant only when the rat attacks from land.
- An elephant may not capture a rat.
- A rat in water may only capture another rat in water.
- A piece on land may not capture a rat in water.
- A rat in water may not capture a piece on land.
- Trap reduction affects only pieces inside the opponent's traps and lasts only while they remain there.

## Explicitly Excluded Variants

- Elephant capturing rat.
- Universal traps.
- Leopard river jumping.
- Lion horizontal jump disabled.
- Tiger jumping across the 3-river-square span.
- Dog water movement.
- Alternate rank ordering between lion and tiger.
