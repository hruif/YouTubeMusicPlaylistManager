# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

from app_info import APP_BUNDLE_IDENTIFIER, APP_NAME, APP_VERSION


ROOT = Path(SPECPATH)
ICON = ROOT / "assets" / "app_icon.icns"


a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        ("assets", "assets"),
        ("web", "web"),
        ("youtube_player_window.py", "."),
        *collect_data_files("tls_client", includes=["dependencies/*"]),
        *collect_data_files("ytmusicapi", includes=["locales/**/*"]),
    ],
    hiddenimports=[
        "AppKit",
        "Foundation",
        "webview",
        "webview.platforms.cocoa",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
    name=APP_NAME,
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
    name=APP_NAME,
)
app = BUNDLE(
    coll,
    name=f"{APP_NAME}.app",
    icon=str(ICON),
    bundle_identifier=APP_BUNDLE_IDENTIFIER,
    info_plist={
        "CFBundleDisplayName": APP_NAME,
        "CFBundleName": APP_NAME,
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": APP_VERSION,
        "NSHighResolutionCapable": "True",
    },
)
