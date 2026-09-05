# Prompt Template: Jungle (Dou Shou Qi) - Desktop + Browser

## Purpose and reuse

Act as a software architect and developer. Plan, build, test, package, and deploy a Jungle board game with a graphical board and a built-in computer opponent, using the defaults below.

**Engine objective: while meeting every requirement and staying within the per-move response-time limits, make the Jungle engine play as strongly as practically possible.** Optimize playing strength throughout development, with Hard as the strongest profile. A working baseline is the starting point for measured improvement; stronger play must not come from exceeding the time limit, weakening correctness, omitting features, or dropping either target.

This specification is independent of the development model, coding agent, programming language, and framework. The model base name below is a user-supplied label for deployment naming; it does not select a model, coding agent, or implementation stack. Use the tools available in the current environment; no named agent, model provider, proprietary plugin, or agent-specific command is required. The in-game AI must run locally and must not require a hosted AI service, account, or API key.

To reuse this template, change only `model_base_name` below, then copy this single file into the destination project or coding agent. It is the only project file that needs to be copied; the linked rules reference supplies the board setup, and no companion project documents need to be copied or supplied. All other choices have defaults or are derived automatically; no other placeholder needs manual replacement. Technology names, file paths, and tool commands introduced as examples are illustrative, not mandatory implementation choices. Equivalent tools and repository layouts are acceptable if documented.

Keep project-specific rule decisions, implementation decisions, setup and release instructions, strength summaries, and validation evidence in this file. Fill in the implementation record at the end during development without removing the requirements above it. Generated application source, assets, tests, dependency manifests, packages, and raw test/benchmark outputs are implementation deliverables, not additional prerequisite documents.

## Only setting to change

- `model_base_name = gpt`

Use a short label containing lowercase letters, digits, and single hyphens between words; start and end with a letter or digit. For example, a label entered as `muse` produces the deployment name and URL shown below. Use the supplied value exactly; do not infer or replace it from the coding agent's detected model identity.

Derived automatically (do not configure separately):

- Cloudflare Pages project name: `{model_base_name}-jungle`.
- Expected production URL: `https://{model_base_name}-jungle.pages.dev`.

For example, the label `muse` produces `muse-jungle` and `https://muse-jungle.pages.dev`. Substitute the supplied label wherever `{model_base_name}` appears in generated files, documentation, and deployment commands. Keep naming in generated configuration sourced from that one value.

## Defaults (no configuration needed)

- Display name: Jungle.
- Work mode: `plan-and-build`; provide the plan, then implement, test, package, deploy, and verify.
- Desktop target: Windows, with a packaged `.exe` and any required bundled runtime files.
- Browser targets: current stable Chrome and Firefox; record the exact versions tested.
- AI move-response limits: Easy **100 ms**, Medium **500 ms**, Hard **2,000 ms** per move in both desktop and browser, after engine initialization, on the documented supported test hardware. These are defaults, not additional settings the requester must configure.
- Languages, UI framework, desktop runtime/shell, and build/test tools: select automatically to meet this specification. A single language is not required for every layer.
- Hosting: Cloudflare Pages free tier, with zero recurring hosting fees, static files only, no Pages Functions, and no paid features.
- Public deployment: required, using the derived project name and production URL.

Apply these defaults without asking the requester to fill in additional settings. The requester may override a default in accompanying instructions, such as asking for `plan-only`, a different desktop platform, a preferred language, or local-only browser delivery; no additional configuration fields are required. Respect such preferences when feasible. If a preference cannot satisfy a required target or performance budget, explain the concrete incompatibility and available alternatives before changing it. Do not silently drop a target.

## Product and delivery requirements

Deliver one maintained codebase that supports:

1. A packaged local desktop application for Windows by default, or the desktop targets explicitly requested, playable without a remote application server or an internet connection after installation.
2. A browser game distributed as static files, with all rules and AI computation running on the player's device.

The desktop-first workflow is mandatory. Phase 1 must deliver a playable human-vs-AI desktop app. Every feature and engine change must pass the relevant desktop checks before web release. A small browser compatibility prototype may be built early to validate the chosen stack; public deployment follows a stable, tested desktop version.

Keep one shared implementation of the rules and AI. Share UI assets and presentation logic wherever practical. Platform-specific presentation or integration code is allowed when needed by the chosen stack, but must not duplicate rules or search logic. Both targets must offer the same required gameplay and controls.

## Technology selection and feasibility

Select the stack and engine design that deliver the strongest practical, measured play within the fixed response-time limits while meeting every other requirement and any supplied language preferences. Treat correctness, required features, responsiveness, packaging, and static browser execution as constraints on the strength objective. Do not assume that a particular language, native compilation, or runtime automatically gives greater playing strength.

