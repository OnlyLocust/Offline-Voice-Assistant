"""
core/recognizer.py — Vosk Speech Recognizer + Audio Callback
=============================================================
Loads the Vosk model once at import time and exposes:
    - `recognizer`  : KaldiRecognizer instance (pre-loaded)
    - `callback()`  : sounddevice RawInputStream callback

The callback drives the state machine by calling handlers from core/handlers.py.
"""

import json
import numpy as np
from vosk import Model, KaldiRecognizer

from utils.constants  import (
    MODEL_PATH, SAMPLE_RATE, WAKE_WORD,
    ASR_CONFIDENCE_THRESHOLD, ASR_MIN_WORD_LENGTH,
)
from utils.get_greet  import get_greeting
from core.state       import State
from core.tts         import speak
from core.handlers    import handle_active_command, handle_pin_input, handle_notice_recording

# ── Audio buffer — collects raw int16 PCM from the mic while in AWAITING_PIN ──
# voice_auth.verify_voice_from_audio() reads this so it does NOT need to call
# sd.rec() (which would conflict with the open RawInputStream in main.py).
_pin_audio_buffer: list[bytes] = []


def get_pin_audio() -> np.ndarray:
    """Return all PCM bytes recorded during the last PIN utterance as int16 array."""
    if not _pin_audio_buffer:
        return np.array([], dtype=np.int16)
    raw = b"".join(_pin_audio_buffer)
    return np.frombuffer(raw, dtype=np.int16)


def clear_pin_audio() -> None:
    _pin_audio_buffer.clear()


# ── Load model once (expensive — do at startup, not per-call) ─────────────────
print("⏳ Loading Vosk model...")
_model     = Model(MODEL_PATH)
recognizer = KaldiRecognizer(_model, SAMPLE_RATE)
print("✅ Vosk model loaded.\n")


# ─────────────────────────────────────────────────────────────────────────────
# ASR quality filter
# ─────────────────────────────────────────────────────────────────────────────

def _is_meaningful(result: dict, text: str, check_word_length: bool = True) -> bool:
    """
    Return True only when the utterance clears both quality gates.

    Gate 1 — Confidence
        Vosk's final JSON may contain a ``"result"`` list where each entry
        has a ``"conf"`` field (0.0 – 1.0).  If present, the per-word
        confidences are averaged and compared against
        ``ASR_CONFIDENCE_THRESHOLD``.  If the key is absent (older model
        builds), this gate is skipped so the assistant still works.

    Gate 2 — Minimum word length
        Any utterance whose *every* token is shorter than
        ``ASR_MIN_WORD_LENGTH`` Unicode characters is silently dropped.
        This catches Vosk hallucinations like "अ", "आ", "ई" that arise
        from breathing, background noise, or clipped audio.
        Pass ``check_word_length=False`` to bypass this gate (PIN mode).

    Args:
        result:           Parsed Vosk final-result dict.
        text:             Already-stripped transcript string.
        check_word_length: When False, Gate 2 is skipped (used in PIN mode
                          where tokens like "एक"/"दो" are legitimately short).

    Returns:
        True  → process the utterance
        False → silently discard it
    """
    # ── Gate 1: per-word confidence ───────────────────────────────────────────
    word_results = result.get("result", [])   # list[{"conf": float, ...}]
    if word_results and ASR_CONFIDENCE_THRESHOLD > 0.0:
        avg_conf = sum(w.get("conf", 1.0) for w in word_results) / len(word_results)
        if avg_conf < ASR_CONFIDENCE_THRESHOLD:
            print(f"🔇 Low confidence ({avg_conf:.2f} < {ASR_CONFIDENCE_THRESHOLD}) — ignored: '{text}'")
            return False

    # ── Gate 2: minimum word length ───────────────────────────────────────────
    if check_word_length and ASR_MIN_WORD_LENGTH > 1:
        tokens = text.split()
        if tokens and all(len(tok) < ASR_MIN_WORD_LENGTH for tok in tokens):
            print(f"🔇 Too short (all words < {ASR_MIN_WORD_LENGTH} chars) — ignored: '{text}'")
            return False

    return True


# ── Mutable state (shared with callback via closure) ──────────────────────────
_state: State = State.SLEEPING


def get_state() -> State:
    return _state


def set_state(s: State) -> None:
    global _state
    _state = s


# ─────────────────────────────────────────────────────────────────────────────
# Audio callback — called by sounddevice on every audio block
# ─────────────────────────────────────────────────────────────────────────────

def callback(indata, frames, time_info, status) -> None:
    """
    sounddevice RawInputStream callback.
    Feeds audio to Vosk; on a complete utterance, routes to the state machine.
    """
    global _state

    # Accumulate raw audio while waiting for PIN (for voice verification)
    if _state == State.AWAITING_PIN:
        _pin_audio_buffer.append(bytes(indata))

    if not recognizer.AcceptWaveform(bytes(indata)):
        return   # partial result — wait for more audio

    result = json.loads(recognizer.Result())
    text   = result.get("text", "").strip()

    if not text:
        return

    # ── ASR quality gates — drop noise / hallucinations before state routing ──
    # In AWAITING_PIN, disable the word-length gate because PIN tokens like
    # "एक", "दो" (2 chars) would otherwise be incorrectly filtered out.
    skip_len_check = (_state == State.AWAITING_PIN)
    if not _is_meaningful(result, text, check_word_length=not skip_len_check):
        return

    # ── SLEEPING: only listen for wake word ───────────────────────────────────
    if _state == State.SLEEPING:
        print(f"🛌 Sleeping | Heard: {text}")
        if WAKE_WORD in text:
            greeting = get_greeting()
            msg      = f"{greeting}! मैं आपकी कैसे मदद कर सकता हूँ?"
            print("🔥 Wake word detected! Assistant is ACTIVE\n")
            _state = State.ACTIVE
            speak(msg)
        return

    # ── AWAITING_PIN: collect PIN digits ──────────────────────────────────────
    if _state == State.AWAITING_PIN:
        print(f"🔐 PIN mode | Heard: {text}")
        audio_arr = get_pin_audio()
        clear_pin_audio()
        _state = handle_pin_input(text, audio_arr)
        return

    # ── RECORDING_NOTICE: any speech triggers the notice recording ────────────
    if _state == State.RECORDING_NOTICE:
        print(f"📢 Notice mode | Heard: {text}")
        # Raw audio is captured inside handle_notice_recording via sounddevice.
        # Vosk text is not used here — we just need any utterance to trigger it.
        _state = handle_notice_recording(text)
        return

    # ── ACTIVE: route to command handlers ─────────────────────────────────────
    print(f"👂 Command mode | Heard: {text}")
    _state = handle_active_command(text)
