import sys
import tkinter as tk

from app_info import APP_NAME, PLAYER_WINDOW_ARG
from app_paths import resource_path
from app_platform import configure_macos_app_identity
from ui import PlaylistManagerUI


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    configure_macos_app_identity(APP_NAME, resource_path("assets", "app_icon.png"))

    if argv and argv[0] == PLAYER_WINDOW_ARG:
        from youtube_player_window import run_player_window

        player_url = argv[1] if len(argv) > 1 else ""
        title = argv[2] if len(argv) > 2 else None
        run_player_window(player_url, title)
        return

    root = tk.Tk()
    PlaylistManagerUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
