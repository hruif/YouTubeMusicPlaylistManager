#!/usr/bin/env python3
"""Build and package the legacy Tk/Python app for the current operating system.

PyInstaller does not cross-compile reliably, so Windows/Linux/macOS artifacts should be
built on matching hosts. The GitHub Actions matrix in this repo runs this script on each OS.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from importlib.util import find_spec
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ASSETS_DIR = ROOT / "assets"
ICON_OUTPUT_DIR = ROOT / "build" / "legacy-icons"
SPEC_FILE = ROOT / "YouTubeMusicPlaylistManager.spec"


def platform_label(platform=None):
    platform = platform or sys.platform
    if platform == "darwin":
        return "macOS"
    if platform.startswith("win"):
        return "windows"
    if platform.startswith("linux"):
        return "linux"
    return platform.replace(" ", "-")


def artifact_extension(platform=None):
    return ".tar.gz" if platform_label(platform) == "linux" else ".zip"


def artifact_name(version, debug=False, platform=None):
    debug_suffix = "-debug" if debug else ""
    return (
        f"YouTubeMusicPlaylistManager-{version}{debug_suffix}-python-"
        f"{platform_label(platform)}{artifact_extension(platform)}"
    )


def artifact_path(version, debug=False, platform=None):
    return ROOT / "dist" / artifact_name(version, debug=debug, platform=platform)


def _rounded_mask(size, radius):
    from PIL import Image
    from PIL import ImageDraw

    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size, size), radius=radius, fill=255)
    return mask


def _build_icon_canvas():
    from PIL import Image
    from PIL import ImageDraw

    youtube = Image.open(ASSETS_DIR / "youtube.png").convert("RGBA")
    spotify = Image.open(ASSETS_DIR / "spotify.png").convert("RGBA")

    canvas_size = 1024
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (24, 26, 32, 255))

    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((0, 0, canvas_size, canvas_size), radius=220, fill=(28, 30, 36, 255))
    draw.polygon([(0, 0), (1024, 0), (0, 1024)], fill=(255, 0, 51, 255))
    draw.polygon([(1024, 0), (1024, 1024), (0, 1024)], fill=(30, 185, 84, 255))

    for logo, box in (
        (youtube, (130, 180, 515, 565)),
        (spotify, (510, 460, 890, 840)),
    ):
        logo = logo.resize((box[2] - box[0], box[3] - box[1]), Image.Resampling.LANCZOS)
        canvas.alpha_composite(logo, (box[0], box[1]))

    canvas.putalpha(_rounded_mask(canvas_size, 220))
    return canvas


def build_app_icon(output_dir=ICON_OUTPUT_DIR):
    from PIL import Image

    output_dir.mkdir(parents=True, exist_ok=True)
    app_icon_png = output_dir / "app_icon.png"
    app_icon_icns = output_dir / "app_icon.icns"
    app_icon_ico = output_dir / "app_icon.ico"

    canvas = _build_icon_canvas()
    canvas.resize((512, 512), Image.Resampling.LANCZOS).save(app_icon_png)
    canvas.save(
        app_icon_ico,
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    if sys.platform != "darwin":
        return output_dir

    with tempfile.TemporaryDirectory() as temp_dir:
        iconset = Path(temp_dir) / "app_icon.iconset"
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            canvas.resize((size, size), Image.Resampling.LANCZOS).save(iconset / f"icon_{size}x{size}.png")
            canvas.resize((size * 2, size * 2), Image.Resampling.LANCZOS).save(iconset / f"icon_{size}x{size}@2x.png")

        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(app_icon_icns)], check=True)
    return output_dir


def _archive_base_name(path):
    name = str(path)
    if name.endswith(".tar.gz"):
        return name[:-7]
    return str(path.with_suffix(""))


def _package_directory(folder_path, archive_path):
    if archive_path.exists():
        archive_path.unlink()

    if archive_path.name.endswith(".tar.gz"):
        shutil.make_archive(
            _archive_base_name(archive_path),
            "gztar",
            root_dir=folder_path.parent,
            base_dir=folder_path.name,
        )
        return

    shutil.make_archive(
        _archive_base_name(archive_path),
        "zip",
        root_dir=folder_path.parent,
        base_dir=folder_path.name,
    )


def _package_macos_app(app_path, archive_path):
    if archive_path.exists():
        archive_path.unlink()
    # ditto preserves macOS .app symlinks/resource forks; zipfile/shutil do not.
    subprocess.run(
        ["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(app_path), str(archive_path)],
        check=True,
    )


def build_app(debug=False):
    icon_dir = build_app_icon()
    if find_spec("PyInstaller") is None:
        raise SystemExit(
            "PyInstaller is not installed. Run `python -m pip install -r requirements-build.txt` first."
        )

    env = dict(os.environ)
    env["PLAYLIST_MANAGER_BUILD_ICON_DIR"] = str(icon_dir)
    if debug:
        env["PLAYLIST_MANAGER_BUILD_DEBUG"] = "1"

    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(SPEC_FILE)],
        cwd=ROOT,
        check=True,
        env=env,
    )

    from app.app_info import APP_NAME, APP_VERSION

    bundle_name = f"{APP_NAME} (Debug)" if debug else APP_NAME
    archive_path = artifact_path(APP_VERSION, debug=debug)

    if sys.platform == "darwin":
        built_path = ROOT / "dist" / f"{bundle_name}.app"
        if not built_path.exists():
            raise FileNotFoundError(f"Expected app bundle was not created: {built_path}")
        _package_macos_app(built_path, archive_path)
    else:
        built_path = ROOT / "dist" / bundle_name
        if not built_path.exists():
            raise FileNotFoundError(f"Expected app directory was not created: {built_path}")
        _package_directory(built_path, archive_path)

    print(f"Built {built_path}")
    print(f"Packaged {archive_path}")
    return archive_path


if __name__ == "__main__":
    if any(argument in {"-h", "--help"} for argument in sys.argv[1:]):
        print("Build the legacy Python app for this OS: python tools/build_legacy_python_app.py [--debug]")
        print("  --debug  Show experimental YouTube queue actions; builds a separate '(Debug)' app.")
        raise SystemExit(0)
    build_app(debug="--debug" in sys.argv[1:])
