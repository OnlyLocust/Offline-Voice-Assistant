"""
alarm_thread.py — Background Alarm Checker
============================================
Runs a daemon thread that checks every second whether any scheduled
alarm time matches the current HH:MM. When matched, it plays a proper
alarm sound and announces it via TTS.

Public API:
    start_alarm_thread()  — call once at startup
    set_alarm(t)          — schedule alarm at "HH:MM"
    cancel_alarm()        — cancel the current alarm
    get_alarm()           — return current alarm time string or None
"""

import threading
import time
from datetime import datetime

from utils.sounds import play_alarm_sound
from core.tts import speak

# ── Internal state ─────────────────────────────────────────────────────────────
_alarm_time: str | None = None
_alarm_running: bool    = False
_lock = threading.Lock()


# ── Alarm checker loop ─────────────────────────────────────────────────────────


def _alarm_checker():
    global _alarm_time, _alarm_running

    while _alarm_running:
        with _lock:
            target = _alarm_time

        if target:
            now = datetime.now().strftime("%H:%M")
            if now == target:
                msg = f"⏰ अलार्म बज रहा है! समय हो गया {target}"
                print("\n" + "=" * 45)
                print(msg)
                print("=" * 45 + "\n")
                # Play proper alarm sound, then speak the TTS announcement
                play_alarm_sound(repeats=4)
                speak("अलार्म बज रहा है। समय हो गया।")

                with _lock:
                    _alarm_time = None   # auto-clear after ringing

        time.sleep(1)


# ── Public API ─────────────────────────────────────────────────────────────────

def start_alarm_thread():
    """Start the background alarm daemon. Call once at program startup."""
    global _alarm_running
    _alarm_running = True
    t = threading.Thread(target=_alarm_checker, daemon=True, name="AlarmChecker")
    t.start()
    print("🕐 Alarm thread started.")


def set_alarm(t: str):
    """
    Schedule an alarm.

    Args:
        t: Time string in "HH:MM" 24-hour format.
    """
    global _alarm_time
    with _lock:
        _alarm_time = t
    print(f"✅ अलार्म सेट हो गया: {t}")
    speak(f"अलार्म {t} बजे के लिए सेट हो गया।")


def cancel_alarm():
    """Cancel the currently scheduled alarm."""
    global _alarm_time
    with _lock:
        _alarm_time = None
    print("🚫 अलार्म रद्द कर दिया गया।")
    speak("अलार्म रद्द कर दिया गया।")


def get_alarm() -> str | None:
    """Return the currently scheduled alarm time, or None."""
    with _lock:
        return _alarm_time