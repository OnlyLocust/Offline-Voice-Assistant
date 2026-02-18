"""
voice_auth.py — MFCC-based Offline Voice Authentication
=========================================================
Records a short audio sample, extracts MFCC features, and compares
them against an enrolled voice profile using cosine similarity.

All processing is fully offline — no internet, no cloud API.

Public API:
    enroll_voice(duration)     — record and save a voice profile (run once)
    load_voice_profile()       — load profile from disk
    verify_voice(duration)     — record + compare; returns True/False
"""

import os
import numpy as np
import sounddevice as sd

from utils.constants import SAMPLE_RATE, VOICE_PROFILE_PATH, VOICE_AUTH_THRESHOLD

# ── Optional MFCC library ─────────────────────────────────────────────────────
try:
    from python_speech_features import mfcc as compute_mfcc
    MFCC_AVAILABLE = True
except ImportError:
    MFCC_AVAILABLE = False
    print("⚠️  python_speech_features not installed — voice auth DISABLED.")
    print("    pip install python_speech_features")


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _record_audio(duration: float) -> np.ndarray:
    """Block and record `duration` seconds from the default microphone."""
    print(f"🎙️  Recording for {duration:.1f}s...")
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
    )
    sd.wait()
    return audio.flatten()


def _extract_mfcc(audio: np.ndarray) -> np.ndarray | None:
    """Return mean MFCC vector (shape: 13,) or None if library missing."""
    if not MFCC_AVAILABLE:
        return None
    audio_f  = audio.astype(np.float32) / 32768.0
    features = compute_mfcc(audio_f, samplerate=SAMPLE_RATE, numcep=13)
    return np.mean(features, axis=0)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity in [0, 1] between two 1-D vectors."""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _profile_path() -> str:
    """Resolve the .npy path for the voice profile."""
    p = VOICE_PROFILE_PATH
    return p if p.endswith(".npy") else p + ".npy"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def enroll_voice(duration: float = 4.0) -> bool:
    """
    Record a voice sample and save its MFCC profile to disk.
    Call this ONCE during initial setup.

    Returns True on success, False on failure.
    """
    if not MFCC_AVAILABLE:
        print("❌ Enrollment skipped: python_speech_features not available.")
        return False

    print("📢 बोलिए — अपना परिचय दीजिए (Speak any phrase for enrollment)...")
    audio   = _record_audio(duration)
    profile = _extract_mfcc(audio)

    if profile is None:
        return False

    path = _profile_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.save(path, profile)
    print(f"✅ Voice profile saved → {path}")
    return True


def load_voice_profile() -> np.ndarray | None:
    """Load the enrolled MFCC profile from disk. Returns None if not found."""
    path = _profile_path()
    if not os.path.exists(path):
        return None
    return np.load(path)


def verify_voice(duration: float = 3.0) -> bool:
    """
    Record a short sample and compare with the enrolled profile.

    Returns:
        True  — similarity ≥ VOICE_AUTH_THRESHOLD  (authorized)
        True  — if MFCC library missing or no profile (fail-open)
        False — similarity below threshold
    """
    if not MFCC_AVAILABLE:
        print("⚠️  Voice auth skipped (library missing). Allowing by default.")
        return True

    profile = load_voice_profile()
    if profile is None:
        print("⚠️  No voice profile found. Run enroll_voice() first. Allowing.")
        return True

    print("🎙️  आवाज़ सत्यापन — कुछ बोलिए (Speak for voice verification)...")
    audio  = _record_audio(duration)
    sample = _extract_mfcc(audio)

    if sample is None:
        return False

    score = _cosine_similarity(profile, sample)
    print(f"🔍 Voice similarity: {score:.3f}  (threshold: {VOICE_AUTH_THRESHOLD})")
    return score >= VOICE_AUTH_THRESHOLD
