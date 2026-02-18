"""
utils/auth/__init__.py
Re-exports the public API so callers can still do:
    from utils.auth import authenticate_user
"""
from utils.auth.pin_auth   import verify_pin
from utils.auth.voice_auth import enroll_voice, verify_voice, load_voice_profile


def authenticate_user(spoken_pin: str, check_voice: bool = True) -> dict:
    """
    Full two-factor authentication pipeline.

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
        result["voice_ok"] = verify_voice()
        if not result["voice_ok"]:
            result["reason"] = "❌ आवाज़ मेल नहीं खाती (Voice mismatch)"
            return result
    else:
        result["voice_ok"] = True   # skipped

    result["authorized"] = True
    result["reason"] = "✅ प्रमाणीकरण सफल (Authentication successful)"
    return result
