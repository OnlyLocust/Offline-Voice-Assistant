"""
intents/notice_intent.py — Hindi/Hinglish Notice Command Parser
================================================================
Parses speech text to detect notice-related commands.

Supported patterns:
  START (duration-based):
    "notice set karo 10 minute baad"
    "10 मिनट बाद नोटिस लगाओ"
    "दस मिनट बाद याद दिलाना"
    "notice 5 minute mein"

  START (clock-time-based):
    "5 baje notice sunana"
    "सात बजे नोटिस बजाओ"
    "notice 7:30 baje"

  CANCEL:
    "notice cancel karo"
    "notice band karo"
    "नोटिस रद्द करो"

  STATUS:
    "notice kitna baaki hai"
    "नोटिस कब बजेगा"

Returns:
    extract_notice_intent(text) → dict | None
    {
      "action":    "start_duration" | "start_clock" | "cancel" | "status" | "unclear",
      "delay":     float | None,    # seconds from now (for start_duration)
      "clock_hm":  tuple | None,    # (hour, minute) for start_clock
      "label":     str,             # human-readable e.g. "10 मिनट बाद"
    }
"""

import re
from datetime import datetime, timedelta

# ── Hindi + Hinglish number words ─────────────────────────────────────────────
_NUMS: dict[str, int] = {
    "शून्य": 0, "zero": 0,
    "एक": 1,   "ek": 1,    "one": 1,
    "दो": 2,   "do": 2,    "two": 2,
    "तीन": 3,  "teen": 3,  "three": 3,
    "चार": 4,  "char": 4,  "four": 4,
    "पांच": 5, "पाँच": 5,  "paanch": 5, "panch": 5, "five": 5,
    "छह": 6,   "chhe": 6,  "six": 6,
    "सात": 7,  "saat": 7,  "seven": 7,
    "आठ": 8,   "aath": 8,  "eight": 8,
    "नौ": 9,   "nau": 9,   "nine": 9,
    "दस": 10,  "das": 10,  "ten": 10,
    "ग्यारह": 11, "gyarah": 11, "eleven": 11,
    "बारह": 12, "barah": 12, "twelve": 12,
    "तेरह": 13, "terah": 13,
    "चौदह": 14, "chaudah": 14,
    "पंद्रह": 15, "pandrah": 15, "fifteen": 15,
    "सोलह": 16, "solah": 16,
    "सत्रह": 17, "satrah": 17,
    "अठारह": 18, "atharah": 18,
    "उन्नीस": 19, "unnees": 19,
    "बीस": 20,  "bees": 20,  "twenty": 20,
    "तीस": 30,  "tees": 30,  "thirty": 30,
    "चालीस": 40, "chalis": 40, "forty": 40,
    "पचास": 50, "pachaas": 50, "fifty": 50,
    "साठ": 60,  "saath": 60,  "sixty": 60,
}

# ── Keyword sets ───────────────────────────────────────────────────────────────
NOTICE_WORDS  = {"नोटिस", "notice", "याद", "reminder", "याद दिलाना", "याद दिलाओ"}
CANCEL_WORDS  = {"रद्द", "cancel", "band", "बंद", "stop", "हटाओ", "rok"}
STATUS_WORDS  = {"बाकी", "kitna", "कितना", "कब", "status", "baaki", "बताओ", "बजेगा"}
AFTER_WORDS   = {"baad", "बाद", "mein", "में", "ke baad", "के बाद", "बाद में"}
CLOCK_WORDS   = {"baje", "बजे", "bajke", "बजकर", "o'clock"}

SECOND_WORDS  = {"सेकंड", "second", "seconds", "sec"}
MINUTE_WORDS  = {"मिनट", "minute", "minutes", "min"}
HOUR_WORDS    = {"घंटे", "घंटा", "hour", "hours", "ghante", "ghanta"}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _tok_to_num(tok: str) -> int | None:
    t = tok.strip().lower()
    if t.isdigit():
        return int(t)
    return _NUMS.get(t)


