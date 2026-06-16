import sys


def configure_macos_app_identity(app_name, icon_path=None):
    if sys.platform != "darwin":
        return

    try:
        from Foundation import NSProcessInfo

        NSProcessInfo.processInfo().setProcessName_(app_name)
    except Exception:
        pass
