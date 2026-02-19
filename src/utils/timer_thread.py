"""
timer_thread.py — Non-blocking Background Timer
================================================
Manages a single active timer in a daemon thread.
When the timer finishes it plays a proper alarm sound and speaks the
completion message.

Public API:
    start_timer(seconds)   — start (or replace) a timer for N seconds
    cancel_timer()         — cancel the running timer
    get_remaining()        — returns seconds remaining (float) or None
    is_running()           — True if a timer is active
"""

import threading
import time
import math

from utils.sounds import play_alarm_sound
from core.tts import speak

# ── Internal state ─────────────────────────────────────────────────────────────
_timer_thread: threading.Thread | None = None
_cancel_event  = threading.Event()
_start_time: float | None = None
_duration: float | None   = None
_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# TTS + Beep helpers (all offline)
# ─────────────────────────────────────────────────────────────────────────────



# ─────────────────────────────────────────────────────────────────────────────
# Timer worker
# ─────────────────────────────────────────────────────────────────────────────

def _timer_worker(seconds: float, cancel_ev: threading.Event):
    global _start_time, _duration

    with _lock:
        _start_time = time.monotonic()
        _duration   = seconds

    print(f"⏱️  Timer started: {seconds:.0f}s")

    # Wait for either the duration or a cancel signal
    cancelled = cancel_ev.wait(timeout=seconds)

    if cancelled:
        print("🚫 Timer cancelled.")
        with _lock:
            _start_time = None
            _duration   = None
        return

    # Timer finished naturally
    print("\n" + "🔔 " * 10)
    print("⏰  टाइमर खत्म हो गया!")
    print("🔔 " * 10 + "\n")

    play_alarm_sound(repeats=3)
    speak("टाइमर खत्म हो गया।")

    with _lock:
        _start_time = None
        _duration   = None


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def start_timer(seconds: float):
    """
    Start a new timer for `seconds` seconds.
    If a timer is already running it is cancelled first.

    Args:
        seconds: Duration in seconds (float).
    """
    global _timer_thread, _cancel_event

    # Cancel any existing timer
    if _timer_thread and _timer_thread.is_alive():
        _cancel_event.set()
        _timer_thread.join(timeout=1.0)

    # Fresh cancel event for the new timer
    _cancel_event = threading.Event()

    _timer_thread = threading.Thread(
        target=_timer_worker,
        args=(seconds, _cancel_event),
        daemon=True,
        name="TimerWorker",
    )
    _timer_thread.start()


def cancel_timer() -> bool:
    """
    Cancel the running timer.
    Returns True if a timer was running, False if there was nothing to cancel.
    """
    global _timer_thread, _cancel_event

    if _timer_thread and _timer_thread.is_alive():
        _cancel_event.set()
        _timer_thread.join(timeout=1.0)
        with _lock:
            _start_time_val = _start_time   # will already be None after join
        print("🚫 Timer cancelled by user.")
        return True
    return False


def get_remaining() -> float | None:
    """
    Return remaining seconds (float) or None if no timer is active.
    """
    with _lock:
        if _start_time is None or _duration is None:
            return None
        elapsed = time.monotonic() - _start_time
        remaining = _duration - elapsed
        return max(0.0, remaining)


def is_running() -> bool:
    """True if a timer is currently active."""
    return _timer_thread is not None and _timer_thread.is_alive()


def format_remaining() -> str:
    """
    Return a human-readable Hindi string of remaining time.
    e.g. "7 minute 30 second baaki hai"
    """
    rem = get_remaining()
    if rem is None:
        return "कोई टाइमर नहीं चल रहा।"

    total = int(math.ceil(rem))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if hours:
        parts.append(f"{hours} घंटे")
    if minutes:
        parts.append(f"{minutes} मिनट")
    if seconds or not parts:
        parts.append(f"{seconds} सेकंड")

    return " ".join(parts) + " बाकी है।"
