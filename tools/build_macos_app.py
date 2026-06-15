#!/usr/bin/env python3
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
APP_ICON_PNG = ASSETS_DIR / "app_icon.png"
APP_ICON_ICNS = ASSETS_DIR / "app_icon.icns"
SPEC_FILE = ROOT / "YouTubeMusicPlaylistManager.spec"


def _rounded_mask(size, radius):
    from PIL import Image
    from PIL import ImageDraw

    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size, size), radius=radius, fill=255)
    return mask


def build_app_icon():
    from PIL import Image

    youtube = Image.open(ASSETS_DIR / "youtube.png").convert("RGBA")
    spotify = Image.open(ASSETS_DIR / "spotify.png").convert("RGBA")

    canvas_size = 1024
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (24, 26, 32, 255))

    from PIL import ImageDraw

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
    canvas.resize((512, 512), Image.Resampling.LANCZOS).save(APP_ICON_PNG)

    with tempfile.TemporaryDirectory() as temp_dir:
        iconset = Path(temp_dir) / "app_icon.iconset"
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            canvas.resize((size, size), Image.Resampling.LANCZOS).save(iconset / f"icon_{size}x{size}.png")
            canvas.resize((size * 2, size * 2), Image.Resampling.LANCZOS).save(iconset / f"icon_{size}x{size}@2x.png")

        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(APP_ICON_ICNS)], check=True)


def build_app(debug=False):
    build_app_icon()
    if find_spec("PyInstaller") is None:
        raise SystemExit(
            "PyInstaller is not installed. Run `python -m pip install -r requirements-build.txt` first."
        )

    env = dict(os.environ)
    if debug:
        # Read by the .spec file: bundles the debug runtime hook (shows the experimental
        # YouTube queue actions) and gives the bundle a distinct "(Debug)" name.
        env["PLAYLIST_MANAGER_BUILD_DEBUG"] = "1"

    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(SPEC_FILE)],
        cwd=ROOT,
        check=True,
        env=env,
    )

    from app_info import APP_NAME, APP_VERSION

    bundle_name = f"{APP_NAME} (Debug)" if debug else APP_NAME
    app_path = ROOT / "dist" / f"{bundle_name}.app"
    if not app_path.exists():
        raise FileNotFoundError(f"Expected app bundle was not created: {app_path}")

    archive_suffix = "-debug" if debug else ""
    archive_base = ROOT / "dist" / f"YouTubeMusicPlaylistManager-{APP_VERSION}{archive_suffix}-macOS"
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=app_path.parent, base_dir=app_path.name)
    print(f"Built {app_path}")
    print(f"Packaged {archive_path}")


if __name__ == "__main__":
    if any(argument in {"-h", "--help"} for argument in sys.argv[1:]):
        print("Build a zipped macOS .app: python tools/build_macos_app.py [--debug]")
        print("  --debug  Show the experimental YouTube queue actions; builds a separate '(Debug)' bundle.")
        raise SystemExit(0)
    build_app(debug="--debug" in sys.argv[1:])
