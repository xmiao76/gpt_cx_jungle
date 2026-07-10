from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from tools.smoke_release import run_packaged_smoke


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build"
RELEASE = ROOT / "release"
SPEC = ROOT / "Jungle.spec"
RELEASE_ZIP_NAME = "Jungle.zip"
MODEL_NAME = "gpt-5.5"
AGENT_NAME = "Codex"
REQUIRED_DISCLOSURES = (
    f"Model used: {MODEL_NAME}",
    f"Code agent used: {AGENT_NAME}",
)
PRESERVED_RELEASE_NAMES = frozenset({"Capture.PNG", "knownIssue.txt"})
SPEC_TEMPLATE = """
a = Analysis(
    ['src/jungle/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[('src/jungle/ui/assets', 'jungle/ui/assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Jungle',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Jungle',
)
""".strip()


def build_release_readme(model_name: str = MODEL_NAME, agent_name: str = AGENT_NAME) -> str:
    return f"""Jungle

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
- Model used: {model_name}
- Code agent used: {agent_name}
"""


def write_spec(spec_path: Path = SPEC) -> None:
    spec_path.write_text(SPEC_TEMPLATE, encoding="utf-8")


def clean(paths: tuple[Path, ...] = (DIST, BUILD, RELEASE)) -> None:
    for path in paths:
        if not path.exists():
            continue
        if path.name.casefold() != "release":
            shutil.rmtree(path)
            continue
        for child in path.iterdir():
            if child.name in PRESERVED_RELEASE_NAMES:
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()


def generate_assets() -> None:
    subprocess.run([sys.executable, "-m", "tools.generate_ui_assets"], cwd=ROOT, check=True)


def build_bundle(spec_path: Path = SPEC) -> Path:
    write_spec(spec_path)
    subprocess.run([sys.executable, "-m", "PyInstaller", str(spec_path)], cwd=ROOT, check=True)
    return DIST / "Jungle"


def assemble_release(bundle_dir: Path, release_dir: Path = RELEASE) -> None:
    shutil.copytree(bundle_dir, release_dir, dirs_exist_ok=True)


def write_release_readme(release_dir: Path = RELEASE) -> Path:
    readme_path = release_dir / "README.txt"
    readme_path.write_text(build_release_readme(), encoding="utf-8")
    return readme_path


def create_release_zip(release_dir: Path = RELEASE) -> Path:
    zip_path = release_dir / RELEASE_ZIP_NAME
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(release_dir.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path == zip_path or file_path.name == "release_smoke_result.txt":
                continue
            archive.write(file_path, arcname=file_path.relative_to(release_dir))
    return zip_path


def verify_release_artifacts(release_dir: Path = RELEASE) -> None:
    readme_path = release_dir / "README.txt"
    readme = readme_path.read_text(encoding="utf-8")
    for required in REQUIRED_DISCLOSURES:
        if required not in readme:
            raise RuntimeError(f"Missing release README requirement: {required}")
    if not (release_dir / "Jungle.exe").exists():
        raise RuntimeError("release/Jungle.exe was not created")
    zip_path = release_dir / RELEASE_ZIP_NAME
    if not zip_path.exists():
        raise RuntimeError(f"release/{RELEASE_ZIP_NAME} was not created")
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    for required_name in ("Jungle.exe", "README.txt", "_internal/python312.dll", "_internal/VCRUNTIME140.dll"):
        if required_name not in names:
            raise RuntimeError(f"release/{RELEASE_ZIP_NAME} is missing {required_name}")
    if not (ROOT / "prompt.md").exists():
        raise RuntimeError("prompt.md must remain in the repository root")


def main() -> None:
    clean()
    generate_assets()
    built = build_bundle()
    assemble_release(built)
    write_release_readme()
    result_file = run_packaged_smoke(RELEASE)
    create_release_zip()
    verify_release_artifacts()
    print(result_file.read_text(encoding="utf-8"))
    print(f"Release created at {RELEASE}")


if __name__ == "__main__":
    main()
