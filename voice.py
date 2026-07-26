"""
ElevenLabs text-to-speech for Chillo.

Uses the REST API over ``httpx`` rather than the ``elevenlabs`` SDK: httpx is
already a pinned dependency (the Wikipedia skill uses it), the TTS endpoint is a
single POST, and this keeps the dependency surface small.

Synthesis is cached on the exact text so a Streamlit rerun never re-bills the
same sentence — characters are the metered resource, and the free tier only
grants 10,000 per month.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx
import streamlit as st

API_ROOT = "https://api.elevenlabs.io/v1"
API_KEY_ENV_VARS = ("ELEVENLABS_API_KEY", "ELEVEN_API_KEY")

#: Female voices, verified present on this account. The default is Sarah —
#: mature and reassuring, which suits an assistant that reads answers aloud.
VOICES = {
    "cgSgspJ2msm6clMCkdW9": "Jessica · soft, warm, conversational (default)",
    "EXAVITQu4vr4xnSDxMaL": "Sarah · calm, reassuring",
    "hpp4J3VqNfWAUOO0d1Us": "Bella · bright, friendly",
    "pFZP5JQG7iQjIQuC4Bku": "Lily · velvety, British",
    "Xb7hH8MSUJpSbSDYk0k2": "Alice · clear, British",
    "XrExE9yKIg1WjnnlVkGX": "Matilda · upbeat, knowledgeable",
}
DEFAULT_VOICE = "cgSgspJ2msm6clMCkdW9"

#: Delivery tuning. ElevenLabs defaults sound like narration; these values make
#: it sound like someone talking to you:
#:   stability      lower -> more emotional range. Too low gets unstable.
#:   style          higher -> more expressive inflection.
#:   speed          slightly under 1.0 reads as unhurried and gentle.
#: Kept as a dict so the whole profile can be swapped in one place.
VOICE_SETTINGS = {
    "stability": 0.38,
    "similarity_boost": 0.80,
    "style": 0.45,
    "use_speaker_boost": True,
    "speed": 0.96,
}

#: eleven_v3 is the only model that lists Urdu among its languages (74 vs 29 on
#: multilingual_v2), which matters because Chillo answers in Roman Urdu.
DEFAULT_MODEL = "eleven_v3"
FALLBACK_MODEL = "eleven_multilingual_v2"

#: Verified working on this account. 32 kbps is ~4x smaller on the wire, which
#: matters because the audio is base64-embedded into the page.
OUTPUT_FORMATS = {
    "mp3_44100_128": "High quality (larger)",
    "mp3_22050_32": "Compact (faster to load)",
}
DEFAULT_FORMAT = "mp3_44100_128"

#: Hard ceiling per utterance. Protects the character quota from a runaway
#: long answer; ``assistant_tools.speech_text`` already trims before this.
MAX_CHARS_PER_UTTERANCE = 700

REQUEST_TIMEOUT = 60.0


@dataclass
class Quota:
    """Character allowance for the current billing period."""

    used: int
    limit: int
    tier: str

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    @property
    def fraction_used(self) -> float:
        return min(1.0, self.used / self.limit) if self.limit else 1.0


class VoiceError(RuntimeError):
    """Synthesis failed; the message is safe to show to the user."""


def resolve_api_key() -> str:
    """Return the ElevenLabs key from the environment, secrets, or the sidebar."""
    for var in API_KEY_ENV_VARS:
        value = os.environ.get(var, "").strip()
        if value:
            return value
    try:
        for var in API_KEY_ENV_VARS:
            value = str(st.secrets.get(var, "")).strip()
            if value:
                return value
    except Exception:  # noqa: BLE001 - no secrets file is a normal local case
        pass
    return str(st.session_state.get("eleven_key_input", "")).strip()


def _friendly(status: int, body: str) -> str:
    """Turn an HTTP failure into something worth showing a user."""
    if status == 401:
        return "ElevenLabs rejected the API key. Check it in the control deck."
    if status == 422 and "quota" in body.lower():
        return "ElevenLabs character quota exhausted for this billing period."
    if status == 429:
        return "ElevenLabs rate limit hit. Wait a few seconds and try again."
    if status == 422:
        return f"ElevenLabs rejected the request: {body[:180]}"
    if status >= 500:
        return "ElevenLabs is having server trouble. Try again shortly."
    return f"ElevenLabs error {status}: {body[:180]}"


@st.cache_data(show_spinner=False, ttl=3600, max_entries=64)
def synthesize(text: str, voice_id: str, model_id: str, output_format: str, api_key: str) -> bytes:
    """
    Convert ``text`` to speech and return MP3 bytes.

    Cached on every argument, so re-running the script (which Streamlit does on
    each interaction) replays the same audio instead of buying it twice.

    Raises:
        VoiceError: on any API or transport failure, with a user-safe message.
    """
    clipped = text.strip()[:MAX_CHARS_PER_UTTERANCE]
    if not clipped:
        raise VoiceError("Nothing to speak.")

    try:
        response = httpx.post(
            f"{API_ROOT}/text-to-speech/{voice_id}",
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            params={"output_format": output_format},
            json={
                "text": clipped,
                "model_id": model_id,
                "voice_settings": VOICE_SETTINGS,
            },
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise VoiceError(f"Could not reach ElevenLabs: {exc}") from exc

    if response.status_code != 200:
        # eleven_v3 is newer and may not be enabled on every account; fall back
        # once to the widely available multilingual model before giving up.
        if response.status_code in (400, 403, 422) and model_id != FALLBACK_MODEL:
            return synthesize(clipped, voice_id, FALLBACK_MODEL, output_format, api_key)
        raise VoiceError(_friendly(response.status_code, response.text))

    if not response.content:
        raise VoiceError("ElevenLabs returned empty audio.")
    return response.content


@st.cache_data(show_spinner=False, ttl=120)
def fetch_quota(api_key: str) -> Quota | None:
    """Read the character allowance. Returns None if it cannot be determined."""
    try:
        response = httpx.get(
            f"{API_ROOT}/user/subscription",
            headers={"xi-api-key": api_key},
            timeout=20.0,
        )
        if response.status_code != 200:
            return None
        data = response.json()
        return Quota(
            used=int(data.get("character_count") or 0),
            limit=int(data.get("character_limit") or 0),
            tier=str(data.get("tier") or "unknown"),
        )
    except Exception:  # noqa: BLE001 - quota display must never break the app
        return None
