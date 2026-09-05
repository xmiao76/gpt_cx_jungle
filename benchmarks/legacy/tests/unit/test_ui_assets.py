from __future__ import annotations

from pathlib import Path

from jungle.ui.assets import BOARD_ASSETS, PIECE_ASSETS, asset_base_path, required_asset_paths, scale_image
from jungle.ui.theme import SUPPORTED_ASSET_SCALES


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


def test_supported_asset_scales_cover_compact_sizes() -> None:
    assert SUPPORTED_ASSET_SCALES == ((1, 1), (5, 6), (3, 4), (2, 3))


def test_scale_image_uses_tk_compatible_zoom_subsample_path() -> None:
    class FakeImage:
        def __init__(self) -> None:
            self.ops: list[tuple[str, int, int]] = []

        def zoom(self, x: int, y: int):
            self.ops.append(("zoom", x, y))
            return self

        def subsample(self, x: int, y: int):
            self.ops.append(("subsample", x, y))
            return self

    image = FakeImage()
    scaled = scale_image(image, (3, 4))

    assert scaled is image
    assert image.ops == [("zoom", 3, 3), ("subsample", 4, 4)]
