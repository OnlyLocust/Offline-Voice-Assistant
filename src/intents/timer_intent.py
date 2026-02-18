"""
timer_intent.py — Hindi Timer Command Parser
=============================================
Parses Hindi speech text to extract timer duration.

Supported patterns (examples):
  "दस मिनट का टाइमर लगाओ"
  "पांच मिनट का टाइमर सेट करो"
  "दो घंटे का टाइमर लगाओ"
  "तीस सेकंड का टाइमर"
  "10 minute ka timer lagao"   ← Hinglish also works
  "timer band karo"
  "timer cancel karo"
  "timer kitna baaki hai"

Returns:
  extract_timer_intent(text) → dict | None
    {
      "action":  "start" | "cancel" | "status",
      "seconds": int | None,   # only for "start"
      "label":   str,          # human-readable duration e.g. "10 मिनट"
    }
"""

import re

# ── Hindi + Hinglish number words ─────────────────────────────────────────────
HINDI_NUMBERS: dict[str, int] = {
    # ones
    "शून्य": 0,  "zero": 0,
    "एक": 1,    "ek": 1,    "one": 1,
    "दो": 2,    "do": 2,    "two": 2,
    "तीन": 3,   "teen": 3,  "three": 3,
    "चार": 4,   "char": 4,  "four": 4,
    "पांच": 5,  "पाँच": 5,  "paanch": 5, "five": 5,
    "छह": 6,    "chhe": 6,  "six": 6,
    "सात": 7,   "saat": 7,  "seven": 7,
    "आठ": 8,    "aath": 8,  "eight": 8,
    "नौ": 9,    "nau": 9,   "nine": 9,
    "दस": 10,   "das": 10,  "ten": 10,
    "ग्यारह": 11, "gyarah": 11, "eleven": 11,
    "बारह": 12, "barah": 12, "twelve": 12,
    "तेरह": 13, "terah": 13, "thirteen": 13,
    "चौदह": 14, "chaudah": 14, "fourteen": 14,
    "पंद्रह": 15, "pandrah": 15, "fifteen": 15,
    "सोलह": 16, "solah": 16, "sixteen": 16,
    "सत्रह": 17, "satrah": 17, "seventeen": 17,
    "अठारह": 18, "atharah": 18, "eighteen": 18,
    "उन्नीस": 19, "unnees": 19, "nineteen": 19,
    "बीस": 20,  "bees": 20,  "twenty": 20,
    "तीस": 30,  "tees": 30,  "thirty": 30,
    "चालीस": 40, "chalis": 40, "forty": 40,
    "पचास": 50, "pachaas": 50, "fifty": 50,
    "साठ": 60,  "saath": 60, "sixty": 60,
    "सत्तर": 70, "sattar": 70, "seventy": 70,
    "अस्सी": 80, "assi": 80, "eighty": 80,
    "नब्बे": 90, "nabbe": 90, "ninety": 90,
}

# ── Time unit keywords ─────────────────────────────────────────────────────────
SECOND_WORDS = {
    "सेकंड", "सेकेंड", "second", "seconds", "sec",
}
MINUTE_WORDS = {
    "मिनट", "मिनटों", "minute", "minutes", "min",
}
HOUR_WORDS = {
    "घंटे", "घंटा", "घंटों", "hour", "hours", "ghante", "ghanta",
}

