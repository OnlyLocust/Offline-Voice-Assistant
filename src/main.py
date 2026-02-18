"""
main.py — Offline Hindi Voice Assistant (Secure Alarm + Timer)
==============================================================
State machine:
  SLEEPING     → hear WAKE_WORD  → ACTIVE
  ACTIVE       → hear alarm intent → AWAITING_PIN
  AWAITING_PIN → hear PIN → voice auth → set alarm → ACTIVE
  ACTIVE       → hear EXIT_WORD  → SLEEPING

Features:
  • Secure alarm setting (PIN + voice auth, fully offline)
  • Non-blocking background timer (start / cancel / status)
  • Time query, alarm cancel/status
  • TTS via PowerShell (Windows) / espeak-ng (Raspberry Pi)
"""

import sounddevice as sd
import json
import time
import subprocess
import platform
from vosk import Model, KaldiRecognizer
from datetime import datetime
from enum import Enum, auto

from utils.constants import (
    MODEL_PATH, SAMPLE_RATE, WAKE_WORD, EXIT_WORD,
    PIN_PROMPT_TIMEOUT,
)
from utils.get_greet import get_greeting
from utils.alarm_thread import start_alarm_thread, get_alarm, cancel_alarm
from utils.timer_thread import (
    start_timer, cancel_timer, is_running, format_remaining,
)
from utils.auth import authenticate_user
from intents.time_intent import check_time_query
from intents.remainder_intent import extract_alarm_intent
from intents.timer_intent import extract_timer_intent
from intents.math_intent import extract_math_intent


# ─────────────────────────────────────────────────────────────────────────────
# State machine
# ─────────────────────────────────────────────────────────────────────────────

class State(Enum):
    SLEEPING      = auto()   # waiting for wake word
    ACTIVE        = auto()   # listening for commands
    AWAITING_PIN  = auto()   # waiting for user to speak PIN


# ─────────────────────────────────────────────────────────────────────────────
# TTS helper
# ─────────────────────────────────────────────────────────────────────────────