- The shared engine may run as native code, interpreted or managed code, transpiled code, or a browser-compatible runtime/artifact such as WebAssembly. The same maintained engine source must supply both targets; a separately rewritten browser engine does not meet this requirement.
- Native compilation, a webview desktop shell, byte-for-byte identical UI bundles, and any particular rendering API are optional implementation choices.
- Demonstrate early that the chosen engine and its dependencies can run locally on desktop and entirely client-side in a browser. Document runtime downloads, startup cost, payload size, platform restrictions, and required static-host capabilities.
- Evaluate plausible stacks against the requirements and any stated language preferences. Build small feasibility or performance prototypes where uncertainty warrants them; implementing several complete engines in different languages is not a prerequisite.
- Use the default move-response limits above unless the requester explicitly overrides them. In the plan, document target hardware, supported foreground runtime conditions, startup and payload targets, and a UI responsiveness threshold. Measure response time from an AI turn becoming ready for action until its legal move is available to the UI for rendering, including queueing and bridge/message overhead. Measure initialization and animation time separately.
- Allocate search time within the total response limit, reserve time for returning the result, and enforce a wall-clock deadline even when search also has a node limit. Keep a legal fallback available whenever legal moves exist and return the best move found before the deadline. Tune search work per target without silently increasing its response limit.
- Measure the selected implementation on a fixed position corpus: elapsed time, completed search depth where applicable, nodes/sec where meaningful, shipped payload size, and startup time. State the hardware, runtime, build configuration, seed, and budget used.
- Pursue and measure improvements in search, move ordering, evaluation, endgame handling, and runtime efficiency as appropriate to the chosen design. Compare candidates against a recorded baseline using repeatable matches at equal per-move wall-clock limits on the same hardware for each target. Keep the strongest validated candidate that meets all constraints, and record rejected or inconclusive experiments. Use Elo estimates with confidence intervals only when the match sample supports them; distinguish measured results, estimates, and future experiments. Do not invent benchmark evidence at the planning stage or claim a globally optimal engine.
- Keep expensive search off the UI event loop using a worker, background task, thread, process, or another supported execution mechanism. Where these are unavailable, demonstrate bounded cooperative scheduling that meets the same responsiveness and cancellation requirements.
- Record toolchain and dependency versions in the stack's normal manifests or lockfiles and document how to reproduce builds. Choose suitable test, automation, and deployment tools without depending on a particular coding agent.

Language independence means any stack that demonstrably meets these constraints may be used; it does not guarantee that every language or library has a viable browser runtime.

## Rules specification

