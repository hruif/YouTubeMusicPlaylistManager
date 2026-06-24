#!/usr/bin/env python3
# Linux WebKitGTK login SPIKE — mirrors electron/login-helper/login.swift (the macOS WKWebView helper).
#
# Question this answers: does Google trust WebKitGTK (WebKit/Safari's engine on Linux) for an
# embedded sign-in, the way it trusts WKWebView on macOS? If yes, the Linux build can reuse the same
# in-app login. If Google shows "this browser or app may not be secure", the hypothesis fails and a
# Linux build would need a manual cookie/header fallback instead.
#
# This is throwaway validation code (not the shipped helper). Run it on a Linux DESKTOP (needs an
# X11/Wayland session — a GUI window opens):
#
#   # Debian/Ubuntu:
#   sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1   # or gir1.2-webkit2-4.0
#   python3 login_linux_spike.py
#
#   # Fedora:
#   sudo dnf install python3-gobject gtk3 webkit2gtk4.1
#   python3 login_linux_spike.py
#
# Then sign in to your Google/YouTube account in the window. SUCCESS = it lands on music.youtube.com
# and prints one JSON line ending in cookie_names that include "SAPISID". FAILURE = Google blocks the
# login ("browser may not be secure") — report that and we'll switch the Linux plan to a manual paste.

import gi
import json
import sys

# Use whichever WebKit2/Soup pair the distro ships (4.1+libsoup3 on newer, 4.0+libsoup2 on older).
_loaded = False
for _wk, _soup in (("4.1", "3.0"), ("4.0", "2.4")):
    try:
        gi.require_version("Gtk", "3.0")
        gi.require_version("WebKit2", _wk)
        gi.require_version("Soup", _soup)
        _loaded = True
        break
    except ValueError:
        continue
if not _loaded:
    sys.stderr.write(
        "WebKit2GTK not found. Install e.g.: sudo apt install python3-gi gir1.2-webkit2-4.1\n"
    )
    print("null")
    sys.exit(1)

from gi.repository import Gtk, WebKit2, GLib, Soup  # noqa: E402,F401  (Soup loads the Cookie type)

LOGIN_URL = (
    "https://accounts.google.com/ServiceLogin"
    "?service=youtube&continue=https%3A%2F%2Fmusic.youtube.com%2F"
)
# httpOnly auth cookies (document.cookie can't see these — we read the network cookie store instead).
AUTH_COOKIES = {"SAPISID", "__Secure-1PAPISID", "__Secure-3PAPISID"}
# WebKitGTK's native UA already presents as WebKit/Safari — leaving it as-is is the actual test. If
# Google blocks it, try uncommenting a macOS-Safari UA override below as a second experiment.
SAFARI_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.5 Safari/605.1.15"
)


class Login:
    def __init__(self):
        self.finished = False
        self.win = Gtk.Window(title="Sign in to YouTube Music")
        self.win.set_default_size(520, 760)
        self.win.connect("destroy", self.on_close)

        self.web = WebKit2.WebView()
        # self.web.get_settings().set_user_agent(SAFARI_UA)  # <- second experiment if default is blocked
        self.win.add(self.web)
        self.win.show_all()

        self.web.load_uri(LOGIN_URL)
        GLib.timeout_add(400, self.poll)

    def on_music_page(self):
        uri = self.web.get_uri() or ""
        return uri.startswith("https://music.youtube.com")

    def poll(self):
        if self.finished:
            return False  # stop the timer
        if self.on_music_page():
            cm = self.web.get_context().get_cookie_manager()
            cm.get_cookies("https://music.youtube.com", None, self.on_cookies, None)
        return True  # keep polling

    def on_cookies(self, manager, result, _user_data):
        try:
            cookies = manager.get_cookies_finish(result)
        except GLib.Error:
            return
        yt = [c for c in cookies if c.get_domain().lstrip(".").endswith("youtube.com")]
        names = sorted({c.get_name() for c in yt})
        if not (AUTH_COOKIES & set(names)):
            return  # signed in to the page but the auth cookie hasn't landed yet
        cookie = "; ".join(f"{c.get_name()}={c.get_value()}" for c in yt)
        self.finish(cookie, names)

    def on_close(self, *_):
        self.finish(None, [])

    def finish(self, cookie, names):
        if self.finished:
            return
        self.finished = True
        if cookie:
            sys.stdout.write(json.dumps({"cookie": cookie, "cookie_names": names}) + "\n")
        else:
            sys.stdout.write("null\n")
        sys.stdout.flush()
        Gtk.main_quit()


Login()
Gtk.main()
