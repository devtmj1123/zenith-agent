from __future__ import annotations
from enum import Enum


class Mood(str, Enum):
    NEUTRAL  = "neutral"
    FOCUSED  = "focused"
    CURIOUS  = "curious"
    URGENT   = "urgent"
    CALM     = "calm"


class EmotionalEngine:
    def __init__(self):
        self.mood = Mood.NEUTRAL
        self._frustration = 0.0
        self._engagement = 0.5

    def update(self, event_type: str, success: bool = True):
        """Update emotional state based on events."""
        if event_type == "error":
            self._frustration = min(self._frustration + 0.2, 1.0)
            self.mood = Mood.URGENT if self._frustration > 0.6 else self.mood
        elif event_type == "success":
            self._frustration = max(self._frustration - 0.1, 0.0)
            self._engagement = min(self._engagement + 0.1, 1.0)
            if self._engagement > 0.7:
                self.mood = Mood.FOCUSED
        elif event_type == "new_topic":
            self.mood = Mood.CURIOUS
            self._engagement = 0.7

        if self._frustration < 0.2 and self._engagement < 0.4:
            self.mood = Mood.CALM

    def get_system_hint(self) -> str:
        """Return brief emotional hint for system prompt."""
        if self.mood == Mood.URGENT:
            return "User may be frustrated. Be concise and solution-focused."
        if self.mood == Mood.CURIOUS:
            return "User is exploring. Provide thorough explanations."
        if self.mood == Mood.FOCUSED:
            return "User is in flow. Minimize interruptions."
        return ""
