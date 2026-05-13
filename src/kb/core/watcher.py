"""File system watcher for auto-indexing on changes."""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


_WATCHED_EXTENSIONS = {".md", ".pdf", ".docx", ".png", ".jpg", ".jpeg", ".webp"}



class _DebouncedHandler(FileSystemEventHandler):
    """Watchdog handler that debounces rapid file changes before firing."""

    def __init__(self, callback: Callable[[], None], debounce_ms: int = 200):
        super().__init__()
        self._callback = callback
        self._debounce = debounce_ms / 1000.0
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def _watched(self, path: str) -> bool:
        return Path(path).suffix.lower() in _WATCHED_EXTENSIONS


    def _schedule(self):
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, self._fire)
            self._timer.start()

    def _fire(self):
        with self._lock:
            self._timer = None
        try:
            self._callback()
        except Exception:
            logger.warning("File watch callback failed", exc_info=True)

    def on_created(self, event):
        if not event.is_directory and self._watched(event.src_path):
            self._schedule()

    def on_modified(self, event):
        if not event.is_directory and self._watched(event.src_path):
            self._schedule()

    def on_deleted(self, event):
        if not event.is_directory and self._watched(event.src_path):
            self._schedule()

    def on_moved(self, event):
        if not event.is_directory and self._watched(event.dest_path):
            self._schedule()

    def stop(self):
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None


def start_watcher(
    watch_dir: Path,
    callback: Callable[[], None],
    debounce_ms: int = 200,
) -> Observer:
    """Start a watchdog observer monitoring watch_dir for .md file changes.

    Returns the started Observer; caller must call observer.stop() + observer.join()
    to shut down cleanly.
    """
    handler = _DebouncedHandler(callback, debounce_ms=debounce_ms)
    observer = Observer()
    observer.schedule(handler, str(watch_dir), recursive=True)
    observer.start()
    return observer
