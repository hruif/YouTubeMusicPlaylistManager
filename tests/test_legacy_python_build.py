from tools import build_legacy_python_app


def test_artifact_name_is_platform_specific():
    assert (
        build_legacy_python_app.artifact_name("0.6.0", platform="win32")
        == "YouTubeMusicPlaylistManager-0.6.0-python-windows.zip"
    )
    assert (
        build_legacy_python_app.artifact_name("0.6.0", platform="linux")
        == "YouTubeMusicPlaylistManager-0.6.0-python-linux.tar.gz"
    )
    assert (
        build_legacy_python_app.artifact_name("0.6.0", platform="darwin")
        == "YouTubeMusicPlaylistManager-0.6.0-python-macOS.zip"
    )


def test_debug_artifact_name_keeps_platform_suffix():
    assert (
        build_legacy_python_app.artifact_name("0.6.0", debug=True, platform="win32")
        == "YouTubeMusicPlaylistManager-0.6.0-debug-python-windows.zip"
    )
