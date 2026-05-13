import tkinter as tk
from ui import PlaylistManagerUI

if __name__ == "__main__":
    root = tk.Tk()
    app = PlaylistManagerUI(root)
    root.mainloop()