Use [Jungle (board game)](https://en.wikipedia.org/wiki/Jungle_(board_game)) as the main requirement reference for the board dimensions, terrain layout, animal ranks, and initial piece positions, including its setup diagrams. Consult the [AncientChess.com rules booklet](https://veryspecial.us/free-downloads/AncientChess.com-DouShouQi.pdf) if setup details are unclear. Record the reference revision or access date in this file's implementation record. If setup details cannot be verified from either reference, report the unresolved details and continue work that does not depend on them.

The referenced setup and the explicit rules below define the application's behavior. Explicit rules in this file take precedence when published variants differ. The shared engine is the single executable implementation; an implementation bug must not redefine the rules. Keep rule decisions and any explicitly requested variants in this file, and keep the UI instructions and tests consistent with them. The UI must display legal moves, outcomes, and explanations supplied by the engine.

### Turns, movement, captures, and traps

- Blue moves first. Players alternate one legal move at a time; passing is not allowed.
- A normal move is one square horizontally or vertically, never diagonally. A piece may move to an empty permitted square or capture an opponent on its destination; it may not land on a friendly piece.
- No piece may enter its own den. Entering the opponent's den wins immediately.
- Only rats may enter water. A rat may move between water and an adjacent empty dry square. Captures across a water/dry boundary are forbidden in either direction; in water, a rat may capture only an opposing rat in water.
- On dry terrain, a rat may capture an elephant. An elephant may capture a rat only when that rat occupies a trap owned by the elephant's side. Apply these animal-specific exceptions before the ordinary rank comparison.
- For other captures on dry terrain, the attacker's effective rank at its origin must be at least the defender's effective rank at its destination.
- A piece in an opponent-owned trap has effective rank zero while it remains there; it regains its normal rank after leaving. A piece in its own side's trap keeps its normal rank. Traps belong to their original side throughout the game.
- Only the lion and tiger have river-jump moves, with the exact restrictions below. Other animals cannot jump.

### Game outcomes and draw policy

- A side wins by entering the opponent's den or capturing every opposing piece. A side that has no legal move on its turn loses.
- Check den entry first, elimination second, and no-legal-move loss third. These decisive results take precedence over a draw reached on the same move.
- Include a finite no-capture draw limit. Before implementation, choose and record its exact numeric value in this file's implementation record; one ply means one player's move. Start the counter at zero, reset it to zero after a capture, and increment it after every non-capturing move. Declare a draw when the recorded limit is reached without a decisive result.
- Record any separate repetition-draw policy here before implementation, including how repeated positions are identified and counted, or explicitly state that no separate repetition rule is used. These are implementation decisions, not extra settings the requester must supply.
- Undo must restore the position, side to move, result, no-capture counter, and any repetition history consistently. Once a game has ended, reject further moves until undo or a new game makes play available.

### River-jump interpretation

Preserve the following explicit jump behavior when reusing this template unless the requester changes it. Treat it as the application's selected rules profile, rather than relying on ambiguous direction names in external descriptions.

For the jump coordinates below, use zero-based `(row, column)` coordinates in the unflipped view: row `0` is at Red's home edge, rows increase toward Blue's home edge, and columns increase from left to right starting at `0`. Board flipping never changes these logical coordinates or the permitted jump directions.

- A jump starts on land next to a river and ends on the first land square directly across it.
- **Lion:** may jump in both directions:
  - North-south (vertical): row `2` to row `6`, or the reverse, at columns `1,2,4,5`; cross three water squares. Distance `abs(dr)=4, dc=0`.
  - East-west (horizontal): column `0` to `3`, or `3` to `6`, or the reverse, at rows `3,4,5`; cross two water squares. Distance `abs(dc)=3, dr=0`.
- **Tiger:** may jump only east-west across two water squares as above. North-south jumps are disabled. They may be added only as a documented optional variant, disabled by default.
- **Rat blocking:** a rat of either color on any intervening water square makes the jump illegal. Check every crossed square.
- A jump may land on an empty square or capture an opponent on the destination square when allowed by the shared capture rules.

## Architecture requirements

- **Static web delivery:** deploy only generated site files, including UI assets, engine artifacts, and any client runtime. No server-side game logic, AI inference, database, or application API is required. A local development server or desktop-local helper process is allowed.
- **One engine core:** board state, move generation, move validation, capture rules, terminal detection, evaluation, and search belong to the shared engine. The UI must not implement a second rules engine.
- **One authoritative game session:** each running game has one owner of its position. UI views consume state and legal-action data from that owner; they do not maintain competing authoritative positions.
- **Target adapters:** keep platform-specific runtime startup, engine invocation, filesystem access, audio setup, and packaging at documented boundaries. Prefer shared presentation code; if separate desktop/browser views are necessary, document the reason and test feature parity.
- **Engine interface:** define a language-neutral command/event or call interface for initialization, state snapshots, legal moves, move submission, AI search, cancellation, undo, new game, and errors. Specify serialization, coordinates, side identity, and versioning when crossing runtime or process boundaries.
- **Search lifecycle:** keep UI input and redraw responsive while thinking. Cancel obsolete work on undo, new game, or shutdown, and prevent stale search results from changing a newer position.
- **Source and assets:** write original application-specific game logic for a new project. General-purpose libraries, runtimes, frameworks, build tools, and generated bindings are allowed. When extending an existing project, reuse compatible application code and piece/tile art or sound assets unless a rewrite is requested or replacement is justified. Document third-party dependencies and asset attribution.

## Gameplay and UI requirements

- Provide human-vs-AI and AI-vs-AI watch/demo modes, with Easy / Medium / Hard difficulty levels.
- Use bounded search within the default move-response limits, or the requester's explicit override. Tune search work per target using measurements while retaining the same rules and AI implementation. Optimize Hard for maximum practical playing strength within its limit and keep Easy / Medium meaningfully distinct.
- Let the player choose human first or AI first before a game. Blue always opens; the choice determines who controls Blue.
- Support complete games and correctly announce wins, losses, and draws. Undo behavior must be documented for both play modes and work safely during AI search.
- Show a clear initialization state in the browser, with progress when measurable and an informative status otherwise. Enable play when initialization completes and display actionable load errors.
- Load correctly at both a static-host root and a nested base path. Resolve engine/runtime files and other assets without assuming installation at `/`.
- Produce a polished board with distinct river, trap, den, and land terrain; animal artwork must be recognizable.
- Each piece must display its short English animal name, such as "Rat" or "Lion", readable for both side colors at supported board sizes and moving with the piece during animations.
- Include selection highlights, legal-move and capture indicators, move animations, capture feedback, turn display, move history, a captured-piece list, undo, and end-of-game messaging.
- Include a board-flip option that changes only display and input coordinate mapping. It must not change logical squares, sides, state, or the turn, and must work with either first-player choice.
- Show the application/engine version and relevant runtime information in the main menu.
- Include "How to play" guidance for new players: den-entry and elimination wins, no-legal-move loss, applicable draw rules, selection/movement controls and indicators, rank order, Rat-vs-Elephant exceptions, river movement, lion/tiger jumps and rat blocking, traps, own-den restriction, undo, board flip, and mute. Explain the selected jump profile accurately.
- Provide move, capture, and win sounds with a mute option; handle browser audio permissions or gesture requirements gracefully.
- Render correctly across supported desktop resolutions, window sizes, aspect ratios, and DPI/display scaling settings. Specify a minimum supported size and avoid clipping, overlap, distortion, or unreadable controls.
- Support mouse input on desktop and browser. Tablet/mobile touch layouts with tap-to-select then tap-to-move are a stretch goal after Phase 1 unless separately required.
- Avoid placeholder visuals in the final release, except in an optional debug mode.

## Testing and AI validation

Integrate tests throughout development using tools appropriate to the chosen languages. Fix defects and add relevant regression coverage before declaring the affected feature complete.

- **Engine correctness:** test rules, legal move generation, captures, terminal states, documented draw counters, and make/unmake or equivalent state restoration. Include the explicit jump restrictions and every rat-blocking path.
- **Reference positions:** maintain reviewed fixtures with expected legal moves and outcomes, fixed move-tree counts (perft), and a reproducible golden corpus covering thousands of positions. Freeze only checked expectations; generating expected results from the engine under test alone does not establish correctness.
- **Cross-target parity:** run the same fixtures through the actual desktop and browser engine artifacts. Compare legal moves, resulting state, terminal status, and winner. Use fixed seeds, deterministic budgets, and defined tie-breaking where exact search-output comparisons are needed.
- **Evaluation and strength:** test symmetry where the evaluation design calls for it. Use repeatable baseline-versus-candidate matches for material search/evaluation changes, with a parameter switch or reproducible version comparison. Record passes and failures in this file's implementation record, including match conditions and uncertainty. Sequential statistical tests or fixed-game matches are acceptable.
- **Benchmark interpretation:** node-limited runs help reproduce behavior; timed runs measure responsiveness and speed benefits. Strength acceptance must include matches at equal per-move wall-clock limits, with balanced sides and matched starting positions, on each target. Do not treat nodes/sec or search depth alone as proof of greater playing strength, especially across different algorithms.
- **Response-time validation:** test the actual desktop and browser builds on the documented hardware across opening, middlegame, tactical, and endgame positions, including expensive searches. Record median, 95th-percentile, and maximum observed move-response times and any deadline overruns for each difficulty. Verify UI responsiveness and legal fallback behavior when time runs out. Fix overruns before accepting the candidate; faster averages do not excuse missed limits.
- **UI and integration:** test coordinate mapping in both orientations, first-player selection, undo, lifecycle cancellation, stale-result handling, and the engine interface or message protocol.
- **Browser smoke and benchmark:** load the real release engine/runtime through a static server, execute legal moves and search, and record timing. Test both root and nested deployment paths.
- **Desktop smoke:** provide an automated headless engine/game mode or equivalent harness and exercise the packaged application. Add GUI integration checks supported by the selected framework.
- **Browser end-to-end:** use a suitable browser automation tool to load the production bundle, wait for initialization, play a deterministic sequence, and assert valid progression. Include full-game completion and terminal-state coverage across the test suite.
- **Full games:** verify complete games in both targets, including human interaction and automated AI-vs-AI play; bounded automated matches must use the documented adjudication rules.
- **CI:** automate engine tests and appropriate lint/static checks, desktop build/smoke for selected operating systems, and browser build, UI tests, engine smoke, parity checks, and end-to-end tests. Record any platform or GUI checks that require a separate environment.

Report the commands, environments, and results actually observed. Label unavailable hardware/browser checks, unrun tests, unmeasured strength claims, and deployment limitations explicitly. Do not mark a release criterion complete based only on a plan or an unavailable tool.

## Desktop release

- Produce launchable packages for each selected desktop target in a documented release folder. Examples include a Windows `.exe` with required bundled files or an installer, a macOS application bundle, or a Linux package/portable bundle; use the format appropriate to the selected stack and OS.
- Include all required application assets and runtime components, or supply a documented installer that installs prerequisites. Ordinary play must work offline after installation and must not depend on the developer's source checkout or development tools.
- Include a copy of this file with the release, with completed installation/launch instructions, gameplay, controls, supported platforms, and known limitations in its implementation record. Present player guidance in the application's help interface as well.
- Test the packaged artifacts after packaging, including automated smoke checks and GUI launches across a recorded window-size and DPI/display-scaling matrix. If packaging defects occur, fix, rebuild, and retest.

## Browser release and deployment

- Produce a self-contained static-site output directory containing the UI, shared engine build, client runtime if required, and assets. Only this output directory is deployed.
- Deploy to Cloudflare Pages free tier by default: no Pages Functions, server-side compute, or paid features. Verify current free-tier limits against the build's file size, content-type, caching, and response-header requirements. If the runtime needs special browser isolation headers or capabilities, verify that Pages and the supported browsers provide them.
- Name the Pages project `{model_base_name}-jungle` and target `https://{model_base_name}-jungle.pages.dev`. Document this derivation and the resulting URL in this file's implementation record; do not introduce a second site-name setting or use the repository name in place of the derived name.
- Verify that the actual production subdomain matches the derived URL. If the name is unavailable or Cloudflare assigns a suffix because of a collision, report the conflict and request a different `model_base_name`; do not silently change the naming scheme. Cloudflare describes this behavior in its [Pages Direct Upload documentation](https://developers.cloudflare.com/pages/get-started/direct-upload/).
- Document exact commands for prerequisite setup, desktop development, a local web server, the production build including engine/runtime preparation, tests, packaging, and Pages deployment. Use Pages Git integration or a supported Pages CLI/API workflow with the derived project name. State the shell and operating system for platform-specific commands.
- Public deployment is required by default. Publish using available authorized account access. After each deployment, load the production URL in a supported browser, verify engine/assets and a gameplay segment, and complete a full deployed game before final release acceptance.
- If deployment access is unavailable, finish and validate the local deliverables, provide the exact deployment steps, and report public deployment and verification as outstanding.
- Only if the requester explicitly asks for local-only browser delivery, validate the production bundle using a local static server and document how to publish it; a live URL is not required for that explicitly reduced scope.

## Plan, documentation, and handoff

Provide a concise plan before implementation, covering:

- The selected stack and feasibility rationale, including how a preferred language reaches both runtimes and which measurements are available or still planned.
- The shared engine, presentation code, target adapters, authoritative session owner, and engine interface.
- The rules profile, board representation, search/evaluation approach, response-time limits and deadline enforcement, and a measured optimization plan for maximizing playing strength within those limits.
- A phased roadmap: feasibility and rules decisions; playable and tested desktop; desktop packaging validation; browser integration and parity; static-site validation and Cloudflare Pages deployment under the defaults.
- Tests and acceptance gates for each phase, including bug fixes, regression coverage, full-game checks, and the display-scaling matrix.
- Reproducible build/run/test/package/deploy workflows and the expected repository and release-folder contents.

Maintain the implementation record in this file with desktop and local-browser setup, production build commands, packaging and deployment instructions, the model-base-name derivation and verified live demo URL, supported environments, gameplay and controls, architecture, and known limitations. Mark an undeployed URL as expected rather than live.

Keep this single specification and its implementation record in the repository as `prompt_template.md`, and report its path. Generate the required application source, tests and fixtures, dependency manifests/lockfiles, automation, packages, and raw measurement outputs during implementation. Summarize the selected rule decisions, strength measurements, reproducible commands, and validation results directly in this file so its meaning never depends on a companion requirements document.

Only if the requester explicitly asks for `plan-only`, deliver the plan, proposed workflows and repository contents, and explicit feasibility questions or measurements still required; do not claim that builds, tests, packages, or deployment have been completed.

By default, continue through implementation and verification in `plan-and-build` mode. The final handoff must identify the delivered files/packages, actual commands and checks run, benchmark evidence, verified production URL, and any remaining limitations.

## Completion criteria

For the default `plan-and-build` workflow, completion requires all of the following, except where the requester explicitly overrides a default:

- A stable, playable desktop package for every selected desktop target, tested after packaging and usable offline after installation.
- A stable browser build for the selected browsers, served as static files with client-side rules and AI.
- One maintained rules/AI implementation used by both targets, with passing cross-target parity tests and required gameplay/UI features.
- Complete games, correct terminal outcomes, responsive AI, and passing required automated tests in both targets.
- A completed, documented strength-optimization pass with baseline comparisons at equal time limits, selection of the strongest candidate supported by the evidence that meets all requirements, and passing response-time checks for every difficulty in both targets.
- Release validation at documented desktop window sizes and display scaling settings, plus browser initialization and root/nested-path asset loading checks.
- This file retained in the repository and included with the release, containing the rules, implementation decisions, player/setup instructions, reproducible workflows, strength summaries, and recorded validation results.
- A verified public Cloudflare Pages site at `https://{model_base_name}-jungle.pages.dev` and a full deployed-game check. A local static-server check replaces this criterion only when the requester explicitly asks for local-only browser delivery.

Any unmet required criterion remains outstanding and must be named explicitly.

## Implementation record

This section records the current project's implementation, not additional configuration or restrictions on a future implementation. When copying this template to a new project, replace these historical entries with that project's choices and fresh evidence. The requester still changes only `model_base_name`; previous validation never establishes that another build passes.

### Decisions and architecture

Rebuild date: 2026-09-04/05. The requester explicitly authorized a whole-program rewrite without preserving the previous language or architecture, and retained Save/Load, Redo, and valid legacy-save compatibility. The former Python application is preserved under `benchmarks/legacy/` solely as a reference and benchmark opponent. It is not bundled or required for normal play.

- Rules references: the linked Wikipedia article and AncientChess booklet, accessed 2026-09-04. The explicit rules above take precedence, particularly the Tiger's east-west-only jump and Rat/Elephant/trap exceptions. Board setup remains supplied by the references rather than duplicated here.
- Draw policy: exactly **100 consecutive non-capturing plies**, reset on capture; den entry, elimination, and no-move wins take precedence. **No separate repetition draw.** Rules identifier: `jungle-tiger-ew-quiet100-v1`.
- Engine: original Rust implementation, compiled natively for Windows and from the same source to WebAssembly. A 63-square signed-rank board, incremental deterministic Zobrist hash, and reversible moves support the search. The quiet counter participates in transposition keys.
- Stack: Rust 1.94.1; Tauri 2.11; React 19.2.8; TypeScript 5.9.3; Vite 8.2.2; wasm-pack 0.15.0. Exact resolved dependencies are in Cargo/npm lockfiles. Tests use Vitest 5.0.0, Playwright 1.63.0, and tauri-driver 2.0.6. Pages deployment uses Wrangler 4.129.0.
- Rationale: Rust supplies a shared native/WASM core and bounded background search. C++/WASM and an all-browser-language engine were feasible alternatives; an interpreted browser runtime adds payload/startup work. No complete competing-language engines were built, and these measurements do not establish a general language ranking.
- Session ownership: Rust `Game` owns the position, history, cursor, outcome and revision. Desktop keeps it behind a native mutex; the browser owns one WASM session. Search works on immutable snapshots in native background tasks or a Web Worker. Revision/job identifiers and cancellation prevent old results from altering a newer game.
- Shared UI: React, semantic board buttons, CSS terrain and animations. Accessible DOM controls replace the initially proposed SVG board. There is no second UI rules engine: terrain, legal destinations, captured pieces, move history and outcomes come from Rust. Platform adapters handle native dialogs, browser downloads, runtime initialization, and search transport.
- Assets: the previous project's 16 compatible animal PNGs were retained in `web/public/animals`; terrain/layout use CSS. Audio is generated locally with Web Audio oscillators. No external font, image, audio, model, or inference service is used. Original application code is MIT-licensed; dependencies retain their own licenses.

The version-1 interface uses JSON. A square is `row * 7 + column`, in the logical unflipped coordinates defined above. Sides serialize as `blue`/`red`; positive board entries are Blue, negative entries Red, zero is empty, and magnitudes 1–8 are Rat through Elephant. Session commands are `snapshot`, `new`, `move`, `undo`, `redo`, `settings`, `import`, and `export`. Move submission includes `from`, `to`, and the observed `revision`. Snapshots include `protocol_version`, `rules_id`, version, revision, board, side, quiet counter, legal moves, outcome/winner/message, history/cursor, captured pieces, terrain and controls state. Search accepts a snapshot and difficulty/time options and emits tagged progress plus a final legal move and statistics; cancellation invalidates the job. Malformed inputs, illegal moves, obsolete revisions and incompatible saves return errors without replacing the session.

Portable saves contain `format_version: 1`, rules identifier, initial position, validated move sequence, cursor and settings. Import replays every move and verifies capture/jump metadata atomically. Valid original-format saves are reverse-checked and replayed to reconstruct history and the no-capture count. Corrupt histories, unsupported rules versions, files larger than 4 MiB, and legacy histories continuing beyond this profile's terminal result are rejected; the input file is never modified. Saves preserve Redo history. In human mode Undo/Redo returns to or restores the previous human decision (normally two plies); in watch mode it steps one ply and pauses.

### Player guide and supported environment

The installer is `release/v1/Jungle-Setup.exe`; it installs per-user and includes the offline Microsoft WebView2 installer. Start Jungle from its installed shortcut. The smaller `release/v1/Jungle.exe` is also launchable when a compatible WebView2 runtime is already installed. Neither needs Rust, Node, Python, the source checkout, an application server, an account, or internet access for ordinary desktop play. Executables are not code-signed, so Windows may show an unknown-publisher warning. Only run packages from a source you trust.

Select an animal, then an engine-highlighted destination. Dots mean empty destinations; outlined opponents are capturable. Blue always opens. New game selects human-first or AI-first and Human vs AI or watch mode. Easy/Medium/Hard have 100/500/2,000 ms response limits. Flip changes only the view. Undo and New game cancel thinking; Redo restores undone play. Save/Load transfers games between desktop and browser. The note button controls sound; browser sound begins after a user gesture. Full rules, ranks, selected jumps, draws and controls are in How to play.

Supported release target: Windows x64 with WebView2, and current Chrome/Firefox on desktop. Validated side-by-side layout sizes are **800×600, 1180×800, and 1600×1000 logical client pixels**. Narrower/smaller views may require vertical scrolling; mobile/touch polish is a stretch goal, not claimed complete. Desktop rendering was exercised at 100%, 125%, 150%, and 200% WebView2 rasterization scales with matching physical window sizes. These tests change only the app's WebView2 scale, not Windows display settings. Normal startup also passed at the machine's actual 300% system scaling: the app fits and centers its own window within the monitor work area, accounting for borders and the taskbar. Tested native outer bounds were 3576×1968 physical pixels at (260, 36), inside a 4096×2040 work area. Changing monitor DPI, multi-monitor transitions, Windows on ARM, macOS and Linux have not been validated.

Timing conditions are an initialized, visible foreground app on the test-class hardware without OS suspension, background-tab throttling, or unbounded contention. Search runs off the UI thread and retains a legal fallback. It receives the total response allowance minus transport/scheduling reserve (normally 35 ms); an independent UI deadline returns the latest legal result. Move response includes bridge/worker delivery and committing the move for rendering. Initialization, the 180 ms piece animation, and the 230 ms watch-mode viewing beat are separate. These are observed limits, not a hard-real-time operating-system guarantee.

Local release validation targets are under 5 seconds to engine readiness, under 5 MiB of uncompressed static assets, and under 100 ms from an input event to UI-frame feedback while Hard is thinking. Network download time is reported separately from local initialization. The installer includes the offline WebView2 prerequisite, but a clean-machine installation without a pre-existing WebView2 runtime has not been exercised on a separate VM.

### Reproducible build, test and release workflow

Use Windows PowerShell from the repository root. Install Node 24.13.0 or compatible newer Node 24, Rustup, and Visual Studio 2022 Build Tools with Desktop development with C++ and Windows SDK. Python 3.10+ is needed only for the archived-opponent/reference comparisons. Normal play has none of these development prerequisites.

```powershell
npm ci
rustup toolchain install 1.94.1 --profile minimal --component rustfmt --component clippy
rustup target add wasm32-unknown-unknown --toolchain 1.94.1
cargo install wasm-pack --version 0.15.0 --locked
cargo install tauri-driver --version 2.0.6 --locked
npx playwright install chrome firefox
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-edge-driver.ps1
```

Driver setup detects WebView2 and downloads the matching Microsoft driver into generated artifacts. No driver path is a user configuration requirement. Development:

```powershell
npm run dev:desktop
# Or, in a separate terminal, use the local browser app:
npm run dev
```

The local web development URL defaults to `http://127.0.0.1:1420`. Build and verify:

```powershell
npm test
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo build -p jungle-engine --release --bins
cargo run -p jungle-engine --release --bin jungle-tablebase -- engine/data/two_piece.bin --check
node scripts/release.mjs package
node scripts/release.mjs desktop
npm run test:browser
node scripts/parity.mjs chrome
node scripts/parity.mjs firefox
node scripts/reference-check.mjs
node scripts/timing.mjs
```

`package` builds WASM/UI, native Tauri, offline-runtime NSIS, and stages `release/v1/`. `desktop` runs packaged headless smoke, silently installs into `artifacts/install-test`, verifies installed bytes against the staged application (allowing only Tauri's `UNK`→`NSS` bundle-type marker), then exercises the actual installed GUI offline. Tests use app-scoped native dialogs, normal board/button interactions and screenshots without changing system display settings. GUI driver sessions are serialized.

`npm run build` alone generates static `dist/web`, including WASM preparation. `npm run preview` serves it at `http://127.0.0.1:4173`; automated parity/timing/smoke scripts create and stop their own ephemeral static server. Browser tests also mount the same output under `/nested/`. Engine/UI changes must repeat appropriate installed-desktop checks before web release.

Strength comparisons are resumable fixed 64-game matches. Each may take hours on this workstation; completed games are reused only when engine/build/budget/opponent identifiers match. Run all four:

```powershell
node scripts/bench.mjs --target=native --opponent=baseline --games=64 --ms=1950 --label=final-native-baseline
node scripts/bench.mjs --target=native --opponent=legacy --games=64 --ms=1950 --label=final-native-legacy
node scripts/bench.mjs --target=chrome --opponent=baseline --games=64 --ms=1950 --label=final-chrome-baseline
node scripts/bench.mjs --target=chrome --opponent=legacy --games=64 --ms=1950 --label=final-chrome-legacy
```

Do not substitute shortened screening runs for these comparisons. `npm run release:verify` rebuilds and runs automated desktop-first checks, then requires matching completed strength results; it does not skip missing evidence. For an already-tested package, `node scripts/release.mjs record` collects matching reports without rebuilding. Gates verify executable/WASM/web/core hashes to reject stale evidence. CI automates engine/static checks, package and installed desktop smoke/GUI, browser tests, parity, the independent rules corpus, tablebase reproduction, and artifact retention. Timed strength matches remain a separate workstation release gate. The workflow is provided but no hosted CI execution is claimed.

Deployment parses the one model label directly from this file and derives project/URL without a second site setting:

```powershell
npx wrangler login
npm run deploy:web
```

`deploy:web` refuses stale/incomplete validation. It uses authorized Wrangler credentials, creates the derived project if necessary, checks the assigned subdomain, uploads only `dist/web` to a preview, verifies deployed engine bytes and gameplay, then promotes to production and verifies Chrome/Firefox gameplay and full games. Local/deployed reports stay separate. On production validation failure it attempts to restore the captured previous successful deployment, but never overwrites a concurrent independent deployment. Credentials never enter source, site assets, command arguments, or reports.

After updating this record following successful deployment, run `node scripts/release.mjs handoff` to copy the specification and matching validation/match evidence into `release/v1/` and generate a SHA-256 manifest. This operation refuses an unverified deployment. Deployment evidence excludes Cloudflare environment-variable values and unrelated account data.

### Strength, timing and artifact evidence

Workstation: Windows 10 Pro 10.0.19045, AMD Ryzen 5 PRO 2400G (4 cores/8 threads), approximately 16 GiB RAM. Runtimes: native Rust release with optimization level 3, thin LTO and one codegen unit; WebView2 152.0.4191.62; Chrome 152.0.7977.77; Playwright’s Firefox 155.0 build; Node 24.13.0; Python 3.12.9 for the archived opponent. Shared engine source identifier: `f18c3560d17c77ae4375af636b418e605958ecf3762182bef14f8adb6732f676`.

Baseline: iterative deepening alpha-beta/PVS, transposition table, capture ordering and basic material/progress evaluation. Candidate adds aspiration windows, killer/history ordering, verified late-move reduction re-search, bounded quiescence with den-threat defense, contextual den/trap/river/Rat-Elephant evaluation and an exact two-animal WDL/DTM tablebase. Easy caps depth at 3; Medium at 8; Hard at 64 with the wall deadline. The tablebase is regenerated from this rules core: 508,032 encoded slots, 1,524,124 bytes, checked FNV checksum `bb9f9aed0862ad80`. Finite-clock probes were compared with brute-force solutions. This is a practical optimization pass, not a claim of globally optimal Jungle play.

Matches use 32 seeded openings with colors swapped, 8–12 randomized opening plies, xorshift32 seed `opening_index + 1729`, equal 1,950 ms search allowances inside Hard's 2,000 ms limit, and only rules-profile outcomes for adjudication. Native baseline/candidate both run natively; Chrome baseline/candidate both run the actual WASM artifact. The legacy opponent runs archived Python Hard natively with supplied move history; this is not a measurement of the old Python-in-browser runtime. Matches used the same workstation and some overlapped other verification jobs, so these are engineering comparisons rather than isolated laboratory ratings. Raw games and paired bootstrap/Hoeffding 95% score intervals are in `artifacts/strength/`.

- Full native vs baseline: **38 wins / 24 draws / 2 losses**, 78.125% score over 64 games. Paired bootstrap 95% score interval: 71.875–84.375%; conservative paired Hoeffding interval: 54.117–100%. Improvement is supported on these openings and conditions.
- Full Chrome vs baseline: **32 wins / 31 draws / 1 loss**, 74.219% score over 64 games. Paired bootstrap 95% score interval: 67.188–81.250%; conservative paired Hoeffding interval: 50.211–98.227%. Improvement is supported on these openings and conditions.
- Full Chrome vs legacy: **53 wins / 8 draws / 3 losses**, 89.063% score over 64 games. Paired bootstrap 95% score interval: 82.813–94.531%; conservative paired Hoeffding interval: 65.054–100%. Improvement is supported on these openings and conditions.
- Full native vs legacy: **51 wins / 9 draws / 4 losses**, 86.719% score over 64 games. Paired bootstrap 95% score interval: 78.906–93.750%; conservative paired Hoeffding interval: 62.711–100%. Improvement is supported on these openings and conditions.
- Preliminary native screening at 80 ms: 8/7/1 vs baseline over 16 games; 16/0/0 vs legacy over 16 games. These are screening evidence only. An early bootstrap RNG defect was fixed; the old baseline screening interval is not used. Ablation switches (`no_lmr`, `no_quiescence`, `no_tablebase`) exist, but separate full ablation matches have not been performed. No finite Elo claim is inferred from an undefeated small sample.

Observed end-to-end response, 10 fixed positions per difficulty/target (opening/middlegame corpus samples, blocked-river tactics and a two-animal endgame):

| Target | Difficulty / limit | Median ms | 95th percentile ms | Maximum ms | Overruns |
|---|---|---:|---:|---:|---:|
| Installed Windows | Easy / 100 ms | 23.9 | 66.1 | 66.1 | 0 |
| Installed Windows | Medium / 500 ms | 86.5 | 263.8 | 263.8 | 0 |
| Installed Windows | Hard / 2,000 ms | 1,977.9 | 1,988.3 | 1,988.3 | 0 |
| Chrome | Easy / 100 ms | 20.3 | 70.2 | 70.2 | 0 |
| Chrome | Medium / 500 ms | 86.8 | 309.4 | 309.4 | 0 |
| Chrome | Hard / 2,000 ms | 1,970.4 | 1,973.9 | 1,973.9 | 0 |
| Firefox | Easy / 100 ms | 21.5 | 38.0 | 38.0 | 0 |
| Firefox | Medium / 500 ms | 112.5 | 383.0 | 383.0 | 0 |
| Firefox | Hard / 2,000 ms | 1,975.5 | 1,982.0 | 1,982.0 | 0 |

The nearest-rank 95th percentile equals the maximum for ten samples; the median averages the two middle observations. These are finite measurements, not population guarantees. Each sample retains the adapter clock and an independent ready-snapshot-to-committed-reply UI observation; the reported response is the larger value, including UI scheduling and bridge/worker delivery but excluding animation completion. Raw response/depth/node samples and build identifiers are in `artifacts/timing-*.json`. For the eight non-endgame Hard corpus samples, Installed Windows completed depths 10–12 at approximately 0.869–1.025 million reported nodes per end-to-end second; Chrome completed depths 10–12 at approximately 0.722–0.866 million reported nodes per end-to-end second; Firefox completed depths 10–11 at approximately 0.615–0.744 million reported nodes per end-to-end second. The two-animal case returns an exact table lookup rather than searching nodes. Rates include response/bridge overhead and are not isolated raw engine throughput. An earlier isolated native opening search completed depth 11 and approximately 2.736 million nodes in 1,900 ms. None of these throughput figures is proof of playing strength.

The final timing pass measured local launch/readiness at 1.57 seconds Installed Windows, 0.63 seconds Chrome, 1.03 seconds Firefox. Installed GUI launches in the final scale matrix ranged from 1.34–1.77 seconds. Browser download latency depends on the connection and is separate from the local-server startup target.

Current staged payload: 26 static files totaling 1,792,032 bytes (uncompressed on disk); Windows application 6,496,768 bytes; offline-runtime installer 263,812,243 bytes. The installer is not uploaded to Pages. Static output is below verified free-tier limits of 20,000 files and 25 MiB per asset. Pages serves only static files with local WASM, relative URLs, CSP, WASM MIME type and revalidation of non-fingerprinted engine files. Neither cross-origin isolation nor SharedArrayBuffer is required. [Pages limits](https://developers.cloudflare.com/pages/platform/limits/) and [static headers](https://developers.cloudflare.com/pages/configuration/headers/) were checked 2026-09-04/05.

### Validation status and remaining work

Completed: 19 Rust rules/session/search/invariant/tablebase tests, including every river lane/direction/blocking color; 5 coordinate/revision-ordering tests; 7 release-safety/statistics tests; formatting and warning-free static analysis; reproducible tablebase; packaged 43-ply den-win smoke; offline installed native Save/Load, Undo/Redo, Flip, Hard cancellation and first-player/flip matrix; three-size/four-scale installed rendering checks; a complete installed 100-ply watch draw and 28-ply human-vs-AI den result; all 30 Chrome/Firefox end-to-end tests including full watch and human games; and all 90 response samples above. Screenshots of supported layouts were inspected for readability and clipping. Input-to-frame feedback during Hard was 15.8–31.9 ms in the desktop scale matrix, 10.1 ms in Chrome and 46 ms in Firefox, below the 100 ms feedback threshold. Sixteen simultaneous native search/reset protocol cases also passed, along with oversized-file recovery and browser-storage-denial tests.

The 10,000-position corpus and **9,937 move transitions** passed against the pre-rewrite independent Python rules oracle (with the explicit new quiet-100 adjudication) and the actual WASM engine in both browsers. Corpus seed: 42; SHA-256: `ab30686616d767a38924e196715642b8afe6f1ba33959b5854ad59c2a90288d7`. Initial perft counts at depths 1–3 are 24, 576 and 12,240, independently checked with the original move generator. This is not merely a comparison of self-generated expected data with itself.

Regressions fixed included native packaged-asset protocol selection, Save/Load pause-state handling, job-specific cancellation, native bridge overhead, atomic search registration, unique client search IDs, delayed-reply ordering, oversized-load recovery, privacy-safe mute settings, default work-area fitting, compact-window board fitting, matching WebView2 driver setup, native file-dialog test acceptance, installed bundle-marker verification and stale-report detection. Build-space pressure was resolved with lossless cache compression; the prior implementation remains recoverable.

All four fixed 64-game strength comparisons are complete: **256 games total**, with the candidate ahead in every comparison and each conservative paired confidence bound above equal score. The candidate is the selected validated engine under the recorded conditions. The baseline, rather than the candidate, is retained only as a benchmark switch; separate ablation experiments remain future work, not claimed evidence.

### Verified deployment and final handoff

**Live production: [gpt-jungle.pages.dev](https://gpt-jungle.pages.dev)**, derived from the sole supplied model label. The rebuilt application was deployed only after the installed desktop checks, browser/parity checks, response-time checks, and all 256 strength games passed. Production deployment identifier: `23799d73-3bad-49fe-8742-41a8a9deef2a`, completed and verified on 2026-09-05 (verification finished at 09:59:25 UTC). The validated preview is [aa68c4db.gpt-jungle.pages.dev](https://aa68c4db.gpt-jungle.pages.dev).

Preview and production both passed Chrome/Firefox initialization, legal gameplay, Undo/Redo, Flip, Help and Save/Load checks with zero recorded browser errors. Production also completed a 100-ply no-capture draw in Chrome and a 121-ply den-entry game in Firefox. Observed production startup was 654 ms in Chrome and 1,198 ms in Firefox. Deployed HTML and engine artifacts matched the tested build hashes; WASM MIME type and CSP were verified. Deployment uploaded only the static output (25 assets plus the header configuration), with no Pages Functions or paid runtime features. Rollback was not needed.

The release folder contains the tested Windows executable, offline-runtime installer, this self-contained specification, license, copied validation/strength evidence, and a SHA-256 manifest. Required release gates for the stated Windows x64 and Chrome/Firefox targets have passed. The unvalidated environments, unsigned-package warning and optional future experiments listed above remain limitations; no additional platform coverage or globally optimal playing strength is claimed.
