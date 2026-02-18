"""
intents/volume_intent.py — Hindi/Hinglish Volume Command Parser
================================================================
Parses speech text to detect volume control commands.

Supported patterns:
  INCREASE:
    "volume badhao", "awaz tez karo", "volume upar karo"
    "आवाज़ बढ़ाओ", "वॉल्यूम तेज़ करो", "ज़्यादा आवाज़"

  DECREASE:
    "volume kam karo", "awaz dheemi karo", "volume neeche karo"
    "आवाज़ कम करो", "वॉल्यूम धीमा करो", "आवाज़ घटाओ"

  MUTE:
    "mute karo", "awaz band karo", "chup karo"
    "म्यूट करो", "आवाज़ बंद करो"

  UNMUTE:
    "unmute karo", "awaz chalu karo", "awaz wapas lao"
    "अनम्यूट करो", "आवाज़ चालू करो"

  SET (exact %):
    "volume 50 percent karo", "volume 70 pratishat set karo"
    "वॉल्यूम 50 प्रतिशत", "आवाज़ 80 पर सेट करो"

  STATUS:
    "volume kitna hai", "awaz kitni hai"
    "वॉल्यूम कितना है"

Returns:
    extract_volume_intent(text) → dict | None
    {
      "action":  "increase" | "decrease" | "mute" | "unmute" | "set" | "status",
      "percent": int | None,   # only for "set"
      "step":    int,          # step size for increase/decrease (default 10)
    }
"""

import re

# ── Keyword sets (all lowercase) ──────────────────────────────────────────────

VOLUME_TRIGGER = {
    # Hindi
    "वॉल्यूम", "आवाज़", "आवाज", "ध्वनि", "आवाज़ें",
    # Hinglish / English
    "volume", "awaz", "awaaz", "sound", "vol",
}

INCREASE_WORDS = {
    # Hindi
    "बढ़ाओ", "बढ़ा", "बढ़ाना", "तेज़", "तेज", "ज़्यादा", "ज्यादा",
    "ऊपर", "उपर", "अधिक", "बड़ा", "बड़ी",
    # Hinglish / English
    "badhao", "badha", "badhana", "tez", "zyada", "jyada",
    "upar", "increase", "up", "louder", "loud", "high", "higher",
    "bada", "badi",
}

DECREASE_WORDS = {
    # Hindi
    "कम", "घटाओ", "घटा", "धीमा", "धीमी", "नीचे", "छोटा",
    "कम करो", "कम करना",
    # Hinglish / English
    "kam", "ghatao", "ghata", "dheema", "dheemi", "neeche",
    "decrease", "down", "lower", "soft", "quiet", "chota",
}

MUTE_WORDS = {
    # Hindi
    "म्यूट", "बंद", "चुप", "शांत", "खामोश",
    # Hinglish / English
    "mute", "band", "chup", "shant", "khamosh", "silent", "silence",
}

UNMUTE_WORDS = {
    # Hindi
    "अनम्यूट", "चालू", "चालु", "वापस", "खोलो",
    # Hinglish / English
    "unmute", "chalu", "wapas", "on", "restore",
}

STATUS_WORDS = {
    # Hindi
    "कितना", "कितनी", "बताओ", "क्या है", "स्तर",
    # Hinglish / English
    "kitna", "kitni", "batao", "status", "level", "check",
}

# Hindi + Hinglish number words (0-100)
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
    "पंद्रह": 15, "pandrah": 15, "fifteen": 15,
    "बीस": 20, "bees": 20, "twenty": 20,
    "पच्चीस": 25, "pachchees": 25, "twenty five": 25,
    "तीस": 30, "tees": 30, "thirty": 30,
    "पैंतीस": 35, "paintees": 35,
    "चालीस": 40, "chalis": 40, "forty": 40,
    "पैंतालीस": 45, "paintaalees": 45,
    "पचास": 50, "pachaas": 50, "fifty": 50,
    "पचपन": 55, "pachpan": 55,
    "साठ": 60, "saath": 60, "sixty": 60,
    "पैंसठ": 65, "painsath": 65,
    "सत्तर": 70, "sattar": 70, "seventy": 70,
    "पचहत्तर": 75, "pachhattar": 75,
    "अस्सी": 80, "assi": 80, "eighty": 80,
    "पचासी": 85, "pachaasi": 85,
    "नब्बे": 90, "nabbe": 90, "ninety": 90,
    "पचानवे": 95, "pachaanave": 95,
    "सौ": 100, "sau": 100, "hundred": 100,
}

PERCENT_WORDS = {"percent", "pratishat", "प्रतिशत", "%", "par", "पर"}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _find_percent(tokens: list[str], lower: str) -> int | None:
    """
    Extract a percentage value from tokens.
    Accepts: "50 percent", "50%", "पचास प्रतिशत", digit strings.
    """
    # Regex: digit optionally followed by %
    m = re.search(r'\b(\d{1,3})\s*%', lower)
    if m:
        return min(100, max(0, int(m.group(1))))

    # Digit token near a percent word
    for i, tok in enumerate(tokens):
        if tok.isdigit():
            val = int(tok)
            # Check surrounding tokens for percent word
            context = tokens[max(0, i-1): i+3]
            if any(pw in context for pw in PERCENT_WORDS):
                return min(100, max(0, val))
            # Also accept bare digit if it's a round number (10,20,...,100)
            if val % 5 == 0 and 0 <= val <= 100:
                return val

        # Hindi word number
        num = _NUMS.get(tok)
        if num is not None:
            context = tokens[max(0, i-1): i+3]
            if any(pw in context for pw in PERCENT_WORDS):
                return min(100, max(0, num))

    return None


def _is_volume_command(lower: str) -> bool:
    return any(vt in lower for vt in VOLUME_TRIGGER)


# ─────────────────────────────────────────────────────────────────────────────
# Main parser
# ─────────────────────────────────────────────────────────────────────────────

def extract_volume_intent(text: str) -> dict | None:
    """
    Parse Hindi/Hinglish text for a volume control command.
    Returns a dict or None if not a volume command.
    """
    lower  = text.lower().strip()
    tokens = lower.split()

    # Gate: must mention volume/sound
    if not _is_volume_command(lower):
        return None

    # ── MUTE (check before decrease — "band" is in both) ─────────────────────
    # Unmute must be checked first (has "chalu" which overrides "band")
    if any(uw in lower for uw in UNMUTE_WORDS):
        return {"action": "unmute", "percent": None, "step": 10}

    if any(mw in lower for mw in MUTE_WORDS):
        return {"action": "mute", "percent": None, "step": 10}

    # ── STATUS ────────────────────────────────────────────────────────────────
    if any(sw in lower for sw in STATUS_WORDS):
        return {"action": "status", "percent": None, "step": 10}

    # ── SET exact % ───────────────────────────────────────────────────────────
    pct = _find_percent(tokens, lower)
    if pct is not None:
        return {"action": "set", "percent": pct, "step": 10}

    # ── INCREASE ──────────────────────────────────────────────────────────────
    if any(iw in lower for iw in INCREASE_WORDS):
        return {"action": "increase", "percent": None, "step": 10}

    # ── DECREASE ──────────────────────────────────────────────────────────────
    if any(dw in lower for dw in DECREASE_WORDS):
        return {"action": "decrease", "percent": None, "step": 10}

    # Volume keyword present but action unclear
    return {"action": "unclear", "percent": None, "step": 10}
