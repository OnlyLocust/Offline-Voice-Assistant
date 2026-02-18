"""
pin_auth.py — Spoken PIN Verification
======================================
Converts spoken Hindi digit words → numeric PIN string → SHA-256 hash compare.

Example:
    "एक दो तीन चार"  →  "1234"  →  hash match
    "1 2 3 4"         →  "1234"  →  hash match
"""

import hashlib
from utils.constants import AUTH_PIN_HASH, HINDI_PIN_WORDS


def _hash_pin(pin: str) -> str:
    """Return SHA-256 hex digest of the PIN string."""
    return hashlib.sha256(pin.encode()).hexdigest()


def verify_pin(spoken_text: str) -> bool:
    """
    Parse spoken text for digit words or numerals and compare against
    the stored PIN hash.

    Accepts:
        • Hindi words  : "एक दो तीन चार"
        • Hinglish     : "ek do teen char"
        • Raw digits   : "1234" or "1 2 3 4"
        • Mixed        : "एक 2 तीन 4"
    """
    spoken_text = spoken_text.strip().lower()
    tokens      = spoken_text.split()
    pin_digits  = []

    for token in tokens:
        if token in HINDI_PIN_WORDS:
            pin_digits.append(str(HINDI_PIN_WORDS[token]))
        elif token.isdigit():
            pin_digits.extend(list(token))   # "1234" → ['1','2','3','4']

    if not pin_digits:
        return False

    return _hash_pin("".join(pin_digits)) == AUTH_PIN_HASH