# ── Timer action keywords ──────────────────────────────────────────────────────
START_WORDS  = {
    "लगाओ", "लगा", "लगा दो", "लगादो",
    "सेट", "set", "set karo",
    "शुरू", "शुरू करो", "शुरू कर दो", "shuru", "start",
    "lagao", "laga", "karo", "kar do", "kardo",
    "चालू", "चलाओ", "चला दो",
}
CANCEL_WORDS = {
    "रद्द", "बंद", "बंद करो", "बंद कर दो",
    "cancel", "band", "stop", "rok", "रोको", "रोक",
    "हटाओ", "हटा दो",
}
STATUS_WORDS = {
    "बाकी", "बाकी है", "kitna", "कितना", "कितना बाकी",
    "status", "remaining", "बचा", "baaki", "बताओ",
    "कितना रहा", "कितना बचा",
}
# Vosk often drops the final 'र' from टाइमर → टाइम
# Also accept Hinglish spellings
TIMER_WORDS  = {
    "टाइमर", "टाइम", "timer", "taimer", "taim", "time",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _word_to_num(token: str) -> int | None:
    """Convert a single Hindi/Hinglish/digit word to integer."""
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return HINDI_NUMBERS.get(token)


def _extract_number(tokens: list[str]) -> tuple[int | None, int]:
    """
    Scan token list for a number (digit or word).
    Returns (value, index_of_token) or (None, -1).
    """
    for i, tok in enumerate(tokens):
        val = _word_to_num(tok)
        if val is not None:
            return val, i
    return None, -1


def _classify_unit(token: str) -> str | None:
    """Return 'second', 'minute', or 'hour' for a unit token, else None."""
    t = token.lower()
    if t in SECOND_WORDS:
        return "second"
    if t in MINUTE_WORDS:
        return "minute"
    if t in HOUR_WORDS:
        return "hour"
    return None


def _to_seconds(value: int, unit: str) -> int:
    if unit == "second":
        return value
    if unit == "minute":
        return value * 60
    if unit == "hour":
        return value * 3600
    return value * 60   # default: minutes


def _unit_label(value: int, unit: str) -> str:
    labels = {"second": "सेकंड", "minute": "मिनट", "hour": "घंटे"}
    return f"{value} {labels.get(unit, unit)}"


# ─────────────────────────────────────────────────────────────────────────────
# Main parser
# ─────────────────────────────────────────────────────────────────────────────

def _has_timer_trigger(lower: str, tokens: list[str]) -> bool:
    """
    Return True if the text looks like a timer command.

    Two ways to trigger:
      1. Contains an explicit timer keyword (टाइमर, टाइम, timer, taim…)
      2. Contains a time-unit word (मिनट / घंटे / सेकंड) + an action word
         → catches "एक मिनट का लगाओ" even if Vosk drops 'टाइमर' entirely
    """
    has_unit   = any(tok in SECOND_WORDS | MINUTE_WORDS | HOUR_WORDS for tok in tokens)
    has_action = any(sw in lower for sw in START_WORDS | CANCEL_WORDS | STATUS_WORDS)
    has_number = any(_word_to_num(tok) is not None for tok in tokens)

    # Primary: strong timer keywords (टाइमर, timer, taimer) — always trigger
    STRONG_TIMER = {"टाइमर", "timer", "taimer"}
    if any(tw in lower for tw in STRONG_TIMER):
        return True

    # Weak timer keywords (टाइम, taim, time) — only trigger when combined
    # with a unit word to avoid false positives on "समय बताओ" type queries
    WEAK_TIMER = {"टाइम", "taim", "time"}
    if any(tw in lower for tw in WEAK_TIMER):
        return has_unit or has_action

    # No timer keyword at all — require unit + (action or number)
    return has_unit and (has_action or has_number)


def extract_timer_intent(text: str) -> dict | None:
    """
    Parse Hindi/Hinglish text for a timer command.

    Returns a dict or None if no timer intent found.

    Handles Vosk quirks:
      - "टाइमर" often transcribed as "टाइम"
      - "लगाओ" sometimes heard as "लगा दो" / "शुरू कर दो"
      - Number + unit alone ("एक मिनट का") treated as start intent
    """
    lower  = text.lower().strip()
    tokens = lower.split()

    # Gate: must look like a timer command
    if not _has_timer_trigger(lower, tokens):
        return None

    # ── CANCEL ────────────────────────────────────────────────────────────────
    if any(cw in lower for cw in CANCEL_WORDS):
        return {"action": "cancel", "seconds": None, "label": ""}

    # ── STATUS ────────────────────────────────────────────────────────────────
    if any(sw in lower for sw in STATUS_WORDS):
        return {"action": "status", "seconds": None, "label": ""}

    # ── START — extract number + unit ─────────────────────────────────────────
    number, num_idx = _extract_number(tokens)

    if number is None:
        # Has timer keyword but no number → ask user to repeat
        return {"action": "unclear", "seconds": None, "label": ""}

    # Look for a unit word anywhere in the sentence (not just near the number)
    # Vosk sometimes reorders tokens slightly
    unit = None
    # First try near the number (preferred)
    search_range = tokens[max(0, num_idx - 1): num_idx + 5]
    for tok in search_range:
        unit = _classify_unit(tok)
        if unit:
            break
    # Fallback: scan whole sentence
    if unit is None:
        for tok in tokens:
            unit = _classify_unit(tok)
            if unit:
                break
    # Last resort: default to minutes
    if unit is None:
        unit = "minute"

    seconds = _to_seconds(number, unit)
    label   = _unit_label(number, unit)

    print(f"⏱️  Timer intent: {number} {unit} = {seconds}s  (from: '{text}')")

    return {
        "action":  "start",
        "seconds": seconds,
        "label":   label,
    }
