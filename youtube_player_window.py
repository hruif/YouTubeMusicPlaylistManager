import sys

import webview


def main():
    player_url = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else "YouTube Queue"
    webview.create_window(title, player_url, width=1120, height=720, min_size=(980, 640))
    webview.start()


if __name__ == "__main__":
    main()
