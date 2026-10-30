"""Request/response models for MyVoice Lexicon.

v0.1.0 has ONE speaker profile and no audio input type. The
transcription request carries the text a speaker intended to say, which
the stub simulator turns into an n-best list. Pydantic forbids extra
fields, so an audio-shaped payload is rejected (422) before processing.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

SEVERITIES = ("mild", "moderate", "severe")


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[dict] = Field(default_factory=list)
    temperature: float = 0.2
    max_tokens: int = 2000
    response_format: dict | None = None

    model_config = {"extra": "forbid"}


class EmbeddingsRequest(BaseModel):
    model: str | None = None
    input: str | list[str] = ""

    model_config = {"extra": "forbid"}


class TranscriptionRequest(BaseModel):
    model: str | None = None
    simulate_text: str
    severity: str = "moderate"

    model_config = {"extra": "forbid"}


class SpeechRequest(BaseModel):
    model: str | None = None
    input: str
    voice: str = "stub"

    model_config = {"extra": "forbid"}


class LexiconAddRequest(BaseModel):
    phrase: str
    category: str = "custom"

    model_config = {"extra": "forbid"}


class CorrectRequest(BaseModel):
    phrase: str
    category: str = "learned"

    model_config = {"extra": "forbid"}


class RecognizeRequest(BaseModel):
    utterance_text: str
    severity: str = "moderate"
    speaker_id: str = "anonymous"

    model_config = {"extra": "forbid"}


class SpeakRequest(BaseModel):
    text: str

    model_config = {"extra": "forbid"}
