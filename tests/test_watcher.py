"""Tests for file system watcher module."""

import threading
import time
from pathlib import Path

from watchdog.events import (
    DirCreatedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
)

from kb.core.watcher import _DebouncedHandler, start_watcher


# ---------------------------------------------------------------------------
# Test 1: Handler schedules callback on file creation
# ---------------------------------------------------------------------------
def test_handler_schedules_callback(tmp_path: Path) -> None:
    """FileCreatedEvent for a .md file should trigger the callback after debounce."""
    called = threading.Event()

    def cb() -> None:
        called.set()

    handler = _DebouncedHandler(callback=cb, debounce_ms=50)
    event = FileCreatedEvent(str(tmp_path / "test.md"))
    event.is_directory = False
    handler.on_created(event)

    # Callback should fire after debounce delay
    assert called.wait(timeout=1.0), "Callback was not called within timeout"


# ---------------------------------------------------------------------------
# Test 2: Multiple rapid events debounce — callback fires only once
# ---------------------------------------------------------------------------
def test_handler_debounces_multiple_events(tmp_path: Path) -> None:
    """5 rapid FileModifiedEvents should result in exactly one callback invocation."""
    call_count = 0
    lock = threading.Lock()

    def cb() -> None:
        nonlocal call_count
        with lock:
            call_count += 1

    handler = _DebouncedHandler(callback=cb, debounce_ms=100)
    event = FileModifiedEvent(str(tmp_path / "note.md"))
    event.is_directory = False

    # Fire 5 events in rapid succession
    for _ in range(5):
        handler.on_modified(event)

    # Wait long enough for the debounce window + callback to fire
    time.sleep(0.3)

    with lock:
        assert call_count == 1, f"Expected 1 callback, got {call_count}"


# ---------------------------------------------------------------------------
# Test 3: Handler ignores non-.md files
# ---------------------------------------------------------------------------
def test_handler_ignores_non_md_files(tmp_path: Path) -> None:
    """FileCreatedEvent for a non-.md file should NOT trigger the callback."""
    called = threading.Event()

    def cb() -> None:
        called.set()

    handler = _DebouncedHandler(callback=cb, debounce_ms=50)
    event = FileCreatedEvent(str(tmp_path / "image.png"))
    event.is_directory = False
    handler.on_created(event)

    # Should NOT fire — sleep past debounce and check
    time.sleep(0.15)
    assert not called.is_set(), "Callback should NOT have been called for non-.md file"


# ---------------------------------------------------------------------------
# Test 4: Handler ignores directory events
# ---------------------------------------------------------------------------
def test_handler_ignores_directories(tmp_path: Path) -> None:
    """DirCreatedEvent (is_directory=True) should NOT trigger the callback."""
    called = threading.Event()

    def cb() -> None:
        called.set()

    handler = _DebouncedHandler(callback=cb, debounce_ms=50)
    event = DirCreatedEvent(str(tmp_path / "notes.md"))
    event.is_directory = True
    handler.on_created(event)

    time.sleep(0.15)
    assert not called.is_set(), "Callback should NOT have been called for directory"


# ---------------------------------------------------------------------------
# Test 5: on_modified triggers for .md files
# ---------------------------------------------------------------------------
def test_handler_on_modified(tmp_path: Path) -> None:
    """FileModifiedEvent for a .md file should trigger the callback."""
    called = threading.Event()

    def cb() -> None:
        called.set()

    handler = _DebouncedHandler(callback=cb, debounce_ms=50)
    event = FileModifiedEvent(str(tmp_path / "doc.md"))
    event.is_directory = False
    handler.on_modified(event)

    assert called.wait(timeout=1.0), "Callback was not called for on_modified"


# ---------------------------------------------------------------------------
# Test 6: on_deleted triggers for .md files
# ---------------------------------------------------------------------------
def test_handler_on_deleted(tmp_path: Path) -> None:
    """FileDeletedEvent for a .md file should trigger the callback."""
    called = threading.Event()

    def cb() -> None:
        called.set()

    handler = _DebouncedHandler(callback=cb, debounce_ms=50)
    event = FileDeletedEvent(str(tmp_path / "old.md"))
    event.is_directory = False
    handler.on_deleted(event)

    assert called.wait(timeout=1.0), "Callback was not called for on_deleted"


# ---------------------------------------------------------------------------
# Test 7: on_moved triggers when destination is .md file
# ---------------------------------------------------------------------------
def test_handler_on_moved(tmp_path: Path) -> None:
    """FileMovedEvent where dest_path ends in .md should trigger the callback."""
    called = threading.Event()

    def cb() -> None:
        called.set()

    handler = _DebouncedHandler(callback=cb, debounce_ms=50)
    event = FileMovedEvent(
        str(tmp_path / "old.txt"), str(tmp_path / "new.md")
    )
    event.is_directory = False
    event.dest_path = str(tmp_path / "new.md")
    handler.on_moved(event)

    assert called.wait(timeout=1.0), "Callback was not called for on_moved"


# ---------------------------------------------------------------------------
# Test 8: stop() cancels pending timer
# ---------------------------------------------------------------------------
def test_handler_stop_cancels_timer() -> None:
    """Calling stop() immediately after an event should cancel the pending callback."""
    called = threading.Event()

    def cb() -> None:
        called.set()

    handler = _DebouncedHandler(callback=cb, debounce_ms=500)
    event = FileCreatedEvent(str(Path("/tmp/test.md")))
    event.is_directory = False
    handler.on_created(event)

    # Immediately stop before the 500ms debounce fires
    handler.stop()

    # Wait long enough to be sure the timer would have fired
    time.sleep(0.2)
    assert not called.is_set(), (
        "Callback should NOT have been called after stop() cancelled the timer"
    )


# ---------------------------------------------------------------------------
# Test 9: Callback exception is caught, not propagated
# ---------------------------------------------------------------------------
def test_handler_callback_exception_caught(tmp_path: Path) -> None:
    """If the callback raises, the exception should be caught and logged, not propagated."""
    called = threading.Event()

    def cb() -> None:
        called.set()
        raise RuntimeError("Simulated callback failure")

    handler = _DebouncedHandler(callback=cb, debounce_ms=50)
    event = FileCreatedEvent(str(tmp_path / "error.md"))
    event.is_directory = False

    # This must not raise
    handler.on_created(event)

    # Wait for callback to execute
    assert called.wait(timeout=1.0), "Callback was not called at all"


# ---------------------------------------------------------------------------
# Test 10: start_watcher creates a running Observer
# ---------------------------------------------------------------------------
def test_start_watcher_returns_observer(tmp_path: Path) -> None:
    """start_watcher returns a running Observer that invokes the callback on .md changes."""
    called = threading.Event()

    def cb() -> None:
        called.set()

    watch_dir = tmp_path / "watched"
    watch_dir.mkdir()

    observer = start_watcher(watch_dir, callback=cb, debounce_ms=100)

    try:
        # Observer should be alive
        assert observer.is_alive(), "Observer should be running after start_watcher"

        # Create a .md file inside the watched directory
        note = watch_dir / "hello.md"
        note.write_text("# Hello", encoding="utf-8")

        # Wait for watcher to detect the file + debounce
        assert called.wait(timeout=3.0), (
            "Callback should have been called after creating .md file in watched dir"
        )
    finally:
        observer.stop()
        observer.join(timeout=2.0)
