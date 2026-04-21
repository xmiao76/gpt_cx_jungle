from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def release_executable_path(release_dir: Path) -> Path:
    return release_dir / "Jungle.exe"


def smoke_result_path(release_dir: Path) -> Path:
    return release_dir / "release_smoke_result.txt"


def run_packaged_smoke(release_dir: Path) -> Path:
    release_exe = release_executable_path(release_dir)
    if not release_exe.exists():
        raise SystemExit(f"{release_exe} not found. Build the release first.")
    subprocess.run([str(release_exe), "--smoke-test"], cwd=release_dir, check=True)
    result_file = smoke_result_path(release_dir)
    if not result_file.exists():
        raise SystemExit("Smoke test did not create release_smoke_result.txt")
    return result_file


def main() -> None:
    result_file = run_packaged_smoke(ROOT / "release")
    print(result_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
