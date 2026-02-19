"""
utils/notice_thread.py — Voice Notice Recorder & Scheduler
============================================================
Records a short voice message, stores it as a temp WAV file,
schedules playback at a future time, plays it, then deletes the file.

All offline. No internet. No permanent storage.

Public API:
    record_notice(duration)          → str | None   (temp file path)
    schedule_notice(filepath, delay) → None          (delay in seconds)
    cancel_notice()                  → bool
    get_notice_status()              → dict
"""

import os
import time
import wave
import tempfile
import threading
import platform
import subprocess
import numpy as np
import sounddevice as sd

from utils.constants import SAMPLE_RATE
from utils.sounds import play_notification_sound

# ── Internal state ─────────────────────────────────────────────────────────────
_notice_thread: threading.Thread | None = None
_cancel_event   = threading.Event()
_lock           = threading.Lock()

_notice_file:    str | None   = None   # path to temp WAV
_notice_eta:     float | None = None   # monotonic time when notice fires
_notice_label:   str          = ""     # human-readable "10 मिनट बाद"


# ─────────────────────────────────────────────────────────────────────────────
# Audio helpers
# ─────────────────────────────────────────────────────────────────────────────

def _speak_tts(text: str) -> None:
    """Non-blocking offline TTS."""
    try:
        if platform.system() == "Windows":
            safe = text.replace('"', '\\"')
            subprocess.Popen(
                ["powershell", "-Command",
                 f'Add-Type -AssemblyName System.Speech; '
                 f'(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{safe}")'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["espeak-ng", "-v", "hi", text],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass


def record_notice(duration: float = 7.0) -> str | None:
    """
    Record `duration` seconds from the microphone and save to a temp WAV file.

    Returns the file path on success, None on failure.
    The caller is responsible for deleting the file after use.
    """
    try:
        print(f"🎙️  Recording notice ({duration:.0f}s)...")
        audio = sd.rec(
            int(duration * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
        )
        sd.wait()

        # Write to a temp file
        tmp = tempfile.NamedTemporaryFile(
            suffix=".wav", delete=False, prefix="notice_"
        )
        with wave.open(tmp.name, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)          # int16 = 2 bytes
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.tobytes())

        print(f"✅ Notice recorded → {tmp.name}")
        return tmp.name

    except Exception as e:
        print(f"❌ Notice recording failed: {e}")
        return None


def _play_wav(filepath: str) -> None:
    """Play a WAV file using sounddevice (offline, no external player needed)."""
    try:
        with wave.open(filepath, "r") as wf:
            frames = wf.readframes(wf.getnframes())
            audio  = np.frombuffer(frames, dtype=np.int16)
            rate   = wf.getframerate()

        sd.play(audio.astype(np.float32) / 32768.0, samplerate=rate)
        sd.wait()
    except Exception as e:
        print(f"❌ Playback failed: {e}")


def _delete_file(filepath: str) -> None:
    """Silently delete a file."""
    try:
        os.remove(filepath)
        print(f"🗑️  Notice file deleted: {filepath}")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Background scheduler worker
# ─────────────────────────────────────────────────────────────────────────────

def _notice_worker(filepath: str, delay: float, cancel_ev: threading.Event) -> None:
    global _notice_file, _notice_eta, _notice_label

    print(f"📅 Notice scheduled in {delay:.0f}s → {filepath}")

    cancelled = cancel_ev.wait(timeout=delay)

    with _lock:
        _notice_eta  = None
        _notice_file = None
        _notice_label = ""

    if cancelled:
        print("🚫 Notice cancelled.")
        _delete_file(filepath)
        return

    # Fire!
    print("\n" + "📢 " * 10)
    print("🔔  नोटिस का समय आ गया!")
    print("📢 " * 10 + "\n")

    # Play notification chime to alert the user, then announce + play recording
    play_notification_sound()
    time.sleep(0.3)          # brief gap between chime and TTS
    _speak_tts("नोटिस सुनिए।")
    time.sleep(0.9)          # brief pause before playback
    _play_wav(filepath)
    _delete_file(filepath)   # delete immediately after playback


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def schedule_notice(filepath: str, delay: float, label: str = "") -> None:
    """
    Schedule a recorded notice to play after `delay` seconds.
    If a notice is already pending, it is cancelled first.

    Args:
        filepath : Path to the recorded WAV file.
        delay    : Seconds from now until playback.
        label    : Human-readable label e.g. "10 मिनट बाद"
    """
    global _notice_thread, _cancel_event, _notice_file, _notice_eta, _notice_label

    # Cancel any existing notice
    if _notice_thread and _notice_thread.is_alive():
        _cancel_event.set()
        _notice_thread.join(timeout=1.0)

    _cancel_event = threading.Event()

    with _lock:
        _notice_file  = filepath
        _notice_eta   = time.monotonic() + delay
        _notice_label = label

    _notice_thread = threading.Thread(
        target=_notice_worker,
        args=(filepath, delay, _cancel_event),
        daemon=True,
        name="NoticeWorker",
    )
    _notice_thread.start()


def cancel_notice() -> bool:
    """
    Cancel the pending notice.
    Returns True if a notice was running, False if nothing to cancel.
    """
    global _notice_thread, _cancel_event

    if _notice_thread and _notice_thread.is_alive():
        _cancel_event.set()
        _notice_thread.join(timeout=1.0)
        return True
    return False


def get_notice_status() -> dict:
    """
    Return info about the pending notice.

    Returns:
        {
          "active":     bool,
          "remaining":  float | None,   # seconds remaining
          "label":      str,
        }
    """
    with _lock:
        eta   = _notice_eta
        label = _notice_label

    if eta is None or (_notice_thread and not _notice_thread.is_alive()):
        return {"active": False, "remaining": None, "label": ""}

    remaining = max(0.0, eta - time.monotonic())
    return {"active": True, "remaining": remaining, "label": label}


def format_notice_remaining() -> str:
    """Return a Hindi string like '7 मिनट 30 सेकंड बाकी है।'"""
    import math
    status = get_notice_status()
    if not status["active"]:
        return "कोई नोटिस नहीं है।"

    total   = int(math.ceil(status["remaining"]))
    hours, r = divmod(total, 3600)
    mins, secs = divmod(r, 60)

    parts = []
    if hours:  parts.append(f"{hours} घंटे")
    if mins:   parts.append(f"{mins} मिनट")
    if secs or not parts: parts.append(f"{secs} सेकंड")

    return " ".join(parts) + " बाद नोटिस बजेगा।"
