# Build Provenance Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record `GPT 5.6-Sol`, `Ultra`, and `Codex` in the source README and every generated release README, then rebuild and verify the release package.

**Architecture:** Keep release provenance as constants in `tools/package_release.py`, render all three disclosures through the existing README generator, and require them during artifact validation. Mirror the exact values in repository documentation and enforce both source and generated text with focused tests.

**Tech Stack:** Python 3.12, pytest, PyInstaller packaging workflow, Markdown/plain-text release documentation, ZIP validation via Python's `zipfile`.

---

### Task 1: Enforce And Implement Current Provenance

**Files:**
- Modify: `tests/unit/test_packaging.py`
- Modify: `tests/integration/test_packaging_smoke.py`
- Modify: `tools/package_release.py`
- Modify: `README.md`
- Modify: `docs/prompt-closure-checklist.md`

- [ ] **Step 1: Update generated-README assertions and add a source-README assertion**

Replace the existing generated disclosure assertions with:

```python
def test_build_release_readme_includes_required_provenance_statements() -> None:
    content = package_release.build_release_readme()
    assert "Model used: GPT 5.6-Sol" in content
    assert "Reasoning effort: Ultra" in content
    assert "Code agent used: Codex" in content
```

Update the integration template test and add the source README check:

```python
def test_release_readme_template_contains_required_disclosure() -> None:
    content = build_release_readme()
    assert "Model used: GPT 5.6-Sol" in content
    assert "Reasoning effort: Ultra" in content
    assert "Code agent used: Codex" in content


def test_source_readme_contains_required_disclosure() -> None:
    content = Path("README.md").read_text(encoding="utf-8")
    assert "Model used: GPT 5.6-Sol" in content
    assert "Reasoning effort: Ultra" in content
    assert "Code agent used: Codex" in content
```

- [ ] **Step 2: Run focused tests and confirm they fail for stale or absent metadata**

Run:

```powershell
python -m pytest tests/unit/test_packaging.py::test_build_release_readme_includes_required_provenance_statements tests/integration/test_packaging_smoke.py::test_release_readme_template_contains_required_disclosure tests/integration/test_packaging_smoke.py::test_source_readme_contains_required_disclosure -q
```

Expected: three failures because the model is still `gpt-5.5` and the reasoning-effort line is absent.

- [ ] **Step 3: Update the release provenance constants and generated text**

Use these constants and required disclosures in `tools/package_release.py`:

```python
MODEL_NAME = "GPT 5.6-Sol"
EFFORT_NAME = "Ultra"
AGENT_NAME = "Codex"
REQUIRED_DISCLOSURES = (
    f"Model used: {MODEL_NAME}",
    f"Reasoning effort: {EFFORT_NAME}",
    f"Code agent used: {AGENT_NAME}",
)
```

Extend the README builder signature and its Important Notes block:

```python
def build_release_readme(
    model_name: str = MODEL_NAME,
    effort_name: str = EFFORT_NAME,
    agent_name: str = AGENT_NAME,
) -> str:
```

```text
- Model used: {model_name}
- Reasoning effort: {effort_name}
- Code agent used: {agent_name}
```

- [ ] **Step 4: Mirror the exact provenance in repository documentation**

Replace the current two-line README disclosure with:

```markdown
## Build Provenance

- `Model used: GPT 5.6-Sol`
- `Reasoning effort: Ultra`
- `Code agent used: Codex`
```

Update the nested disclosure list in `docs/prompt-closure-checklist.md` to contain the same three exact lines.

- [ ] **Step 5: Run focused tests and confirm they pass**

Run the focused command from Step 2.

Expected: `3 passed`.

- [ ] **Step 6: Commit source, tests, and documentation**

```powershell
git add README.md docs/prompt-closure-checklist.md tools/package_release.py tests/unit/test_packaging.py tests/integration/test_packaging_smoke.py
git commit -m "docs: record current build provenance"
```

### Task 2: Rebuild And Verify Release Artifacts

**Files:**
- Modify: `release/README.txt`
- Modify: `release/Jungle.zip`

- [ ] **Step 1: Rebuild the release and run its packaged smoke test**

Run:

```powershell
python -m tools.package_release
```

Expected: PyInstaller completes, the packaged executable reports a valid nonzero-turn smoke result, and the command prints `Release created at` followed by the repository release path.

- [ ] **Step 2: Verify generated and archived README metadata**

Run:

```powershell
@'
from pathlib import Path
import zipfile

required = (
    "Model used: GPT 5.6-Sol",
    "Reasoning effort: Ultra",
    "Code agent used: Codex",
)
release_text = Path("release/README.txt").read_text(encoding="utf-8")
with zipfile.ZipFile("release/Jungle.zip") as archive:
    archived_text = archive.read("README.txt").decode("utf-8")
    names = set(archive.namelist())
for disclosure in required:
    assert disclosure in release_text
    assert disclosure in archived_text
for artifact in ("Jungle.exe", "README.txt", "_internal/python312.dll", "_internal/VCRUNTIME140.dll"):
    assert artifact in names
print("release provenance verified")
'@ | python -
```

Expected: `release provenance verified`.

- [ ] **Step 3: Run the full regression suite and static checks**

Run:

```powershell
python -m pytest -q
python -m compileall -q src tools
git diff --check
```

Expected: all tests pass, compilation exits zero, and `git diff --check` produces no output.

- [ ] **Step 4: Commit the regenerated release artifacts**

```powershell
git add release/README.txt release/Jungle.zip
git commit -m "build: package current provenance metadata"
```

- [ ] **Step 5: Confirm final branch state**

Run:

```powershell
git status --short --branch
git log --oneline -4
```

Expected: a clean `5.5xhigh` worktree with the provenance source commit and regenerated-release commit at the tip.