def _find_number(tokens: list[str]) -> tuple[int | None, int]:
    for i, tok in enumerate(tokens):
        v = _tok_to_num(tok)
        if v is not None:
            return v, i
    return None, -1


def _classify_unit(tok: str) -> str | None:
    t = tok.lower()
    if t in SECOND_WORDS: return "second"
    if t in MINUTE_WORDS: return "minute"
    if t in HOUR_WORDS:   return "hour"
    return None


def _to_seconds(val: int, unit: str) -> int:
    return val if unit == "second" else val * 60 if unit == "minute" else val * 3600


def _is_notice_command(lower: str) -> bool:
    return any(nw in lower for nw in NOTICE_WORDS)


def _is_after_pattern(lower: str) -> bool:
    """True if text implies 'X time from now' (duration-based)."""
    return any(aw in lower for aw in AFTER_WORDS)


def _is_clock_pattern(lower: str) -> bool:
    """True if text implies a specific clock time."""
    return any(cw in lower for cw in CLOCK_WORDS)


def _parse_clock_time(tokens: list[str], lower: str) -> tuple[int, int] | None:
    """
    Try to extract (hour, minute) from tokens.
    Handles: "7 baje", "7:30 baje", "saat baje"
    """
    # "HH:MM" pattern
    m = re.search(r'(\d{1,2})[:\.](\d{2})', lower)
    if m:
        return int(m.group(1)), int(m.group(2))

    # Single number before/near a clock word
    num, idx = _find_number(tokens)
    if num is not None:
        return num, 0

    return None


def _clock_to_delay(hour: int, minute: int) -> float:
    """Return seconds until the next occurrence of HH:MM (today or tomorrow)."""
    now  = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


# ─────────────────────────────────────────────────────────────────────────────
# Main parser
# ─────────────────────────────────────────────────────────────────────────────

def extract_notice_intent(text: str) -> dict | None:
    """
    Parse Hindi/Hinglish text for a notice command.
    Returns a dict or None if not a notice command.
    """
    lower  = text.lower().strip()
    tokens = lower.split()

    # Gate: must mention notice/reminder
    if not _is_notice_command(lower):
        return None

    # ── CANCEL ────────────────────────────────────────────────────────────────
    if any(cw in lower for cw in CANCEL_WORDS):
        return {"action": "cancel", "delay": None, "clock_hm": None, "label": ""}

    # ── STATUS ────────────────────────────────────────────────────────────────
    if any(sw in lower for sw in STATUS_WORDS):
        return {"action": "status", "delay": None, "clock_hm": None, "label": ""}

    # ── CLOCK TIME ("5 baje notice") ──────────────────────────────────────────
    if _is_clock_pattern(lower):
        hm = _parse_clock_time(tokens, lower)
        if hm:
            h, m = hm
            # Apply AM/PM heuristic: if hour < 6 and no "subah", assume PM
            if h < 6 and "सुबह" not in lower and "subah" not in lower:
                h += 12
            h = min(h, 23)
            delay = _clock_to_delay(h, m)
            label = f"{h:02d}:{m:02d} बजे"
            return {
                "action":   "start_clock",
                "delay":    delay,
                "clock_hm": (h, m),
                "label":    label,
            }
        return {"action": "unclear", "delay": None, "clock_hm": None, "label": ""}

    # ── DURATION ("10 minute baad notice") ────────────────────────────────────
    num, num_idx = _find_number(tokens)
    if num is None:
        return {"action": "unclear", "delay": None, "clock_hm": None, "label": ""}

    # Find unit near the number
    unit = None
    for tok in tokens[max(0, num_idx - 1): num_idx + 5]:
        unit = _classify_unit(tok)
        if unit:
            break
    if unit is None:
        for tok in tokens:
            unit = _classify_unit(tok)
            if unit:
                break
    if unit is None:
        unit = "minute"   # default

    delay = _to_seconds(num, unit)
    unit_labels = {"second": "सेकंड", "minute": "मिनट", "hour": "घंटे"}
    label = f"{num} {unit_labels[unit]} बाद"

    return {
        "action":   "start_duration",
        "delay":    float(delay),
        "clock_hm": None,
        "label":    label,
    }
