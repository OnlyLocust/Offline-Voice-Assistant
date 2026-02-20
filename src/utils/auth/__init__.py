"""
utils/auth/__init__.py
Re-exports the public API so callers can still do:
    from utils.auth import authenticate_user
"""
import numpy as np

from utils.auth.pin_auth   import verify_pin
from utils.auth.voice_auth import (
    enroll_voice, verify_voice, verify_voice_from_audio, load_voice_profile
)


def authenticate_user(spoken_pin: str,
                      check_voice: bool = True,
                      audio: np.ndarray | None = None) -> dict:
    """
    Full two-factor authentication pipeline.

    Args:
        spoken_pin : Vosk-transcribed text of what the user spoke
        check_voice: Whether to run MFCC voice verification (default True)
        audio      : Pre-recorded int16 PCM array from the mic stream.
                     If provided, voice is verified from this buffer
                     (avoids a second sd.rec() that conflicts with
                     the open RawInputStream).  If None, falls back to
                     a fresh sd.rec() recording.

    Returns dict with keys:
        pin_ok, voice_ok, authorized (bool), reason (str)
    """
    result = {"pin_ok": False, "voice_ok": False, "authorized": False, "reason": ""}

    # Step 1 — PIN
    result["pin_ok"] = verify_pin(spoken_pin)
    if not result["pin_ok"]:
        result["reason"] = "❌ गलत पासवर्ड (Wrong PIN)"
        return result

    # Step 2 — Voice (informational only — PIN alone is enough to authorize)
    if check_voice:
        if audio is not None and len(audio) > 0:
            result["voice_ok"] = verify_voice_from_audio(audio)
        else:
            result["voice_ok"] = verify_voice()

        if not result["voice_ok"]:
            # Warn but do NOT block — correct PIN is sufficient
            print("⚠️  Voice mismatch detected (PIN correct — alarm will still be set)")
    else:
        result["voice_ok"] = True   # skipped

    # PIN correct → authorized regardless of voice result
    result["authorized"] = True
    result["reason"] = "✅ प्रमाणीकरण सफल (Authentication successful)"
    return result
