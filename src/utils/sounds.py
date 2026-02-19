"""
utils/sounds.py — Offline Audio Alert Sounds
=============================================
Provides two synthesised sounds built entirely from numpy + sounddevice
so the assistant never needs an external audio file or system utility.

Public API
----------
    play_alarm_sound()        — Loud, urgent repeating alarm (for alarms/timers)
    play_notification_sound() — Short, pleasant chime (for notice reminders)

Both functions are blocking by default (they return after playback finishes).
Use threading.Thread(..., daemon=True).start() if non-blocking playback is needed.
"""

import numpy as np
import sounddevice as sd

_SR = 44100   # sample rate for all generated audio


# ─────────────────────────────────────────────────────────────────────────────
# Low-level helpers
# ─────────────────────────────────────────────────────────────────────────────

def _tone(freq: float, duration: float, amplitude: float = 0.6) -> np.ndarray:
    """Return a sine-wave tone as a float32 array."""
    t = np.linspace(0, duration, int(_SR * duration), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _silence(duration: float) -> np.ndarray:
    """Return a block of silence as a float32 array."""
    return np.zeros(int(_SR * duration), dtype=np.float32)


def _envelope(audio: np.ndarray, attack: float = 0.01, release: float = 0.05) -> np.ndarray:
    """Apply a simple linear attack/release envelope to avoid click artefacts."""
    audio = audio.copy()
    a_samples = int(_SR * attack)
    r_samples = int(_SR * release)
    if a_samples > 0:
        audio[:a_samples] *= np.linspace(0, 1, a_samples)
    if r_samples > 0:
        audio[-r_samples:] *= np.linspace(1, 0, r_samples)
    return audio


def _play(audio: np.ndarray) -> None:
    """Play a float32 numpy array through the default output device."""
    try:
        sd.play(audio, samplerate=_SR)
        sd.wait()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Public: Alarm sound  (used by alarm_thread + timer_thread)
# ─────────────────────────────────────────────────────────────────────────────

def play_alarm_sound(repeats: int = 3) -> None:
    """
    Play an urgent alarm sound made of repeating two-tone klaxon bursts.

    Each burst:  high note → low note → short silence  (≈ 0.9 s)
    `repeats` controls how many burst groups play (default 3 → ≈ 2.7 s total).
    """
    try:
        burst_parts = []
        for _ in range(repeats):
            # High-frequency burst
            hi = _envelope(_tone(1050, 0.25, amplitude=0.75))
            # Low-frequency burst
            lo = _envelope(_tone(700,  0.25, amplitude=0.75))
            # Short gap
            gap = _silence(0.08)
            # Another hi burst for urgency
            hi2 = _envelope(_tone(1050, 0.20, amplitude=0.75))
            gap2 = _silence(0.12)
            burst_parts.extend([hi, lo, gap, hi2, gap2])

        audio = np.concatenate(burst_parts)
        _play(audio)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Public: Notification chime  (used by notice_thread)
# ─────────────────────────────────────────────────────────────────────────────

def play_notification_sound() -> None:
    """
    Play a pleasant three-note ascending chime to signal a notice/reminder.

    Notes:  C5 → E5 → G5  (a simple major-chord arpeggio)
    Total duration ≈ 0.9 s.
    """
    try:
        # Major-chord arpeggio: C5(523 Hz) → E5(659 Hz) → G5(784 Hz)
        c5  = _envelope(_tone(523, 0.22, amplitude=0.55))
        e5  = _envelope(_tone(659, 0.22, amplitude=0.55))
        g5  = _envelope(_tone(784, 0.35, amplitude=0.55))
        gap = _silence(0.05)

        audio = np.concatenate([c5, gap, e5, gap, g5])
        _play(audio)
    except Exception:
        pass
