"""YouTube Music auth views: the "Set Queue Headers" (browser-auth) screen, and
(later) the OAuth connect screen.

Tk view builders extracted from the UI controller (step 2 of decomposing ui.py).
They build the widgets and wire buttons to the controller's auth methods (the
networking/threading stays on the controller).
"""
import tkinter as tk
from tkinter import ttk


def build_browser_auth(controller, parent):
    controller.current_display_view = "youtube_browser_auth"
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(3, weight=1)

    status_var = tk.StringVar(value=f"Status: {controller._youtube_music_queue_auth_status()}")

    title = ttk.Label(parent, text="Set YouTube Music Queue Headers", font=("Helvetica", 15, "bold"))
    title.grid(row=0, column=0, sticky=tk.W, pady=(0, 12))

    intro = ttk.Label(
        parent,
        text=(
            "\"Play in YouTube Music\" needs your YouTube Music browser headers to create a private "
            "playlist on your account. This is a one-time setup (repeat it only if it stops working, "
            "e.g. after signing out). The headers stay on this computer and are never uploaded anywhere."
        ),
        wraplength=760,
    )
    intro.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 12))

    steps_frame = ttk.LabelFrame(parent, text="How to copy your headers", padding="12")
    steps_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 12))
    steps_frame.columnconfigure(0, weight=1)

    steps_text = ttk.Label(
        steps_frame,
        text=(
            "1. Click \"Open YouTube Music\" and make sure you are signed in.\n"
            "2. Open your browser's developer tools (⌥⌘I on Mac, Ctrl+Shift+I on Windows, in "
            "Chrome/Edge or Firefox) and select the Network tab.\n"
            "3. Reload the page, then type  browse  in the Network filter box.\n"
            "4. Click a POST request named \"browse\" with status 200.\n"
            "5. Copy it — Chrome/Edge: right-click → Copy → \"Copy as fetch (Node.js)\".  "
            "Firefox: right-click → Copy Value → \"Copy Request Headers\".\n"
            "6. Paste below, click \"Save Headers\", then \"Test Saved Headers\" to confirm."
        ),
        justify=tk.LEFT,
        wraplength=740,
    )
    steps_text.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 8))

    open_music_button = ttk.Button(
        steps_frame,
        text="Open YouTube Music",
        command=lambda: controller._open_external_url("https://music.youtube.com/"),
    )
    open_music_button.grid(row=1, column=0, sticky=tk.W, padx=(0, 8))

    docs_button = ttk.Button(
        steps_frame,
        text="Browser Auth Help",
        command=lambda: controller._open_external_url("https://ytmusicapi.readthedocs.io/en/stable/setup/browser.html"),
    )
    docs_button.grid(row=1, column=1, sticky=tk.W)

    headers_frame = ttk.LabelFrame(parent, text="Request Headers", padding="8")
    headers_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 12))
    headers_frame.columnconfigure(0, weight=1)
    headers_frame.rowconfigure(0, weight=1)

    headers_text = tk.Text(headers_frame, height=12, wrap=tk.NONE)
    headers_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    headers_scrollbar = ttk.Scrollbar(headers_frame, orient=tk.VERTICAL, command=headers_text.yview)
    headers_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    headers_text.configure(yscrollcommand=headers_scrollbar.set)

    status_label = ttk.Label(parent, textvariable=status_var, justify=tk.LEFT)
    status_label.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    actions_frame = ttk.Frame(parent)
    actions_frame.grid(row=5, column=0, sticky=(tk.W, tk.E))
    actions_frame.columnconfigure(3, weight=1)

    save_button = ttk.Button(
        actions_frame,
        text="Save Headers",
        command=lambda: controller.save_youtube_music_browser_headers(headers_text, status_var, test_button),
    )
    save_button.grid(row=0, column=0, sticky=tk.W, padx=(0, 8))

    test_button = ttk.Button(
        actions_frame,
        text="Test Saved Headers",
        command=lambda: controller.test_youtube_music_browser_headers(status_var, test_button),
    )
    test_button.grid(row=0, column=1, sticky=tk.W, padx=(0, 8))
    if not controller.youtube_account.has_browser_auth():
        test_button.state(["disabled"])

    back_button = ttk.Button(actions_frame, text="Back to Settings", command=controller.show_settings_display)
    back_button.grid(row=0, column=2, sticky=tk.W)


