from __future__ import annotations

from pathlib import Path

from jungle.ui.assets import BOARD_ASSETS, PIECE_ASSETS, asset_base_path, required_asset_paths


def test_all_required_assets_exist() -> None:
    missing = [path for path in required_asset_paths() if not path.exists()]
    assert not missing


def test_asset_base_path_points_to_ui_assets_directory() -> None:
    assert asset_base_path().name == "assets"


def test_asset_manifest_has_expected_counts() -> None:
    assert len(BOARD_ASSETS) == 7
    assert len(PIECE_ASSETS) == 16


def test_packaging_script_includes_asset_datas() -> None:
    content = Path("tools/package_release.py").read_text(encoding="utf-8")
    assert "src/jungle/ui/assets" in content
