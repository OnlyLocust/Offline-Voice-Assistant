"""
core/handlers.py — Command Handlers (Active, PIN & Notice States)
=================================================================
All business logic for processing recognized speech lives here.
main.py stays thin — it only wires audio → callback → handlers.

Exported functions:
    handle_active_command(text)    → State
    handle_pin_input(text)         → State
    handle_notice_recording(text)  → State
"""

import time
import numpy as np

from core.state import State
from core.tts   import speak

from utils.constants       import EXIT_WORD, PIN_PROMPT_TIMEOUT
from utils.alarm_thread    import get_alarm, cancel_alarm
from utils.timer_thread    import start_timer, cancel_timer, is_running, format_remaining
from utils.auth            import authenticate_user

from intents.time_intent      import check_time_query, check_date_query
from intents.remainder_intent import extract_alarm_intent
from intents.timer_intent     import extract_timer_intent
from intents.math_intent      import extract_math_intent
from intents.notice_intent    import extract_notice_intent
from intents.volume_intent    import extract_volume_intent

from utils.notice_thread import (
    record_notice, schedule_notice,
    cancel_notice, get_notice_status, format_notice_remaining,
)
from utils.volume_control import (
    get_volume, set_volume, increase_volume, decrease_volume,
    mute, unmute, is_muted,
)


# ── Shared state (set by main, read here) ─────────────────────────────────────
# Using a dict so handlers can mutate it without needing 'global' everywhere.
assistant_ctx: dict = {
    "pending_alarm_text":  "",
    "pin_prompt_time":     0.0,
    "pending_notice_delay": None,   # float seconds until notice fires
    "pending_notice_label": "",     # human-readable label
}


# ─────────────────────────────────────────────────────────────────────────────
# Timer handler
# ─────────────────────────────────────────────────────────────────────────────

