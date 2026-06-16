"""Single-instance guard.

Prevents two copies of the app from running at once, which would otherwise race
on the shared temporary-playlist records and on auto-delete-on-exit. On POSIX we
use an advisory ``flock`` that the OS releases automatically if the process dies
(even on a crash), so a stale lock cannot wedge future launches. On platforms
without ``fcntl`` we fall back to a PID file with a liveness check.
"""

import os
from pathlib import Path

from app.app_paths import private_user_data_path


class SingleInstanceLock:
    def __init__(self, lock_file=None):
        # Keep the lock in the same (always user-writable) data dir as the temp-playlist records
        # it guards, so every instance sharing those records shares the lock — including
        # from-source runs and across separate repo checkouts. The debug bundle's data dir is
        # already separate, so it gets its own lock.
        self.lock_file = Path(lock_file or private_user_data_path("instance.lock"))
        self._handle = None
        self._using_pidfile = False

    def acquire(self):
        """Return True if this process now owns the lock, False if another live
        instance holds it."""
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            import fcntl
        except ImportError:
            return self._acquire_pidfile()

        handle = self.lock_file.open("w")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False

        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        self._handle = handle
        return True

    def release(self):
        if self._using_pidfile:
            self._release_pidfile()
            self._using_pidfile = False
            return
        if self._handle is None:
            return
        try:
            import fcntl

            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            self._handle.close()
        except Exception:
            pass
        self._handle = None

    def _release_pidfile(self):
        try:
            current = int(self.lock_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return
        if current == os.getpid():
            try:
                self.lock_file.unlink()
            except OSError:
                pass

    def _acquire_pidfile(self):
        try:
            existing_pid = int(self.lock_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            existing_pid = None

        if existing_pid is not None and self._pid_is_alive(existing_pid):
            return False

        self.lock_file.write_text(str(os.getpid()), encoding="utf-8")
        self._using_pidfile = True
        return True

    @staticmethod
    def _pid_is_alive(pid):
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except OSError as error:
            import errno

            return getattr(error, "errno", None) == errno.EPERM
        return True
