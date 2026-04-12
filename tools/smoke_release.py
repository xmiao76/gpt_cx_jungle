from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_EXE = ROOT / "release" / "Jungle.exe"


def main() -> None:
    if not RELEASE_EXE.exists():
        raise SystemExit("release/Jungle.exe not found. Build the release first.")
    subprocess.run([str(RELEASE_EXE), "--smoke-test"], cwd=ROOT / "release", check=True)
    result_file = ROOT / "release" / "release_smoke_result.txt"
    if not result_file.exists():
        raise SystemExit("Smoke test did not create release_smoke_result.txt")
    print(result_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
