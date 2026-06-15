# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

from app_info import APP_BUNDLE_IDENTIFIER, APP_NAME, APP_VERSION


ROOT = Path(SPECPATH)
ICON = ROOT / "assets" / "app_icon.icns"

# Debug builds (python tools/build_macos_app.py --debug) bundle a runtime hook that
# turns on the experimental YouTube queue actions, and use a distinct app name so the
# debug bundle does not overwrite or get confused with the release build.
DEBUG_BUILD = os.environ.get("PLAYLIST_MANAGER_BUILD_DEBUG", "").lower() in {"1", "true", "yes", "on"}
BUNDLE_NAME = f"{APP_NAME} (Debug)" if DEBUG_BUILD else APP_NAME
RUNTIME_HOOKS = [str(ROOT / "tools" / "debug_queue_runtime_hook.py")] if DEBUG_BUILD else []


a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        ("assets", "assets"),
        *collect_data_files("tls_client", includes=["dependencies/*"]),
        *collect_data_files("ytmusicapi", includes=["locales/**/*"]),
    ],
    hiddenimports=[
        "AppKit",
        "Foundation",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=RUNTIME_HOOKS,
    excludes=[
        "black",
        "docutils",
        "IPython",
        "jedi",
        "jupyter",
        "jupyter_client",
        "jupyter_core",
        "matplotlib",
        "nbformat",
        "notebook",
        "numpy",
        "pandas",
        "PIL",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "scipy",
        "sphinx",
        "tkinter.test",
        "zmq",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=BUNDLE_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=BUNDLE_NAME,
)
app = BUNDLE(
    coll,
    name=f"{BUNDLE_NAME}.app",
    icon=str(ICON),
    bundle_identifier=APP_BUNDLE_IDENTIFIER + (".debug" if DEBUG_BUILD else ""),
    info_plist={
        "CFBundleDisplayName": BUNDLE_NAME,
        "CFBundleName": BUNDLE_NAME,
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": APP_VERSION,
        "NSHighResolutionCapable": "True",
    },
)
