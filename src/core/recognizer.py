"""
core/recognizer.py — Vosk Speech Recognizer + Audio Callback
=============================================================
Loads the Vosk model once at import time and exposes:
    - `recognizer`  : KaldiRecognizer instance (pre-loaded)
    - `callback()`  : sounddevice RawInputStream callback

The callback drives the state machine by calling handlers from core/handlers.py.
"""

import json
from vosk import Model, KaldiRecognizer

from utils.constants  import MODEL_PATH, SAMPLE_RATE, WAKE_WORD
from utils.get_greet  import get_greeting
from core.state       import State
from core.tts         import speak
from core.handlers    import handle_active_command, handle_pin_input, handle_notice_recording


# ── Load model once (expensive — do at startup, not per-call) ─────────────────
print("⏳ Loading Vosk model...")
_model     = Model(MODEL_PATH)
recognizer = KaldiRecognizer(_model, SAMPLE_RATE)
print("✅ Vosk model loaded.\n")


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

    if not recognizer.AcceptWaveform(bytes(indata)):
        return   # partial result — wait for more audio

    result = json.loads(recognizer.Result())
    text   = result.get("text", "").strip()

    if not text:
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
        _state = handle_pin_input(text)
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
