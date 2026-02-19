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


def _trim_silence(audio: np.ndarray,
                  frame_ms: int = 20,
                  energy_threshold: float = 0.01) -> np.ndarray:
    """
    Remove leading and trailing low-energy (silent) frames from `audio`.

    This prevents RMS-silent mic padding from pulling the mean MFCC vector
    away from the actual voiced content, which is the dominant cause of
    low cosine-similarity scores between enrollment and verification.

    Args:
        audio:            int16 PCM array.
        frame_ms:         Frame size in milliseconds to measure energy.
        energy_threshold: Fraction of peak RMS below which a frame is silent.

    Returns the trimmed int16 array.  If everything is below the threshold
    (completely silent input) the original array is returned unchanged.
    """
    if len(audio) == 0:
        return audio

    frame_size = int(SAMPLE_RATE * frame_ms / 1000)
    audio_f    = audio.astype(np.float32) / 32768.0

    # Compute per-frame RMS
    n_frames = len(audio_f) // frame_size
    if n_frames == 0:
        return audio

    frames = audio_f[: n_frames * frame_size].reshape(n_frames, frame_size)
    rms    = np.sqrt(np.mean(frames ** 2, axis=1))   # shape: (n_frames,)
    peak   = rms.max()
    if peak == 0:
        return audio

    voiced = rms >= (energy_threshold * peak)         # True where speech present
    voiced_indices = np.where(voiced)[0]
    if voiced_indices.size == 0:
        return audio

    first = voiced_indices[0]  * frame_size
    last  = (voiced_indices[-1] + 1) * frame_size
    return audio[first:last]


def _extract_mfcc(audio: np.ndarray) -> np.ndarray | None:
    """Return mean MFCC vector (shape: 13,) or None if library missing."""
    if not MFCC_AVAILABLE:
        return None
    audio        = _trim_silence(audio)          # drop silent leading/trailing
    audio_f      = audio.astype(np.float32) / 32768.0
    features     = compute_mfcc(audio_f, samplerate=SAMPLE_RATE, numcep=13)
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

def enroll_voice(duration: float = 4.0, passes: int = 3) -> bool:
    """
    Record multiple passes of the user's PIN phrase and save the averaged
    MFCC profile to disk.  Call this ONCE during initial setup.

    Args:
        duration: Seconds to record per pass.
        passes:   Number of repetitions to average (default 3).
                  More passes → more stable profile → better recognition.

    Returns True on success, False on failure.
    """
    if not MFCC_AVAILABLE:
        print("❌ Enrollment skipped: python_speech_features not available.")
        return False

    vectors = []
    for i in range(passes):
        print(f"\n🎙️  Pass {i + 1}/{passes} — अपना PIN बोलिए (Speak your PIN)...")
        audio = _record_audio(duration)
        vec   = _extract_mfcc(audio)
        if vec is None:
            print(f"   ⚠️  Pass {i + 1} failed — skipping.")
            continue
        vectors.append(vec)
        print(f"   ✅ Pass {i + 1} recorded.")
        if i < passes - 1:
            input("   Enter दबाएं और फिर PIN बोलें... (Press Enter, then speak PIN...)")

    if not vectors:
        print("❌ No valid passes recorded. Enrollment failed.")
        return False

    profile = np.mean(vectors, axis=0)   # average across all passes

    path = _profile_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.save(path, profile)
    print(f"\n✅ Voice profile saved ({len(vectors)}/{passes} passes averaged) → {path}")
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


def verify_voice_from_audio(audio: np.ndarray) -> bool:
    """
    Compare a PRE-RECORDED audio array with the enrolled profile.
    Use this when the microphone is already open in a RawInputStream
    (calling sd.rec() again would conflict or record silence).

    Args:
        audio: int16 numpy array of raw PCM samples at SAMPLE_RATE

    Returns:
        True  — similarity ≥ VOICE_AUTH_THRESHOLD  (authorized)
        True  — if MFCC library missing, no profile, or audio too short (fail-open)
        False — similarity below threshold
    """
    if not MFCC_AVAILABLE:
        print("⚠️  Voice auth skipped (library missing). Allowing by default.")
        return True

    profile = load_voice_profile()
    if profile is None:
        print("⚠️  No voice profile found. Run enroll_voice() first. Allowing.")
        return True

    # Need at least ~0.5 s of audio to get meaningful MFCCs
    min_samples = int(SAMPLE_RATE * 0.5)
    if len(audio) < min_samples:
        print(f"⚠️  PIN audio too short ({len(audio)} samples < {min_samples}). Allowing.")
        return True

    print("🔍 आवाज़ की जाँच हो रही है (Verifying voice from PIN audio)...")
    sample = _extract_mfcc(audio)

    if sample is None:
        return False

    score = _cosine_similarity(profile, sample)
    print(f"🔍 Voice similarity: {score:.3f}  (threshold: {VOICE_AUTH_THRESHOLD})")
    return score >= VOICE_AUTH_THRESHOLD
