from __future__ import annotations

from pathlib import Path

from conftest import load_tool_module

build_release_readme = load_tool_module("package_release").build_release_readme


def test_prompt_artifacts_exist() -> None:
    assert Path("prompt.md").exists()
    assert Path("docs/prompt-closure-checklist.md").exists()


def test_release_readme_template_contains_required_disclosure() -> None:
    content = build_release_readme()
    assert "Model used: gpt-5.5" in content
    assert "Code agent used: Codex" in content
