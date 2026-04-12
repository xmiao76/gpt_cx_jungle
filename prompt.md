Act as a senior software architect and technical lead.

Build a Windows desktop Jungle board game application with a GUI and built-in game engine so a human can play against the computer on a visual Jungle board. Use the standard Jungle / Dou Shou Qi rules described on this page as the baseline game specification:
https://en.wikipedia.org/wiki/Jungle_(board_game)

Choose the best implementation approach and provide a step-by-step plan covering development, testing, and release.

Requirements:
Choose the best programming language, architecture, and Windows GUI framework. Include all modules needed for a complete Jungle application. You may study existing engine designs, but all source code must be newly written for this application. Phase 1 must deliver a working GUI version where a human can play against the engine. The engine must be fast enough for a smooth, responsive experience. The app must be easy to build, run, and test locally. Testing must be integrated throughout development. Automated tests must be created and maintained during development. Defects found in testing or real gameplay must be fixed and retested until stable. The final application must complete full Jungle games correctly. AI-vs-AI mode is desirable if practical.

Release requirements:
The final build must produce a packaged .exe in a release folder. The release folder must also contain a README.txt explaining launch, gameplay, controls, and important notes. The packaged release .exe must be tested after packaging, not only in development. Release validation must confirm the .exe in the release folder starts and can be used to play a real Jungle game. Any defects found in the packaged release version must be fixed, rebuilt, and retested until the release executable passes all required checks. Save this instruction prompt as prompt.md in the codebase to keep a record of the requirements.

The Jungle program must fully support the standard rules from the above Wikipedia page, including:
- 7×9 board layout
- all special board areas: dens, traps, and rivers
- all 8 animal pieces per side with correct relative ranks
- legal movement validation for every piece
- turn handling and win/loss detection
- den-entry win condition
- capture-all-opponent-pieces win condition if supported by the chosen ruleset
- rat water movement rules
- lion and tiger river-jump rules
- blocking of lion/tiger jumps by a rat in the river
- correct capture restrictions involving rat, elephant, water, land, traps, and rank comparisons
- trap behavior, including temporary rank reduction while in the opponent’s trap
- prevention of illegal self-den entry
- clear handling of any ambiguous or variant rules by explicitly documenting the selected standard ruleset before implementation

If rule ambiguities or common variants are found, choose one clearly documented standard ruleset based on the cited Wikipedia page and keep the implementation consistent with that ruleset. Call out any optional variants separately, but do not let them delay the main playable release.

Please provide:
tech stack and justification; architecture; module breakdown and responsibilities; phased roadmap; test plan for each phase; automated testing approach; AI/engine approach; performance optimization; local build, run, and test workflow; defect-fix and regression-test workflow; packaging plan for the executable; release validation plan for the packaged .exe; expected contents of the release folder; suggested contents of README.txt; where and how prompt.md should be stored in the codebase; and completion criteria.

Also include recommendations for:
- board representation and game-state modeling
- move generation and legal-move filtering
- rules engine design for terrain-aware movement and capture logic
- AI search strategy suitable for Jungle (for example minimax/alpha-beta or another appropriate approach)
- evaluation function design for Jungle, including piece rank, position, mobility, den pressure, trap control, and tactical threats
- save/load support if practical
- undo/redo if practical
- move history and basic game logging
- debugging tools or developer diagnostics for validating rules correctness

Completion criteria:
The task is complete only when the application is playable and stable, can complete full Jungle games without crashes or rule errors, all required automated tests pass, the executable is packaged into the release folder, the packaged release .exe is tested directly from the release folder, the tested release executable can launch and play a real game, the release folder contains both the runnable .exe and a README.txt, and the codebase includes prompt.md containing this task prompt.
