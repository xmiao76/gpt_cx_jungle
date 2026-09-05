# Jungle

A Windows desktop and static-browser Jungle / Dou Shou Qi game. One Rust rules/search engine runs natively in Tauri and as WebAssembly in the browser, with a shared React interface. All gameplay and AI run on the player's device.

[Play online](https://gpt-jungle.pages.dev) · [Windows installer](release/v1/Jungle-Setup.exe)

The self-contained requirements, implementation record, player guide, and complete build/test/release instructions are in [prompt_template.md](prompt_template.md). Change only its `model_base_name` when choosing a deployment name.

```powershell
npm ci
npm run dev:desktop
# Or run the local browser version:
npm run dev
```

See the specification for the pinned Rust, WebAssembly, and Windows build prerequisites. Run `npm test` for engine, coordinate, and release-safety tests. `npm run release:verify` performs the desktop-first release checks; `npm run deploy:web` refuses deployment without matching validation and strength evidence.

New Windows packages are staged in `release/v1/`. The pre-rewrite Python application and its original files are preserved in `benchmarks/legacy/` for regression comparisons; they are not part of the shipped application.
