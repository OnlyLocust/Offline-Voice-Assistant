"""
auth.py — Offline Authentication Module
========================================
Provides two layers of security for alarm setting:
  1. Password (PIN) verification via spoken digits (Hindi)
  2. Voice authentication via MFCC cosine similarity

All processing is done offline on-device (Raspberry Pi / Windows).
"""

import os
import json
import hashlib
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
import tempfile

# ── Optional: scipy for MFCC (pure offline) ──────────────────────────────────
try:
    from python_speech_features import mfcc as compute_mfcc
    MFCC_AVAILABLE = True
except ImportError:
    MFCC_AVAILABLE = False
    print("⚠️  python_speech_features not installed. Voice auth will be DISABLED.")
    print("    Install with: pip install python_speech_features")

from utils.constants import (
    SAMPLE_RATE,
    AUTH_PIN_HASH,
    VOICE_PROFILE_PATH,
    VOICE_AUTH_THRESHOLD,
    HINDI_PIN_WORDS,
)

# ─────────────────────────────────────────────────────────────────────────────
# PIN / Password Verification
# ─────────────────────────────────────────────────────────────────────────────

def _hash_pin(pin: str) -> str:
    """SHA-256 hash of the PIN string."""
    return hashlib.sha256(pin.encode()).hexdigest()


def verify_pin(spoken_text: str) -> bool:
    """
    Convert spoken Hindi digit words → numeric PIN string → compare hash.

    Example: "एक दो तीन चार" → "1234"
    Also accepts raw digit strings like "1 2 3 4" or "1234".
    """
    spoken_text = spoken_text.strip().lower()

    # Build PIN from Hindi words
    tokens = spoken_text.split()
    pin_digits = []
    for token in tokens:
        if token in HINDI_PIN_WORDS:
            pin_digits.append(str(HINDI_PIN_WORDS[token]))
        elif token.isdigit():
            pin_digits.extend(list(token))  # "1234" → ['1','2','3','4']

    if not pin_digits:
        return False

    pin_str = "".join(pin_digits)
    return _hash_pin(pin_str) == AUTH_PIN_HASH


# ─────────────────────────────────────────────────────────────────────────────
# Voice Authentication (MFCC Cosine Similarity)
# ─────────────────────────────────────────────────────────────────────────────

def _record_audio(duration: float = 3.0) -> np.ndarray:
    """Record `duration` seconds of audio from the microphone."""
    print(f"🎙️  Recording for {duration:.1f}s...")
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
    )
    sd.wait()
    return audio.flatten()


def _extract_mfcc(audio: np.ndarray) -> np.ndarray:
    """Extract mean MFCC feature vector from raw int16 audio."""
    if not MFCC_AVAILABLE:
        return None
    audio_float = audio.astype(np.float32) / 32768.0
    features = compute_mfcc(audio_float, samplerate=SAMPLE_RATE, numcep=13)
    return np.mean(features, axis=0)  # shape: (13,)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def enroll_voice(duration: float = 4.0) -> bool:
    """
    Record user's voice and save MFCC profile to disk.
    Call this once during setup / enrollment.
    Returns True on success.
    """
    if not MFCC_AVAILABLE:
        print("❌ Voice enrollment skipped: python_speech_features not available.")
        return False

    print("📢 बोलिए — अपना परिचय दीजिए (Speak a sample phrase for enrollment)...")
    audio = _record_audio(duration)
    profile = _extract_mfcc(audio)

    if profile is None:
        return False

    os.makedirs(os.path.dirname(VOICE_PROFILE_PATH), exist_ok=True)
    np.save(VOICE_PROFILE_PATH, profile)
    print(f"✅ Voice profile saved → {VOICE_PROFILE_PATH}")
    return True


def load_voice_profile() -> np.ndarray | None:
    """Load the enrolled voice profile from disk."""
    path = VOICE_PROFILE_PATH + ".npy" if not VOICE_PROFILE_PATH.endswith(".npy") else VOICE_PROFILE_PATH
    if not os.path.exists(path):
        # Try without extension
        alt = VOICE_PROFILE_PATH if os.path.exists(VOICE_PROFILE_PATH) else None
        if alt is None:
            return None
        path = alt
    return np.load(path)


def verify_voice(duration: float = 3.0) -> bool:
    """
    Record a short voice sample and compare with enrolled profile.
    Returns True if similarity ≥ VOICE_AUTH_THRESHOLD.
    """
    if not MFCC_AVAILABLE:
        print("⚠️  Voice auth skipped (library missing). Allowing by default.")
        return True

    profile = load_voice_profile()
    if profile is None:
        print("⚠️  No voice profile found. Run enroll_voice() first. Allowing by default.")
        return True

    print("🎙️  आवाज़ सत्यापन — कुछ बोलिए (Speak for voice verification)...")
    audio = _record_audio(duration)
    sample = _extract_mfcc(audio)

    if sample is None:
        return False

    similarity = _cosine_similarity(profile, sample)
    print(f"🔍 Voice similarity score: {similarity:.3f} (threshold: {VOICE_AUTH_THRESHOLD})")

    return similarity >= VOICE_AUTH_THRESHOLD


# ─────────────────────────────────────────────────────────────────────────────
# Combined Auth Gate
# ─────────────────────────────────────────────────────────────────────────────

def authenticate_user(spoken_pin: str, check_voice: bool = True) -> dict:
    """
    Full authentication pipeline.

    Args:
        spoken_pin:  Transcribed text containing the spoken PIN.
        check_voice: Whether to also run voice verification.

    Returns:
        dict with keys:
            - 'pin_ok'   (bool)
            - 'voice_ok' (bool)
            - 'authorized' (bool) — True only if both pass
            - 'reason'   (str)
    """
    result = {"pin_ok": False, "voice_ok": False, "authorized": False, "reason": ""}

    # Step 1: PIN
    result["pin_ok"] = verify_pin(spoken_pin)
    if not result["pin_ok"]:
        result["reason"] = "❌ गलत पासवर्ड (Wrong PIN)"
        return result

    # Step 2: Voice
    if check_voice:
        result["voice_ok"] = verify_voice()
        if not result["voice_ok"]:
            result["reason"] = "❌ आवाज़ मेल नहीं खाती (Voice mismatch)"
            return result
    else:
        result["voice_ok"] = True  # skipped

    result["authorized"] = True
    result["reason"] = "✅ प्रमाणीकरण सफल (Authentication successful)"
    return result
