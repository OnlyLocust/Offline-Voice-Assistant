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
# Raise to 0.85+ for stricter matching; lower to 0.70 for noisy environments
VOICE_AUTH_THRESHOLD = 0.78

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