def speak(text: str, blocking: bool = True):
    """Speak text using platform-appropriate TTS."""
    print(f"🔊 {text}")
    try:
        if platform.system() == "Windows":
            safe = text.replace('"', '\\"')
            cmd = [
                "powershell", "-Command",
                f'Add-Type -AssemblyName System.Speech; '
                f'(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{safe}")'
            ]
            if blocking:
                subprocess.run(cmd, check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(cmd,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # Raspberry Pi / Linux
            cmd = ["espeak-ng", "-v", "hi", text]
            if blocking:
                subprocess.run(cmd, check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(cmd,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Global assistant state
# ─────────────────────────────────────────────────────────────────────────────

state: State      = State.SLEEPING
pin_prompt_time: float = 0.0   # when we entered AWAITING_PIN


# ─────────────────────────────────────────────────────────────────────────────
# Command handlers
# ─────────────────────────────────────────────────────────────────────────────

def handle_timer_command(text: str) -> bool:
    """
    Check if text is a timer command and handle it.
    Returns True if it was a timer command (so caller can skip other checks).
    """
    intent = extract_timer_intent(text)
    if intent is None:
        return False

    action = intent["action"]

    if action == "start":
        seconds = intent["seconds"]
        label   = intent["label"]
        start_timer(seconds)
        speak(f"{label} का टाइमर शुरू कर रहा हूँ।")
        print(f"⏱️  Timer → {seconds}s ({label})")

    elif action == "cancel":
        if cancel_timer():
            speak("टाइमर रद्द कर दिया।")
        else:
            speak("कोई टाइमर नहीं चल रहा।")

    elif action == "status":
        if is_running():
            msg = format_remaining()
            speak(msg)
        else:
            speak("कोई टाइमर नहीं चल रहा।")

    elif action == "unclear":
        speak("समय समझ नहीं आया। कृपया दोबारा बोलें।")
        speak("उदाहरण: दस मिनट का टाइमर लगाओ।")

    return True


def handle_math_command(text: str) -> bool:
    """
    Check if text is a math command and handle it.
    Returns True if it was a math command (so caller can skip other checks).
    """
    intent = extract_math_intent(text)
    if intent is None:
        return False

    answer = intent["answer"]
    eq     = intent["equation"]
    print(f"🧮 {eq}")
    speak(answer)
    return True


def handle_active_command(text: str):
    """
    Process a command while in ACTIVE state.
    Returns the next State.
    """
    global state, pin_prompt_time

    # ── EXIT ──────────────────────────────────────────────────────────────────
    if EXIT_WORD in text:
        speak("ठीक है, मैं सो रहा हूँ। धन्यवाद!")
        print("🙏 Going back to sleep...\n")
        return State.SLEEPING

    # ── TIME QUERY ────────────────────────────────────────────────────────────
    check_time_query(text)

    # ── TIMER COMMANDS (checked before alarm to avoid keyword clash) ──────────
    if handle_timer_command(text):
        return State.ACTIVE

    # ── MATH CALCULATOR ─────────────────────────────────────────────────────────
    if handle_math_command(text):
        return State.ACTIVE

    # ── ALARM CANCEL ──────────────────────────────────────────────────────────
    if ("अलार्म" in text or "alarm" in text.lower()) and (
        "रद्द" in text or "बंद" in text or "cancel" in text.lower()
    ):
        current = get_alarm()
        if current:
            cancel_alarm()
        else:
            speak("कोई अलार्म सेट नहीं है।")
        return State.ACTIVE

    # ── ALARM STATUS ──────────────────────────────────────────────────────────
    if ("अलार्म" in text or "alarm" in text.lower()) and (
        "कब" in text or "क्या" in text or "बताओ" in text or "status" in text.lower()
    ):
        current = get_alarm()
        if current:
            speak(f"अलार्म {current} बजे के लिए सेट है।")
        else:
            speak("कोई अलार्म सेट नहीं है।")
        return State.ACTIVE

    # ── ALARM SET (requires auth) ─────────────────────────────────────────────
    alarm_keywords = ["अलार्म", "जगाना", "उठाना", "याद"]
    if any(kw in text for kw in alarm_keywords):
        assistant_state["pending_alarm_text"] = text
        speak("अलार्म सेट करने के लिए पासवर्ड बोलिए। कृपया अपना पिन बोलें।")
        print("🔐 Alarm intent detected → requesting PIN...")
        pin_prompt_time = time.time()
        return State.AWAITING_PIN

    return State.ACTIVE


def handle_pin_input(text: str):
    """
    Process spoken text while in AWAITING_PIN state.
    Returns the next State.
    """
    global state

    # ── Timeout check ─────────────────────────────────────────────────────────
    if time.time() - pin_prompt_time > PIN_PROMPT_TIMEOUT:
        speak("समय समाप्त। अलार्म सेट नहीं हुआ।")
        print("⏱️  PIN timeout. Returning to ACTIVE.\n")
        return State.ACTIVE

    # ── EXIT escape hatch ─────────────────────────────────────────────────────
    if EXIT_WORD in text:
        speak("ठीक है, अलार्म रद्द।")
        return State.ACTIVE

    # ── Run full authentication ───────────────────────────────────────────────
    print(f"🔑 PIN attempt: '{text}'")
    auth = authenticate_user(spoken_pin=text, check_voice=True)

    print(f"   PIN ok={auth['pin_ok']}  Voice ok={auth['voice_ok']}")
    print(f"   {auth['reason']}")

    if auth["authorized"]:
        speak("प्रमाणीकरण सफल! अलार्म सेट हो रहा है।")
        # Parse and set the alarm from the original command
        pending_text = assistant_state.get("pending_alarm_text", "")
        result = extract_alarm_intent(pending_text)
        if result is None:
            speak("अलार्म का समय समझ नहीं आया। कृपया दोबारा बोलें।")
        assistant_state["pending_alarm_text"] = ""
        return State.ACTIVE
    else:
        speak(auth["reason"])
        speak("अलार्म सेट नहीं हुआ।")
        assistant_state["pending_alarm_text"] = ""
        return State.ACTIVE


# Shared mutable assistant state (avoids globals in callback)
assistant_state = {
    "pending_alarm_text": "",
}


# ─────────────────────────────────────────────────────────────────────────────
# Vosk audio callback
# ─────────────────────────────────────────────────────────────────────────────

model      = Model(MODEL_PATH)
recognizer = KaldiRecognizer(model, SAMPLE_RATE)


def callback(indata, frames, time_info, status):
    global state

    data = bytes(indata)

    if not recognizer.AcceptWaveform(data):
        return

    result = json.loads(recognizer.Result())
    text   = result.get("text", "").strip()

    if not text:
        return

    # ── SLEEPING ──────────────────────────────────────────────────────────────
    if state == State.SLEEPING:
        print(f"🛌 Sleeping | Heard: {text}")
        if WAKE_WORD in text:
            greeting = get_greeting()
            msg = f"{greeting}! मैं आपकी कैसे मदद कर सकता हूँ?"
            print("� Wake word detected! Assistant is ACTIVE\n")
            state = State.ACTIVE
            speak(msg)
        return

    # ── AWAITING_PIN ──────────────────────────────────────────────────────────
    if state == State.AWAITING_PIN:
        print(f"🔐 PIN mode | Heard: {text}")
        state = handle_pin_input(text)
        return

    # ── ACTIVE ────────────────────────────────────────────────────────────────
    print(f"👂 Command mode | Heard: {text}")
    state = handle_active_command(text)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("🤖 Hindi Voice Assistant — Alarm + Timer + Calculator")
    print("=" * 60)
    print(f"   Wake word  : '{WAKE_WORD}'")
    print(f"   Exit word  : '{EXIT_WORD}'")
    print(f"   Time       : {datetime.now().strftime('%H:%M:%S')}")
    print("─" * 60)
    print("   Timer cmds : 'दस मिनट का टाइमर लगाओ'")
    print("                'टाइमर बंद करो' / 'टाइमर कितना बाकी है'")
    print("   Math cmds  : 'पांच प्लस सात' / 'दस माइनस तीन'")
    print("                'छह गुणा चार' / 'बीस भाग पांच'")
    print("   Alarm cmds : 'कल सात बजे जगाना' (PIN + voice required)")
    print("=" * 60)
    print()

    # Start alarm background thread
    start_alarm_thread()

    print("🎧 Listening for wake word...\n")

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=8000,
        dtype="int16",
        channels=1,
        callback=callback,
    ):
        while True:
            time.sleep(0.1)
