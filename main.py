import tkinter as tk
from tkinter import messagebox

from app_info import APP_NAME
from app_lock import SingleInstanceLock
from app_paths import resource_path
from app_platform import configure_macos_app_identity
from ui import PlaylistManagerUI


def main():
    configure_macos_app_identity(APP_NAME, resource_path("assets", "app_icon.png"))

    root = tk.Tk()

    instance_lock = SingleInstanceLock()
    if not instance_lock.acquire():
        root.withdraw()
        messagebox.showwarning(
            APP_NAME,
            f"{APP_NAME} is already running.\n\n"
            "Only one copy can run at a time so temporary playlists are not deleted "
            "or modified by two windows at once. Switch to the open window instead.",
        )
        root.destroy()
        return

    try:
        PlaylistManagerUI(root)
        root.mainloop()
    finally:
        instance_lock.release()


if __name__ == "__main__":
    main()