def _handle_timer(text: str) -> bool:
    """
    Parse and execute a timer command.
    Returns True if text was a timer command (caller should skip further checks).
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
        speak(format_remaining() if is_running() else "कोई टाइमर नहीं चल रहा।")

    elif action == "unclear":
        speak("समय समझ नहीं आया। कृपया दोबारा बोलें।")
        speak("उदाहरण: दस मिनट का टाइमर लगाओ।")

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Math handler
# ─────────────────────────────────────────────────────────────────────────────

def _handle_math(text: str) -> bool:
    """
    Parse and execute a math calculation command.
    Returns True if text was a math command.
    """
    intent = extract_math_intent(text)
    if intent is None:
        return False

    print(f"🧮 {intent['equation']}")
    speak(intent["answer"])
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Alarm handlers
# ─────────────────────────────────────────────────────────────────────────────

def _handle_alarm_cancel(text: str) -> bool:
    """Handle 'alarm cancel' commands. Returns True if matched."""
    if not ("अलार्म" in text or "alarm" in text.lower()):
        return False
    if not ("रद्द" in text or "बंद" in text or "cancel" in text.lower()):
        return False

    if get_alarm():
        cancel_alarm()
    else:
        speak("कोई अलार्म सेट नहीं है।")
    return True


def _handle_alarm_status(text: str) -> bool:
    """Handle 'alarm status' commands. Returns True if matched."""
    if not ("अलार्म" in text or "alarm" in text.lower()):
        return False
    if not ("कब" in text or "क्या" in text or "बताओ" in text or "status" in text.lower()):
        return False

    current = get_alarm()
    speak(f"अलार्म {current} बजे के लिए सेट है।" if current else "कोई अलार्म सेट नहीं है।")
    return True


def _handle_alarm_set(text: str) -> State:
    """
    Detect alarm-set intent and transition to AWAITING_PIN.
    Returns AWAITING_PIN if triggered, else ACTIVE.
    """
    alarm_keywords = ["अलार्म", "जगाना", "उठाना", "याद"]
    if not any(kw in text for kw in alarm_keywords):
        return State.ACTIVE

    assistant_ctx["pending_alarm_text"] = text
    assistant_ctx["pin_prompt_time"]    = time.time()
    speak("अलार्म सेट करने के लिए पासवर्ड बोलिए। कृपया अपना पिन बोलें।")
    print("🔐 Alarm intent detected → requesting PIN...")
    return State.AWAITING_PIN


# ─────────────────────────────────────────────────────────────────────────────
# Notice handler
# ─────────────────────────────────────────────────────────────────────────────

def _handle_notice(text: str) -> State:
    """
    Parse and begin handling a notice command.
    If a start intent is detected, transitions to RECORDING_NOTICE.
    Returns ACTIVE for cancel/status/no-match.
    """
    intent = extract_notice_intent(text)
    if intent is None:
        return State.ACTIVE   # not a notice command — signal no-match

    action = intent["action"]

    if action == "cancel":
        if cancel_notice():
            speak("नोटिस रद्द कर दिया।")
        else:
            speak("कोई नोटिस नहीं है।")
        return State.ACTIVE

    if action == "status":
        speak(format_notice_remaining())
        return State.ACTIVE

    if action == "unclear":
        speak("नोटिस का समय समझ नहीं आया। दोबारा बोलें।")
        speak("उदाहरण: दस मिनट बाद नोटिस लगाओ।")
        return State.ACTIVE

    # start_duration or start_clock — store delay and go to recording state
    delay = intent["delay"]
    label = intent["label"]
    assistant_ctx["pending_notice_delay"] = delay
    assistant_ctx["pending_notice_label"] = label

    speak(f"ठीक है। {label} का नोटिस सेट होगा।")
    speak("अब अपना नोटिस बोलिए। आपके पास 7 सेकंड हैं।")
    print(f"📢 Notice recording mode — delay={delay:.0f}s label='{label}'")
    return State.RECORDING_NOTICE


def handle_notice_recording(text: str) -> State:
    """
    Called when state == RECORDING_NOTICE.
    The Vosk text is ignored — we record raw audio from the mic in a
    background thread so the main loop is never blocked.
    Returns ACTIVE immediately.
    """
    import threading

    delay = assistant_ctx.get("pending_notice_delay") or 60.0
    label = assistant_ctx.get("pending_notice_label", "")
    assistant_ctx["pending_notice_delay"] = None
    assistant_ctx["pending_notice_label"] = ""

    def _record_and_schedule():
        filepath = record_notice(duration=7.0)
        if filepath:
            schedule_notice(filepath, delay, label)
            speak(f"नोटिस रिकॉर्ड हो गया। {label} बजेगा।")
        else:
            speak("नोटिस रिकॉर्ड नहीं हो सका। दोबारा कोशिश करें।")

    threading.Thread(target=_record_and_schedule, daemon=True,
                     name="NoticeRecorder").start()
    return State.ACTIVE


# ─────────────────────────────────────────────────────────────────────────────
# Volume handler
# ─────────────────────────────────────────────────────────────────────────────

def _handle_volume(text: str) -> bool:
    """
    Parse and execute a volume command.
    Returns True if text was a volume command.
    """
    intent = extract_volume_intent(text)
    if intent is None:
        return False

    action = intent["action"]
    step   = intent["step"]

    if action == "increase":
        new_vol = increase_volume(step)
        speak(f"वॉल्यूम बढ़ा दिया। अब {new_vol} प्रतिशत है।")
        print(f"🔊 Volume ↑ {new_vol}%")

    elif action == "decrease":
        new_vol = decrease_volume(step)
        speak(f"वॉल्यूम घटा दिया। अब {new_vol} प्रतिशत है।")
        print(f"🔊 Volume ↓ {new_vol}%")

    elif action == "mute":
        mute()
        speak("आवाज़ बंद कर दी।")
        print("🔇 Muted")

    elif action == "unmute":
        unmute()
        vol = get_volume()
        speak(f"आवाज़ चालू कर दी। वॉल्यूम {vol} प्रतिशत है।")
        print(f"🔊 Unmuted ({vol}%)")

    elif action == "set":
        pct     = intent["percent"]
        new_vol = set_volume(pct)
        speak(f"वॉल्यूम {new_vol} प्रतिशत पर सेट हो गया।")
        print(f"🔊 Volume = {new_vol}%")

    elif action == "status":
        vol    = get_volume()
        muted  = is_muted()
        status = "म्यूट है" if muted else f"{vol} प्रतिशत"
        speak(f"वॉल्यूम {status} है।")
        print(f"🔊 Volume status: {vol}% muted={muted}")

    elif action == "unclear":
        speak("वॉल्यूम कमांड समझ नहीं आया। कहिए: वॉल्यूम बढ़ाओ या वॉल्यूम कम करो।")

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Public: ACTIVE state dispatcher
# ─────────────────────────────────────────────────────────────────────────────

def handle_active_command(text: str) -> State:
    """
    Route a recognized command to the appropriate handler.

    Priority order:
        1. Exit
        2. Time query
        3. Volume control
        4. Timer
        5. Math
        6. Notice
        7. Alarm cancel / status / set
    """
    # 1 — Exit
    if EXIT_WORD in text:
        speak("ठीक है, मैं सो रहा हूँ। धन्यवाद!")
        print("🙏 Going back to sleep...\n")
        return State.SLEEPING

    # 2 — Time / Date query (non-exclusive)
    check_time_query(text)
    check_date_query(text)

    # 3 — Volume control
    if _handle_volume(text):
        return State.ACTIVE

    # 4 — Timer
    if _handle_timer(text):
        return State.ACTIVE

    # 5 — Math
    if _handle_math(text):
        return State.ACTIVE

    # 6 — Notice (before alarm — 'याद' keyword shared)
    notice_state = _handle_notice(text)
    if notice_state != State.ACTIVE or extract_notice_intent(text) is not None:
        return notice_state

    # 7 — Alarm cancel / status / set
    if _handle_alarm_cancel(text):
        return State.ACTIVE
    if _handle_alarm_status(text):
        return State.ACTIVE
    return _handle_alarm_set(text)


# ─────────────────────────────────────────────────────────────────────────────
# Public: AWAITING_PIN state handler
# ─────────────────────────────────────────────────────────────────────────────

def handle_pin_input(text: str, audio: np.ndarray | None = None) -> State:
    """
    Process spoken text while waiting for the security PIN.

    Args:
        text : Vosk-recognised transcript of the PIN utterance
        audio: Raw int16 PCM captured during that utterance (from the
               RawInputStream buffer).  Passed to authenticate_user so
               voice verification reuses this audio instead of calling
               sd.rec() a second time (which would capture silence or
               conflict with the open stream).

    Returns the next state (ACTIVE in all cases — either success or failure).
    """
    # Timeout
    elapsed = time.time() - assistant_ctx["pin_prompt_time"]
    if elapsed > PIN_PROMPT_TIMEOUT:
        speak("समय समाप्त। अलार्म सेट नहीं हुआ।")
        print("⏱️  PIN timeout. Returning to ACTIVE.\n")
        return State.ACTIVE

    # Escape hatch
    if EXIT_WORD in text:
        speak("ठीक है, अलार्म रद्द।")
        return State.ACTIVE

    # Authenticate (pass pre-captured audio so we don't do a second recording)
    print(f"🔑 PIN attempt: '{text}'")
    auth = authenticate_user(spoken_pin=text, check_voice=True, audio=audio)
    print(f"   PIN ok={auth['pin_ok']}  Voice ok={auth['voice_ok']}")
    print(f"   {auth['reason']}")

    pending = assistant_ctx.get("pending_alarm_text", "")
    assistant_ctx["pending_alarm_text"] = ""

    if auth["authorized"]:
        speak("प्रमाणीकरण सफल! अलार्म सेट हो रहा है।")
        result = extract_alarm_intent(pending)
        if result is None:
            speak("अलार्म का समय समझ नहीं आया। कृपया दोबारा बोलें।")
    else:
        speak(auth["reason"])
        speak("अलार्म सेट नहीं हुआ।")

    return State.ACTIVE
