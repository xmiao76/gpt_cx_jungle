from __future__ import annotations

from jungle.app.controller import run_smoke_validation


def test_smoke_validation_script_runs() -> None:
    assert run_smoke_validation() == 0