def build_oauth(controller, parent):
    controller.current_display_view = "youtube_auth"
    parent.columnconfigure(0, weight=1)

    saved_credentials = controller.youtube_account.load_client_credentials() or {}
    client_id_var = tk.StringVar(value=saved_credentials.get("client_id", ""))
    client_secret_var = tk.StringVar(value=saved_credentials.get("client_secret", ""))
    status_var = tk.StringVar(value=f"Status: {controller._youtube_music_auth_status()}")
    code_var = tk.StringVar(value="No sign-in code yet")
    url_var = tk.StringVar(value="")

    title = ttk.Label(parent, text="Connect YouTube Music", font=("Helvetica", 15, "bold"))
    title.grid(row=0, column=0, sticky=tk.W, pady=(0, 12))

    intro = ttk.Label(
        parent,
        text=(
            "This OAuth sign-in is kept for account experiments and future features. The hidden temporary "
            "queue feature currently uses Settings > Set Queue Headers because ytmusicapi OAuth playlist "
            "writes can fail with HTTP 400."
        ),
        wraplength=720,
    )
    intro.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 12))

    setup_frame = ttk.LabelFrame(parent, text="One-Time Google Setup", padding="12")
    setup_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 12))
    setup_frame.columnconfigure(0, weight=1)

    setup_text = ttk.Label(
        setup_frame,
        text=(
            "If you still want to test OAuth, create an OAuth Client ID with application type "
            "\"TVs and Limited Input devices\". Desktop OAuth clients will fail with this sign-in flow. "
            "If your OAuth app is External and in Testing mode, add your Google account under "
            "Audience > Test users. Copy the TV client ID and client secret below."
        ),
        wraplength=700,
    )
    setup_text.grid(row=0, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(0, 8))

    credentials_button = ttk.Button(
        setup_frame,
        text="Open Credentials",
        command=lambda: controller._open_external_url("https://console.cloud.google.com/apis/credentials"),
    )
    credentials_button.grid(row=1, column=0, sticky=tk.W, padx=(0, 8))

    help_button = ttk.Button(
        setup_frame,
        text="OAuth Help",
        command=lambda: controller._open_external_url("https://ytmusicapi.readthedocs.io/en/stable/setup/oauth.html"),
    )
    help_button.grid(row=1, column=1, sticky=tk.W)

    audience_button = ttk.Button(
        setup_frame,
        text="Open Audience",
        command=lambda: controller._open_external_url("https://console.cloud.google.com/auth/audience"),
    )
    audience_button.grid(row=1, column=2, sticky=tk.W, padx=(8, 0))

    credentials_frame = ttk.LabelFrame(parent, text="OAuth Client", padding="12")
    credentials_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 12))
    credentials_frame.columnconfigure(1, weight=1)

    client_id_label = ttk.Label(credentials_frame, text="Client ID:")
    client_id_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=(0, 6))
    client_id_entry = ttk.Entry(credentials_frame, textvariable=client_id_var)
    client_id_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 6))

    client_secret_label = ttk.Label(credentials_frame, text="Client secret:")
    client_secret_label.grid(row=1, column=0, sticky=tk.W, padx=(0, 8))
    client_secret_entry = ttk.Entry(credentials_frame, textvariable=client_secret_var, show="*")
    client_secret_entry.grid(row=1, column=1, sticky=(tk.W, tk.E))

    sign_in_frame = ttk.LabelFrame(parent, text="Sign In", padding="12")
    sign_in_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 12))
    sign_in_frame.columnconfigure(0, weight=1)

    status_label = ttk.Label(sign_in_frame, textvariable=status_var)
    status_label.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 8))

    code_label = ttk.Label(sign_in_frame, textvariable=code_var, font=("Helvetica", 18, "bold"))
    code_label.grid(row=1, column=0, sticky=tk.W)

    copy_button = ttk.Button(
        sign_in_frame,
        text="Copy Code",
        command=lambda: controller._copy_to_clipboard(code_var.get()),
    )
    copy_button.grid(row=1, column=1, sticky=tk.W, padx=(12, 6))

    def open_current_sign_in_url():
        sign_in_url = url_var.get().strip()
        if not sign_in_url:
            status_var.set("Status: click Save and Start Sign-In first to request a code.")
            return

        opened = controller._open_external_url(sign_in_url)
        if opened:
            status_var.set("Status: sign-in page opened. Finish Google sign-in in the browser.")
        else:
            status_var.set("Status: could not open the browser automatically. Copy the URL below.")

    open_sign_in_button = ttk.Button(
        sign_in_frame,
        text="Open Sign-In Page",
        command=open_current_sign_in_url,
    )
    open_sign_in_button.grid(row=1, column=2, sticky=tk.W)
    open_sign_in_button.state(["disabled"])

    url_entry = ttk.Entry(sign_in_frame, textvariable=url_var, state="readonly")
    url_entry.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(8, 0))

    start_button = ttk.Button(
        parent,
        text="Save and Start Sign-In",
        command=lambda: controller._start_youtube_music_oauth_flow(
            client_id_var.get(),
            client_secret_var.get(),
            status_var,
            code_var,
            url_var,
            start_button,
            open_sign_in_button,
        ),
    )
    start_button.grid(row=5, column=0, sticky=tk.W)
