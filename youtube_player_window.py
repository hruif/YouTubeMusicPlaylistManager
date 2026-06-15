import sys

import webview

from app_info import APP_NAME
from app_paths import resource_path
from app_platform import configure_macos_app_identity


def player_window_title(title=None):
    queue_title = title or "Queue Player"
    return queue_title if queue_title.startswith(APP_NAME) else f"{APP_NAME} - {queue_title}"


def run_player_window(player_url, title=None):
    configure_macos_app_identity(f"{APP_NAME} Player", resource_path("assets", "app_icon.png"))
    webview.create_window(player_window_title(title), player_url, width=1120, height=720, min_size=(980, 640))
    webview.start()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    player_url = argv[0] if argv else ""
    title = argv[1] if len(argv) > 1 else None
    run_player_window(player_url, title)


if __name__ == "__main__":
    main()
