import http.server
import importlib.util
import json
import subprocess
import sys
import threading
import urllib.parse
import uuid
import webbrowser
from pathlib import Path


class YouTubeQueuePlayer:
    """Serves queue data locally and opens the YouTube player surface."""

    def __init__(
        self,
        player_file,
        launcher_file=None,
        host="127.0.0.1",
        queue_cache_limit=20,
        browser_open=None,
        process_launcher=None,
        native_available=None,
        unavailable_callback=None
    ):
        self.player_file = Path(player_file)
        self.launcher_file = Path(launcher_file) if launcher_file else None
        self.host = host
        self.queue_cache_limit = queue_cache_limit
        self.browser_open = browser_open or webbrowser.open
        self.process_launcher = process_launcher or subprocess.Popen
        self.native_available = native_available
        self.unavailable_callback = unavailable_callback
        self.server = None
        self.thread = None
        self.base_url = None
        self.queues = {}

    def shutdown(self):
        if not self.server:
            return

        server = self.server
        thread = self.thread
        self.server = None
        self.thread = None
        self.base_url = None

        server.shutdown()
        server.server_close()
        if thread:
            thread.join(timeout=1)

    def open_queue(self, title, queue_tracks):
        player_url = self.queue_url(title, queue_tracks)
        return self._open_player_url(player_url, title or "YouTube Queue")

    def queue_url(self, title, queue_tracks):
        base_url = self._ensure_server()
        queue_token = self.store_queue(title, queue_tracks)
        return f"{base_url}/player?{urllib.parse.urlencode({'queue': queue_token})}"

    def store_queue(self, title, queue_tracks):
        queue_token = uuid.uuid4().hex
        self.queues[queue_token] = self.queue_payload(title, queue_tracks)
        while len(self.queues) > self.queue_cache_limit:
            oldest_token = next(iter(self.queues))
            if oldest_token == queue_token:
                break
            self.queues.pop(oldest_token, None)
        return queue_token

    def queue_payload(self, title, queue_tracks):
        return {
            'title': title or 'YouTube Queue',
            'tracks': queue_tracks
        }

    def _ensure_server(self):
        if self.server:
            return self.base_url

        if not self.player_file.exists():
            raise FileNotFoundError(f"Missing YouTube player asset: {self.player_file}")

        # The handler closes over this object so queue payloads stay in memory only.
        owner = self

        class YouTubeQueueHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                parsed_url = urllib.parse.urlparse(self.path)
                if parsed_url.path in ('/', '/player'):
                    self._send_player_html()
                    return

                if parsed_url.path.startswith('/queue/'):
                    queue_token = urllib.parse.unquote(parsed_url.path.removeprefix('/queue/'))
                    self._send_queue(queue_token)
                    return

                if parsed_url.path == '/favicon.ico':
                    self.send_response(204)
                    self.end_headers()
                    return

                self.send_error(404)

            def do_POST(self):
                parsed_url = urllib.parse.urlparse(self.path)
                if parsed_url.path == '/unavailable':
                    self._mark_unavailable()
                    return

                self.send_error(404)

            def log_message(self, _format, *args):
                return

            def _send_player_html(self):
                html_text = owner.player_file.read_text(encoding='utf-8')
                self._send_bytes(html_text.encode('utf-8'), 'text/html; charset=utf-8')

            def _send_queue(self, queue_token):
                payload = owner.queues.get(queue_token)
                if payload is None:
                    self.send_error(404, "Queue not found")
                    return

                payload_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')
                self._send_bytes(payload_bytes, 'application/json; charset=utf-8')

            def _mark_unavailable(self):
                try:
                    content_length = int(self.headers.get('Content-Length', '0') or 0)
                    body_text = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
                    payload = json.loads(body_text or '{}')
                    if not isinstance(payload, dict):
                        raise ValueError("Expected a JSON object")
                    owner.mark_unavailable(payload)
                except Exception as error:
                    self.send_error(400, str(error))
                    return

                self._send_bytes(b'{}', 'application/json; charset=utf-8')

            def _send_bytes(self, payload_bytes, content_type):
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(payload_bytes)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(payload_bytes)

        server = http.server.ThreadingHTTPServer((self.host, 0), YouTubeQueueHandler)
        server.daemon_threads = True

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        self.server = server
        self.thread = thread
        self.base_url = f"http://{self.host}:{server.server_port}"
        return self.base_url

    def mark_unavailable(self, payload):
        if callable(self.unavailable_callback):
            self.unavailable_callback(payload)

    def _open_player_url(self, player_url, title):
        if self._open_native_player(player_url, title):
            return "native"

        # Browser fallback keeps playback usable when the optional pywebview dependency is absent.
        self.browser_open(player_url)
        return "browser"

    def _open_native_player(self, player_url, title):
        if not self._native_player_available():
            return False

        # Use a subprocess so pywebview's GUI loop cannot interfere with Tk's main loop.
        self.process_launcher(
            [
                sys.executable,
                str(self.launcher_file),
                player_url,
                title or "YouTube Queue"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return True

    def _native_player_available(self):
        if not self.launcher_file or not self.launcher_file.exists():
            return False
        if self.native_available is not None:
            return bool(self.native_available)
        return importlib.util.find_spec("webview") is not None
