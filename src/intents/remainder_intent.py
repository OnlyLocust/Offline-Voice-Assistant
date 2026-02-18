"""
remainder_intent.py — Alarm Intent Extractor
==============================================
Parses Hindi speech text to extract alarm/reminder intent,
then calls set_alarm() from alarm_thread to actually schedule it.
"""

import re
from datetime import datetime, timedelta
from utils.alarm_thread import set_alarm

# ── Hindi number words ─────────────────────────────────────────────────────────
HINDI_NUMBERS = {
    "एक": 1,  "दो": 2,   "तीन": 3,  "चार": 4,
    "पांच": 5, "पाँच": 5, "छह": 6,   "सात": 7,
    "आठ": 8,  "नौ": 9,   "दस": 10,  "ग्यारह": 11, "बारह": 12,
}


def word_to_number(text: str) -> int | None:
    for word, num in HINDI_NUMBERS.items():
        if word in text:
            return num
    return None


def detect_date(text: str) -> str:
    today = datetime.now().date()
    if "परसों" in text:
        return str(today + timedelta(days=2))
    elif "कल" in text:
        return str(today + timedelta(days=1))
    else:
        return str(today)   # default: today


def detect_period(text: str) -> str | None:
    if "सुबह" in text:
        return "AM"
    if "शाम" in text or "रात" in text:
        return "PM"
    return None


def extract_time(text: str) -> tuple[int | None, int | None]:
    # "10:30" or "10.30"
    match = re.search(r'(\d{1,2})[:.:](\d{2})', text)
    if match:
        return int(match.group(1)), int(match.group(2))

    # bare digit like "10 बजे"
    match = re.search(r'(\d{1,2})', text)
    if match:
        return int(match.group(1)), 0

    # Hindi word like "सात बजे"
    num = word_to_number(text)
    if num:
        return num, 0

    return None, None


def extract_alarm_intent(text: str) -> dict | None:
    """
    Parse Hindi text for alarm intent.

    Returns a result dict if an alarm intent was found and the alarm was set,
    otherwise returns None.
    """
    lower = text.lower()

    # ── Detect alarm action ────────────────────────────────────────────────────
    if not any(kw in lower for kw in ["अलार्म", "जगाना", "उठाना", "याद"]):
        return None   # not an alarm command

    result = {
        "action": "set_alarm",
        "date": detect_date(lower),
        "period": detect_period(lower),
        "time": None,
    }

    # ── Extract time ───────────────────────────────────────────────────────────
    hour, minute = extract_time(lower)

    if hour is None:
        print("⚠️  समय समझ नहीं आया। कृपया दोबारा बोलें।")
        print("    (Could not understand the time. Please repeat.)")
        return None

    # Apply AM/PM correction
    if result["period"] == "PM" and hour < 12:
        hour += 12
    elif result["period"] == "AM" and hour == 12:
        hour = 0

    # Clamp to valid range
    hour   = max(0, min(23, hour))
    minute = max(0, min(59, minute))

    alarm_str = f"{hour:02d}:{minute:02d}"
    result["time"] = alarm_str

    print(f"📋 Alarm intent parsed: {result}")

    # ── Actually set the alarm ─────────────────────────────────────────────────
    set_alarm(alarm_str)

    return result
