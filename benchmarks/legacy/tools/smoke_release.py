from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALID_RESULTS = {"ongoing", "den_entry", "capture_all", "no_legal_moves"}


def release_executable_path(release_dir: Path) -> Path:
    return release_dir / "Jungle.exe"


def smoke_result_path(release_dir: Path) -> Path:
    return release_dir / "release_smoke_result.txt"


def parse_smoke_result(content: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in content.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def validate_smoke_result(result_file: Path) -> None:
    values = parse_smoke_result(result_file.read_text(encoding="utf-8"))
    if values.get("result") not in VALID_RESULTS:
        raise SystemExit(f"Smoke test wrote invalid result: {values.get('result')!r}")
    try:
        turns = int(values.get("turns", ""))
    except ValueError as exc:
        raise SystemExit("Smoke test did not write a numeric turns value") from exc
    if turns <= 0:
        raise SystemExit("Smoke test did not play any turns")
    if values.get("hard_legal") != "true":
        raise SystemExit("Packaged Hard engine did not return a legal move")
    if values.get("tablebase_legal") != "true":
        raise SystemExit("Packaged tablebase did not return a legal move")
    if values.get("trap_capture_legal") != "true":
        raise SystemExit("Packaged rules rejected an elephant capturing a rat in its own trap")
    try:
        tablebase_hits = int(values.get("tablebase_hits", ""))
    except ValueError as exc:
        raise SystemExit("Packaged smoke did not write numeric tablebase hits") from exc
    if tablebase_hits <= 0:
        raise SystemExit("Packaged Hard engine did not probe the bundled tablebase")


def run_packaged_smoke(release_dir: Path) -> Path:
    release_exe = release_executable_path(release_dir)
    if not release_exe.exists():
        raise SystemExit(f"{release_exe} not found. Build the release first.")
    subprocess.run([str(release_exe), "--smoke-test"], cwd=release_dir, check=True)
    result_file = smoke_result_path(release_dir)
    if not result_file.exists():
        raise SystemExit("Smoke test did not create release_smoke_result.txt")
    validate_smoke_result(result_file)
    return result_file


def main() -> None:
    result_file = run_packaged_smoke(ROOT / "release")
    print(result_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
