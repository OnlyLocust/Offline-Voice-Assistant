import hashlib
import os

# ── Vosk Model ────────────────────────────────────────────────────────────────
MODEL_PATH  = r"models\vosk-model-small-hi-0.22"
SAMPLE_RATE = 16000

# ── Wake / Exit Words ─────────────────────────────────────────────────────────
WAKE_WORD = "नमस्ते"
EXIT_WORD = "धन्यवाद"

# ── Authentication ────────────────────────────────────────────────────────────
# PIN: Change this to your desired PIN (e.g. "1234")
# Store only the SHA-256 hash — never the raw PIN.
_RAW_PIN = "1234"   # ← CHANGE THIS before deploying
AUTH_PIN_HASH = hashlib.sha256(_RAW_PIN.encode()).hexdigest()

# Voice profile storage path (relative to project root)
VOICE_PROFILE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "models", "voice_profile"
)

# Cosine similarity threshold for voice match (0.0 – 1.0)
# 0.60 is the practical ceiling for MFCC mean-vector cosine similarity
# between a short PIN utterance and an enrollment phrase.
# Same speaker typically scores 0.55–0.70; different speaker scores < 0.45.
# Raise toward 0.70 only after re-enrolling with the PIN phrase itself.
VOICE_AUTH_THRESHOLD = 0.60

# ── Hindi digit words → numeric value (for PIN spoken in Hindi) ───────────────
HINDI_PIN_WORDS = {
    "शून्य": 0, "zero": 0,
    "एक": 1,   "one": 1,
    "दो": 2,   "two": 2,
    "तीन": 3,  "three": 3,
    "चार": 4,  "four": 4,
    "पांच": 5, "पाँच": 5, "five": 5,
    "छह": 6,   "six": 6,
    "सात": 7,  "seven": 7,
    "आठ": 8,   "eight": 8,
    "नौ": 9,   "nine": 9,
}

# ── Auth State Timeouts (seconds) ─────────────────────────────────────────────
PIN_PROMPT_TIMEOUT  = 15   # seconds to wait for PIN after alarm intent detected
VOICE_AUTH_DURATION = 3.0  # seconds of audio for voice verification

# ── ASR Quality Filters ────────────────────────────────────────────────────────
# Minimum average per-word confidence (0.0 – 1.0) reported by Vosk.
# Utterances whose average confidence falls below this value are silently
# discarded — they are almost certainly background noise or misrecognitions.
# Tune lower (e.g. 0.55) in noisy environments; raise (e.g. 0.80) for
# stricter filtering.  Set to 0.0 to disable the confidence gate entirely.
ASR_CONFIDENCE_THRESHOLD = 0.65

# Minimum number of Unicode characters a word must have to be counted as
# "real speech".  Vosk sometimes hallucinates very short tokens like "अ",
# "आ", "ई" for breath or background sounds.  Any utterance whose EVERY word
# is shorter than this limit is dropped before reaching the state machine.
# Hindi words are typically 2+ characters; 3 is a safe minimum.
# Set to 1 to disable the word-length gate entirely.
ASR_MIN_WORD_LENGTH = 3
