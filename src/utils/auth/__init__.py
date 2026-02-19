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

    # Step 2 — Voice
    if check_voice:
        if audio is not None and len(audio) > 0:
            # Use the already-recorded PIN audio — no extra mic recording needed
            result["voice_ok"] = verify_voice_from_audio(audio)
        else:
            # Fallback: record fresh (only works if mic stream is NOT open)
            result["voice_ok"] = verify_voice()

        if not result["voice_ok"]:
            result["reason"] = "❌ आवाज़ मेल नहीं खाती (Voice mismatch)"
            return result
    else:
        result["voice_ok"] = True   # skipped

    result["authorized"] = True
    result["reason"] = "✅ प्रमाणीकरण सफल (Authentication successful)"
    return result
