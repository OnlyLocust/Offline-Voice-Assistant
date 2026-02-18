"""
core/state.py — Assistant State Machine Definition
====================================================
Defines the three states the assistant can be in at any time.
"""

from enum import Enum, auto


class State(Enum):
    SLEEPING         = auto()   # Waiting for wake word; ignores all other speech
    ACTIVE           = auto()   # Listening for commands
    AWAITING_PIN     = auto()   # Waiting for user to speak their security PIN
    RECORDING_NOTICE = auto()   # Recording the user's voice notice message
