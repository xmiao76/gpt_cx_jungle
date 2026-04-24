from __future__ import annotations

import zipfile

import pytest

from conftest import load_tool_module

package_release = load_tool_module("package_release")
smoke_release = load_tool_module("smoke_release")


def test_build_release_readme_includes_required_model_and_agent_statements() -> None:
    content = package_release.build_release_readme()
    assert "Model used: gpt-5.5" in content
    assert "Code agent used: Codex" in content


def test_write_release_readme_creates_expected_file(tmp_path) -> None:
    readme_path = package_release.write_release_readme(tmp_path)
    assert readme_path == tmp_path / "README.txt"
    content = readme_path.read_text(encoding="utf-8")
    assert "Launch" in content
    assert "Extract the full Jungle.zip archive" in content


def test_create_release_zip_packages_full_runtime_payload(tmp_path) -> None:
    release_dir = tmp_path / "release"
    internal_dir = release_dir / "_internal"
    internal_dir.mkdir(parents=True)
    (release_dir / "Jungle.exe").write_text("binary", encoding="utf-8")
    (release_dir / "README.txt").write_text("notes", encoding="utf-8")
    (internal_dir / "python312.dll").write_text("dll", encoding="utf-8")
    (internal_dir / "VCRUNTIME140.dll").write_text("runtime", encoding="utf-8")
    (release_dir / "release_smoke_result.txt").write_text("winner=blue", encoding="utf-8")

    zip_path = package_release.create_release_zip(release_dir)

    assert zip_path == release_dir / package_release.RELEASE_ZIP_NAME
    with zipfile.ZipFile(zip_path) as archive:
        assert sorted(archive.namelist()) == [
            "Jungle.exe",
            "README.txt",
            "_internal/VCRUNTIME140.dll",
            "_internal/python312.dll",
        ]


def test_write_spec_uses_static_local_package_resolution(tmp_path) -> None:
    spec_path = tmp_path / "Jungle.spec"

    package_release.write_spec(spec_path)

    content = spec_path.read_text(encoding="utf-8")
    assert "collect_submodules" not in content
    assert "hiddenimports=[]" in content
    assert "pathex=['src']" in content


def test_verify_release_artifacts_requires_required_statements(tmp_path, monkeypatch) -> None:
    release_dir = tmp_path / "release"
    internal_dir = release_dir / "_internal"
    internal_dir.mkdir(parents=True)
    (release_dir / "Jungle.exe").write_text("binary", encoding="utf-8")
    (release_dir / "README.txt").write_text("missing statements", encoding="utf-8")
    (internal_dir / "python312.dll").write_text("dll", encoding="utf-8")
    (internal_dir / "VCRUNTIME140.dll").write_text("runtime", encoding="utf-8")
    package_release.create_release_zip(release_dir)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "prompt.md").write_text("prompt", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Missing release README requirement"):
        package_release.verify_release_artifacts(release_dir)


def test_run_packaged_smoke_executes_release_exe_and_reads_result(tmp_path, monkeypatch) -> None:
    release_dir = tmp_path / "release"
    release_dir.mkdir()
    exe = release_dir / "Jungle.exe"
    exe.write_text("binary", encoding="utf-8")
    result = release_dir / "release_smoke_result.txt"
    calls: list[tuple[list[str], Path]] = []

    def fake_run(command: list[str], cwd: Path, check: bool) -> None:
        assert check is True
        calls.append((command, cwd))
        result.write_text("winner=blue\nresult=den_entry\nturns=42", encoding="utf-8")

    monkeypatch.setattr(smoke_release.subprocess, "run", fake_run)

    result_path = smoke_release.run_packaged_smoke(release_dir)

    assert result_path == result
    assert calls == [([str(exe), "--smoke-test"], release_dir)]


def test_run_packaged_smoke_rejects_zero_turn_result(tmp_path, monkeypatch) -> None:
    release_dir = tmp_path / "release"
    release_dir.mkdir()
    exe = release_dir / "Jungle.exe"
    exe.write_text("binary", encoding="utf-8")
    result = release_dir / "release_smoke_result.txt"

    def fake_run(command: list[str], cwd: Path, check: bool) -> None:
        result.write_text("winner=none\nresult=ongoing\nturns=0", encoding="utf-8")

    monkeypatch.setattr(smoke_release.subprocess, "run", fake_run)

    with pytest.raises(SystemExit, match="did not play any turns"):
        smoke_release.run_packaged_smoke(release_dir)


def test_run_packaged_smoke_rejects_unknown_result_type(tmp_path, monkeypatch) -> None:
    release_dir = tmp_path / "release"
    release_dir.mkdir()
    exe = release_dir / "Jungle.exe"
    exe.write_text("binary", encoding="utf-8")
    result = release_dir / "release_smoke_result.txt"

    def fake_run(command: list[str], cwd: Path, check: bool) -> None:
        result.write_text("winner=blue\nresult=surprise\nturns=3", encoding="utf-8")

    monkeypatch.setattr(smoke_release.subprocess, "run", fake_run)

    with pytest.raises(SystemExit, match="invalid result"):
        smoke_release.run_packaged_smoke(release_dir)


def test_package_release_main_runs_packaged_smoke_before_verification(monkeypatch, tmp_path) -> None:
    order: list[str] = []
    result_file = tmp_path / "release_smoke_result.txt"
    result_file.write_text("winner=blue", encoding="utf-8")

    monkeypatch.setattr(package_release, "clean", lambda: order.append("clean"))
    monkeypatch.setattr(package_release, "generate_assets", lambda: order.append("assets"))
    monkeypatch.setattr(package_release, "build_bundle", lambda: order.append("build") or (tmp_path / "bundle"))
    monkeypatch.setattr(package_release, "assemble_release", lambda bundle: order.append(f"assemble:{bundle.name}"))
    monkeypatch.setattr(package_release, "write_release_readme", lambda: order.append("readme") or (tmp_path / "README.txt"))
    monkeypatch.setattr(package_release, "run_packaged_smoke", lambda release: order.append("smoke") or result_file)
    monkeypatch.setattr(package_release, "create_release_zip", lambda: order.append("zip") or (tmp_path / "Jungle.zip"))
    monkeypatch.setattr(package_release, "verify_release_artifacts", lambda: order.append("verify"))

    package_release.main()

    assert order == ["clean", "assets", "build", "assemble:bundle", "readme", "smoke", "zip", "verify"]
