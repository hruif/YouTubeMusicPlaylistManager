// Native WKWebView login helper for the Electron app.
//
// Electron's Chromium login window is blocked by Google ("this browser may not be secure"), but a
// real WKWebView IS Safari, which Google trusts — the same reason the Tauri build's login works.
// So Electron spawns this tiny helper for sign-in: it opens a WKWebView, lets the user log in,
// captures the youtube.com session cookies (incl. httpOnly ones like SAPISID, which document.cookie
// can't see), prints them as JSON on stdout, and exits. Electron then hands the cookie to youtubei.js.
//
// Build: swiftc login.swift -O -o login-helper -framework WebKit -framework AppKit

import AppKit
import WebKit

let LOGIN_URL =
  "https://accounts.google.com/ServiceLogin?service=youtube&continue=https%3A%2F%2Fmusic.youtube.com%2F"
// Real Safari UA (WKWebView already presents as Safari; set explicitly to match the Tauri build).
let SAFARI_UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15"
let AUTH_COOKIES = ["SAPISID", "__Secure-1PAPISID", "__Secure-3PAPISID"]

final class LoginDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
  var webView: WKWebView!
  var window: NSWindow!
  var finished = false

  func applicationDidFinishLaunching(_ note: Notification) {
    webView = WKWebView(frame: NSRect(x: 0, y: 0, width: 520, height: 760))
    webView.customUserAgent = SAFARI_UA

    window = NSWindow(
      contentRect: NSRect(x: 0, y: 0, width: 520, height: 760),
      styleMask: [.titled, .closable],
      backing: .buffered, defer: false)
    window.title = "Sign in to YouTube Music"
    window.contentView = webView
    window.delegate = self
    window.center()
    window.makeKeyAndOrderFront(nil)
    NSApp.activate(ignoringOtherApps: true)

    webView.load(URLRequest(url: URL(string: LOGIN_URL)!))
    Timer.scheduledTimer(withTimeInterval: 0.4, repeats: true) { _ in self.poll() }
  }

  // The session is "live" once we've landed on music.youtube.com with an auth cookie present.
  private func onMusicPage() -> Bool { webView.url?.host == "music.youtube.com" }

  private func poll() {
    guard !finished, onMusicPage() else { return }
    webView.configuration.websiteDataStore.httpCookieStore.getAllCookies { cookies in
      let yt = cookies.filter { $0.domain.trimmingCharacters(in: ["."]).hasSuffix("youtube.com") }
      let names = yt.map { $0.name }
      guard AUTH_COOKIES.contains(where: names.contains) else { return }
      let cookie = yt.map { "\($0.name)=\($0.value)" }.joined(separator: "; ")
      self.finish(cookie: cookie, names: Array(Set(names)).sorted())
    }
  }

  // The user closed the window without finishing → cancelled.
  func windowWillClose(_ notification: Notification) { finish(cookie: nil, names: []) }

  private func finish(cookie: String?, names: [String]) {
    if finished { return }
    finished = true
    if let cookie = cookie,
      let data = try? JSONSerialization.data(withJSONObject: ["cookie": cookie, "cookie_names": names]),
      let json = String(data: data, encoding: .utf8)
    {
      FileHandle.standardOutput.write(Data((json + "\n").utf8))
    } else {
      FileHandle.standardOutput.write(Data("null\n".utf8))
    }
    NSApp.terminate(nil)
  }
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = LoginDelegate()
app.delegate = delegate
app.run()
