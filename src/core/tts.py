"""
core/tts.py — Hindi Text-to-Speech (gTTS + pygame)
====================================================
Primary path  : gTTS  → temp MP3  → pygame.mixer playback
Fallback path : Windows SAPI (System.Speech) via PowerShell
               — activated when gTTS/pygame is unavailable.

Temp-file lifecycle
-------------------
1. tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") creates a
   uniquely-named file; we close it immediately so pygame can open it.
2. pygame plays the file; we poll mixer.music.get_busy() instead of
   sleeping a fixed amount — playback ends exactly when the audio ends.
3. Cleanup happens in a finally block so the temp file is ALWAYS removed,
   even if playback raises an exception.

Thread safety
-------------
A threading.Lock() serialises concurrent speak() calls (e.g. the main
callback thread + alarm/timer background threads).  Non-blocking callers
should pass blocking=False to fire-and-forget in a daemon thread.

Usage:
    from core.tts import speak
    speak("नमस्ते!")                 # blocking (default)
    speak("पृष्ठभूमि में", blocking=False)  # fire-and-forget
"""

import os
import time
import tempfile
import threading
import platform
import subprocess
import logging

logger = logging.getLogger(__name__)

# ── Try importing optional TTS/audio dependencies ────────────────────────────
try:
    from gtts import gTTS as _gTTS
    _GTTS_AVAILABLE = True
except ImportError:
    _GTTS_AVAILABLE = False
    logger.warning("gTTS not installed. Hindi TTS will use Windows SAPI fallback.")

try:
    import pygame as _pygame
    _pygame.mixer.init()
    _PYGAME_AVAILABLE = True
except Exception:
    _PYGAME_AVAILABLE = False
    logger.warning("pygame not available. Hindi TTS will use Windows SAPI fallback.")

# Serialise all speak() calls so two threads never play audio simultaneously.
_tts_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _speak_gtts(text: str) -> bool:
    """
    Speak `text` using gTTS → temp MP3 → pygame.

    Returns True on success, False on any failure (caller tries fallback).
    Temp file is always deleted in the finally block.
    """
    if not (_GTTS_AVAILABLE and _PYGAME_AVAILABLE):
        return False

    tmp_path = None
    try:
        # 1. Generate Hindi MP3 into a named temp file.
        #    delete=False so pygame can open it after we close the handle.
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".mp3", prefix="tts_"
        ) as tmp:
            tmp_path = tmp.name   # remember path for cleanup

        tts = _gTTS(text=text, lang="hi", slow=False)
        tts.save(tmp_path)

        # 2. Play via pygame mixer.
        _pygame.mixer.music.load(tmp_path)
        _pygame.mixer.music.play()

        # 3. Wait for playback to finish — no fixed sleep.
        while _pygame.mixer.music.get_busy():
            time.sleep(0.05)

        # 4. Unload so the file handle is released before deletion.
        _pygame.mixer.music.unload()
        return True

    except Exception as exc:
        logger.debug("gTTS/pygame playback failed: %s", exc)
        try:
            # Ensure mixer is stopped before cleanup
            _pygame.mixer.music.stop()
            _pygame.mixer.music.unload()
        except Exception:
            pass
        return False

    finally:
        # Always delete the temp file, even on error.
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass  # if locked briefly, skip — OS will clean it on reboot

    return False  # unreachable, but satisfies the return-type checker


def _speak_sapi(text: str, blocking: bool = True) -> None:
    """
    Fallback TTS using Windows System.Speech (English voice) via PowerShell,
    or espeak-ng on Linux/Pi.

    Note: SAPI does NOT produce correct Hindi pronunciation — it is a
    last-resort fallback used only when gTTS or pygame are unavailable.
    """
    try:
        if platform.system() == "Windows":
            safe = text.replace("'", "\\'").replace('"', '\\"')
            cmd = [
                "powershell", "-NonInteractive", "-Command",
                (
                    "Add-Type -AssemblyName System.Speech; "
                    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    f'$s.Speak("{safe}")'
                ),
            ]
        else:
            cmd = ["espeak-ng", "-v", "hi", text]

        if blocking:
            subprocess.run(
                cmd, check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    except Exception as exc:
        logger.debug("SAPI fallback failed: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def speak(text: str, blocking: bool = True) -> None:
    """
    Speak `text` in Hindi using the best available engine.

    Engine priority
    ---------------
    1. gTTS (online, native Hindi voice)  +  pygame playback
    2. Windows SAPI / espeak-ng (offline, limited Hindi accuracy)

    Args:
        text:     Hindi (Devanagari or Roman) text to speak.
        blocking: If True (default), returns only after audio finishes.
                  If False, starts a daemon thread and returns immediately.
    """
    print(f"🔊 {text}")

    if blocking:
        _do_speak(text)
    else:
        t = threading.Thread(
            target=_do_speak, args=(text,), daemon=True, name="TTSThread"
        )
        t.start()


def _do_speak(text: str) -> None:
    """Acquire TTS lock, try gTTS then SAPI fallback."""
    with _tts_lock:
        try:
            success = _speak_gtts(text)
            if not success:
                _speak_sapi(text, blocking=True)
        except Exception as exc:
            logger.debug("speak() failed entirely: %s", exc)
            # TTS failure must NEVER crash the assistant.
