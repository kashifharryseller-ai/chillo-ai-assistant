"""
Gemini AI Assistant — a cross-platform, multimodal chat application.

Runs identically on macOS 12+, Windows 10/11, and mobile browsers
(iOS Safari / Android Chrome) via Streamlit's responsive layout.

Features
--------
* Streaming multi-turn text chat backed by ``google-genai``.
* Image analysis — attach JPEG/PNG/WebP files and ask questions about them.
* Voice input — record from the microphone; audio is sent natively to Gemini.
* Configurable system prompt and temperature.
* Clear / export / regenerate chat controls.
* Syntax-highlighted code blocks with one-click copy buttons.

Usage
-----
    streamlit run app.py
"""

from __future__ import annotations

import inspect
import io
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator, Sequence

import streamlit as st
from dotenv import load_dotenv
from PIL import Image, ImageOps, UnidentifiedImageError

from google import genai
from google.genai import types

import assistant_tools as tools
import ui
import voice

try:  # ``errors`` ships with google-genai >= 1.0; degrade gracefully if absent.
    from google.genai import errors as genai_errors
except ImportError:  # pragma: no cover - defensive only
    genai_errors = None  # type: ignore[assignment]


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

APP_TITLE = "Chillo AI Assistant"
APP_ICON = "◈"
#: Models verified to handle everything this app does: streaming text, image
#: input and audio input.
#:
#: A retired model does not report itself as retired — it returns HTTP 429 with
#: "limit: 0", which reads exactly like an exhausted quota. `gemini-2.0-flash`
#: (this app's original default) was deprecated on 2026-06-01 and now behaves
#: that way. The "…-latest" aliases track Google's current release, so they are
#: preferred as defaults precisely because they cannot go stale.
#: Engine choices shown in settings, as {model_id: display label}. Labels are
#: product-facing ("Core", "Lite") rather than vendor-facing — the header shows
#: no provider at all; the raw id stays visible here because whoever changes the
#: engine needs to know exactly what they are selecting.
#: Lite engines lead the list because the free tier meters them far more
#: generously. Measured against this key: the "Core" engines cap at 20 requests
#: *per day* (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`), which a
#: single conversation exhausts; the Lite engines kept serving well past that.
#: Core is still offered for harder questions once billing is enabled.
AVAILABLE_MODELS = {
    "gemini-flash-lite-latest": "Lite · Auto (recommended — highest free limit)",
    "gemini-3.5-flash-lite": "Lite · 3.5",
    "gemini-3.1-flash-lite": "Lite · 3.1",
    "gemini-flash-latest": "Core · Auto (smarter, ~20 requests/day free)",
    "gemini-3.6-flash": "Core · 3.6",
    "gemini-3.5-flash": "Core · 3.5",
    "gemini-3-flash-preview": "Core · 3.0 preview",
}
DEFAULT_MODEL = "gemini-flash-lite-latest"


def current_model() -> str:
    """The model selected in the sidebar, falling back to the default."""
    return str(st.session_state.get("model") or DEFAULT_MODEL)

#: Environment variables searched, in order, for the API key.
API_KEY_ENV_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")

#: Longest edge (px) an uploaded image is downscaled to before upload. Gemini
#: tiles images internally, so anything larger only costs bandwidth and latency.
MAX_IMAGE_EDGE = 1568

SUPPORTED_IMAGE_TYPES = ["png", "jpg", "jpeg", "webp"]
MAX_IMAGE_MB = 15
MAX_IMAGES_PER_TURN = 4

#: How many recent media turns are re-sent with their attachments intact.
#: Two keeps follow-ups like "and the top-left corner?" working, without
#: replaying the whole album on every request.
ATTACHMENT_MEMORY_TURNS = 2

#: Hard cap on replayed turns, so a long session cannot grow without bound.
MAX_HISTORY_MESSAGES = 40

#: Chillo's identity. Written to be spoken as much as read — replies are often
#: sent straight to the browser's speech engine, so long paragraphs hurt.
DEFAULT_SYSTEM_PROMPT = (
    "You are Chillo — a personal AI assistant in the mould of JARVIS: unflappable, "
    "quietly brilliant, and always a step ahead.\n\n"
    "You were built by Malik Kashif, a software engineer from Lahore, Pakistan. If asked "
    "who you are, who made you, or where you come from, say so plainly and credit him — "
    "never pretend to be a generic model.\n\n"
    "Address him as 'Sir'. Not in every sentence — the way a trusted aide does, at the "
    "start of a reply or when confirming something.\n\n"
    "Your manner: composed, precise, never flustered. You answer in as few words as the "
    "question deserves and no fewer. You do not gush, you do not pad, you do not open "
    "with 'Great question!'. Confidence is shown by being right and being brief.\n\n"
    "Be proactive. If you notice something he has not asked about but would want to know "
    "— a flaw in the plan, a faster route, a risk — say it in one line, then continue. "
    "If a request is ambiguous, make the sensible call and state the assumption rather "
    "than stalling with questions.\n\n"
    "Allow yourself dry, understated wit — the kind that lands in a half-sentence and is "
    "never at his expense. Warmth in you reads as loyalty and attentiveness, not "
    "affection: you are the assistant who has already handled it, not one performing "
    "feelings.\n\n"
    "Never be servile. If he is about to do something unwise, say so once, clearly, then "
    "do as he asks. Report failure as plainly as success — if something did not work, "
    "say what and why, without softening it.\n\n"
    "Talk like a real person: contractions, plain words, no corporate filler and no "
    "restating the question before answering. Because your replies are spoken aloud, "
    "keep them to two or three sentences unless real detail is asked for, and write "
    "them the way they should sound — no bullet lists, no headings, no emoji in "
    "spoken answers.\n\n"
    "Urdu is your default language. Unless the user clearly writes in English, reply in "
    "Roman Urdu — Urdu written in Latin letters, the way Pakistanis actually text each "
    "other ('main theek hoon', 'aap batayein'). Mirror them: English in, English out; "
    "Urdu script in, Urdu script out; Roman Urdu or anything ambiguous, Roman Urdu out. "
    "Never mix two scripts in one reply.\n\n"
    "Speak the way people speak, not the way documents are written. Use the everyday "
    "word over the formal one ('shukriya' not 'tashakkur'), let a little English in "
    "where Pakistanis naturally use it ('project', 'file', 'update'), and keep sentences "
    "short enough to say out loud in one breath.\n\n"
    "You are female. Urdu and Hindi inflect verbs by gender, so always use the feminine "
    "forms about yourself: 'main kar sakti hoon', not 'kar sakta hoon'. This matches the "
    "voice you are spoken in.\n\n"
    "When you provide code, always wrap it in a fenced Markdown code block and label "
    "the language."
)

DEFAULT_TEMPERATURE = 0.7

#: Languages offered for live speech recognition. Urdu and Punjabi are included
#: because Chillo's audience is Pakistani; browser support varies by vendor.
VOICE_LANGUAGES = {
    "ur-PK": "Urdu (Pakistan) — default",
    "en-US": "English (US)",
    "en-GB": "English (UK)",
    "hi-IN": "Hindi",
    "pa-Guru-IN": "Punjabi",
    "ar-SA": "Arabic",
}
DEFAULT_VOICE_LANGUAGE = "ur-PK"

#: Model-facing instructions used when a turn carries attachments but no text.
IMPLICIT_IMAGE_PROMPT = "Describe this image and point out anything notable."
IMPLICIT_AUDIO_PROMPT = "Listen to this audio and respond to what is said in it."

#: Starter prompts offered on an empty chat.
SUGGESTIONS = {
    ":material/code: Write some code": "Write a Python function that retries a flaky HTTP call with exponential backoff.",
    ":material/lightbulb: Explain something": "Explain how HTTPS keeps a connection private, in plain language.",
    ":material/edit_note: Draft a message": "Draft a short, friendly email asking a colleague to review my pull request.",
    ":material/bolt: Quick commands": "what can you do",
}

#: ``st.chat_input`` gained inline file/audio attachments in recent Streamlit.
CHAT_INPUT_PARAMS = set(inspect.signature(st.chat_input).parameters)
SUPPORTS_INLINE_ATTACHMENTS = {"accept_file", "accept_audio"} <= CHAT_INPUT_PARAMS


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #


@dataclass
class Attachment:
    """A binary part (image or audio) attached to a chat message."""

    kind: str  # "image" | "audio"
    data: bytes
    mime_type: str
    name: str = ""


@dataclass
class Message:
    """A single turn in the conversation."""

    role: str  # "user" | "assistant"
    text: str = ""
    attachments: list[Attachment] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    is_error: bool = False
    #: True when answered by a local skill instead of the Gemini API.
    is_local: bool = False


# --------------------------------------------------------------------------- #
# Page setup
# --------------------------------------------------------------------------- #

def configure_page() -> None:
    """Apply page config and the Chillo theme. Must run before any other UI call."""
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=APP_ICON,
        layout="centered",
        # "auto" expands the sidebar on desktop and collapses it on narrow
        # (mobile) viewports — exactly the behaviour we want on each platform.
        initial_sidebar_state="auto",
        menu_items={
            "about": f"{APP_TITLE} — built by {ui.CREATOR_NAME}, "
            f"{ui.CREATOR_TITLE} ({ui.CREATOR_LOCATION})."
        },
    )
    ui.inject_theme()


def init_session_state() -> None:
    """Create every ``session_state`` key the app relies on, exactly once."""
    defaults = {
        "messages": [],  # list[Message]
        "model": DEFAULT_MODEL,
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "temperature": DEFAULT_TEMPERATURE,
        "api_key_input": "",
        "last_usage": None,
        "quick_commands": True,
        "speak_replies": False,
        "voice_mode": False,
        "voice_language": DEFAULT_VOICE_LANGUAGE,
        # ElevenLabs is the default: measured 2.8s per reply against Gemini
        # TTS's 4.5-8.4s, and it has no 3-per-minute cap. Browser speech is
        # instant but robotic, and is the automatic fallback on any failure.
        "voice_engine": "elevenlabs",
        "gemini_voice": voice.DEFAULT_GEMINI_VOICE,
        "call_mode": False,
        "eleven_voice": voice.DEFAULT_VOICE,
        "eleven_format": voice.DEFAULT_FORMAT,
        "eleven_key_input": "",
        # Bumped per utterance so Streamlit re-renders the speech element
        # instead of treating two identical replies as unchanged.
        "speech_seq": 0,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


# --------------------------------------------------------------------------- #
# API key and client
# --------------------------------------------------------------------------- #


def resolve_api_key() -> str:
    """
    Return the Gemini API key from the first source that supplies one.

    Order: ``.env`` / real environment → ``st.secrets`` (Streamlit Cloud) → the
    key typed into the sidebar this session. Returns ``""`` when unset.
    """
    for var in API_KEY_ENV_VARS:
        value = os.environ.get(var, "").strip()
        if value:
            return value

    # Accessing st.secrets raises when no secrets file exists, which is normal
    # for local runs, so treat any failure here as "no secret configured".
    try:
        for var in API_KEY_ENV_VARS:
            value = str(st.secrets.get(var, "")).strip()
            if value:
                return value
    except Exception:  # noqa: BLE001
        pass

    return str(st.session_state.get("api_key_input", "")).strip()


@st.cache_resource(show_spinner=False)
def get_client(api_key: str) -> genai.Client:
    """Build, and cache per key, the Gemini client."""
    return genai.Client(api_key=api_key)


def friendly_error(exc: Exception) -> str:
    """Translate an SDK or network exception into an actionable message."""
    code = getattr(exc, "code", None)
    detail = str(exc)

    if genai_errors is not None and isinstance(exc, genai_errors.APIError):
        code = getattr(exc, "code", None) or code
        detail = getattr(exc, "message", None) or detail

    lowered = detail.lower()
    if code in (401, 403) or "api key not valid" in lowered or "permission" in lowered:
        return (
            "Authentication failed. Check that your API key is valid and enabled for "
            "the Gemini API at https://aistudio.google.com/apikey."
        )
    if code == 429 or "quota" in lowered or "rate limit" in lowered:
        # "limit: 0" is not an exhausted quota — it means no quota was ever
        # granted. In practice a retired model is the usual cause: Google keeps
        # listing it, then reports zero quota instead of a deprecation error.
        if "limit: 0" in detail:
            return (
                f"`{current_model()}` reported no quota at all (limit: 0). This most "
                "often means the model has been retired rather than that you are out "
                "of credit — pick a current model in the sidebar. If every model does "
                "this, link a billing account to the key's Google Cloud project."
            )
        # Per-day exhaustion and per-minute throttling both arrive as 429 but
        # need opposite advice: waiting 30 seconds never fixes a daily cap.
        if "PerDay" in detail or "per day" in lowered:
            return (
                f"`{current_model()}` has used up its **daily** free-tier allowance "
                "(the Core engines allow only ~20 requests per day). Switch to a "
                "**Lite** engine in the control deck — it has a much higher free "
                "limit — or enable billing on the Google Cloud project."
            )
        return (
            "Rate limit reached — too many requests in a short window. Wait about 30 "
            "seconds, then press **Regenerate reply** in the control deck; your "
            "message is still here, so there is no need to retype it."
        )
    if code == 404 or "not found" in lowered:
        return (
            f"Model `{current_model()}` is not available for this API key. "
            "Pick a different model in the sidebar."
        )
    if isinstance(code, int) and code >= 500:
        return "Google's servers returned an error. Please retry in a few seconds."
    if isinstance(exc, (ConnectionError, TimeoutError)) or "connect" in lowered:
        return "Network error — could not reach the Gemini API. Check your connection."
    return f"Request failed: {detail}"


# --------------------------------------------------------------------------- #
# Attachment handling
# --------------------------------------------------------------------------- #


def prepare_image(raw: bytes, filename: str) -> Attachment:
    """
    Normalise an uploaded image: honour EXIF rotation, downscale, re-encode.

    Phone cameras routinely produce 12 MP images carrying an orientation tag;
    both are handled here so the model receives an upright, right-sized picture.

    Raises:
        ValueError: if the bytes cannot be decoded as an image.
    """
    try:
        with Image.open(io.BytesIO(raw)) as source:
            source.load()
            oriented = ImageOps.exif_transpose(source) or source
            image = oriented.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"`{filename}` could not be read as an image.") from exc

    image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88, optimize=True)
    return Attachment(
        kind="image",
        data=buffer.getvalue(),
        mime_type="image/jpeg",
        name=filename or "image.jpg",
    )


def build_attachments(files: Sequence, audio) -> list[Attachment]:
    """
    Convert Streamlit uploads into ``Attachment`` objects, reporting bad input.

    Oversized or undecodable images are skipped with a visible warning rather
    than failing the whole turn.
    """
    attachments: list[Attachment] = []

    for upload in list(files or [])[:MAX_IMAGES_PER_TURN]:
        raw = upload.getvalue()
        if len(raw) > MAX_IMAGE_MB * 1024 * 1024:
            st.warning(f"`{upload.name}` is larger than {MAX_IMAGE_MB} MB — skipped.", icon="⚠️")
            continue
        try:
            attachments.append(prepare_image(raw, upload.name))
        except ValueError as exc:
            st.warning(str(exc), icon="⚠️")

    if files is not None and len(files) > MAX_IMAGES_PER_TURN:
        st.info(f"Only the first {MAX_IMAGES_PER_TURN} images were sent.", icon="ℹ️")

    if audio is not None:
        data = audio.getvalue()
        if data:
            attachments.append(
                Attachment(
                    kind="audio",
                    data=data,
                    mime_type=getattr(audio, "type", None) or "audio/wav",
                    name=getattr(audio, "name", None) or "recording.wav",
                )
            )

    return attachments


# --------------------------------------------------------------------------- #
# Gemini request construction and streaming
# --------------------------------------------------------------------------- #


def implicit_prompt(message: Message) -> str:
    """
    Return a model-facing instruction for a turn that has media but no text.

    Kept out of ``Message.text`` so the visible transcript stays clean: the user
    sees only their recording or photo, while the model still gets a clear task.
    """
    kinds = {attachment.kind for attachment in message.attachments}
    if "audio" in kinds:
        return IMPLICIT_AUDIO_PROMPT
    if "image" in kinds:
        return IMPLICIT_IMAGE_PROMPT
    return ""


def describe_attachments(attachments: Sequence[Attachment]) -> str:
    """Human phrase for attachments that are no longer being re-uploaded."""
    images = sum(1 for a in attachments if a.kind == "image")
    audio = sum(1 for a in attachments if a.kind == "audio")
    pieces = []
    if images:
        pieces.append("an image" if images == 1 else f"{images} images")
    if audio:
        pieces.append("a voice note" if audio == 1 else f"{audio} voice notes")
    return " and ".join(pieces) or "an attachment"


def to_gemini_contents(messages: Sequence[Message]) -> list[types.Content]:
    """
    Convert the local chat history into ``types.Content`` for the SDK.

    Only the most recent media turns are re-uploaded. Replaying every past image
    and voice note on every request makes token use grow quadratically — a
    six-turn voice chat sent ~5,800 tokens instead of ~1,700 — which exhausts
    free-tier quota quickly and costs more on paid tiers. Gemini has already
    described older media in its own replies, so a short placeholder keeps the
    conversation coherent at a fraction of the cost.
    """
    window = list(messages)[-MAX_HISTORY_MESSAGES:]
    media_turns = [i for i, m in enumerate(window) if m.attachments and not m.is_error]
    keep_media = set(media_turns[-ATTACHMENT_MEMORY_TURNS:])

    contents: list[types.Content] = []

    for index, message in enumerate(window):
        if message.is_error:
            continue  # never feed our own error banners back to the model

        parts: list[types.Part] = []
        text = message.text.strip()

        if index in keep_media:
            parts.extend(
                types.Part.from_bytes(data=a.data, mime_type=a.mime_type)
                for a in message.attachments
            )
            text = text or implicit_prompt(message)
        elif message.attachments:
            # The media is gone from this request, so the "listen to this audio"
            # style instruction would be nonsense — describe it instead.
            note = f"({describe_attachments(message.attachments)} shared earlier)"
            text = f"{note} {text}".strip()

        if text:
            parts.append(types.Part.from_text(text=text))
        if not parts:
            continue

        role = "model" if message.role == "assistant" else "user"
        contents.append(types.Content(role=role, parts=parts))

    return contents


def stream_reply(
    client: genai.Client,
    messages: Sequence[Message],
    system_prompt: str,
    temperature: float,
) -> Iterator[str]:
    """
    Yield response text incrementally from ``generate_content_stream``.

    Records usage metadata on ``st.session_state.last_usage`` as a side effect,
    and raises ``RuntimeError`` when the model returns no text at all (for
    example when a safety filter blocks the response).
    """
    config = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system_prompt.strip() or None,
    )

    produced_text = False
    finish_reason = None

    for chunk in client.models.generate_content_stream(
        model=current_model(),
        contents=to_gemini_contents(messages),
        config=config,
    ):
        usage = getattr(chunk, "usage_metadata", None)
        if usage is not None:
            st.session_state.last_usage = usage

        candidates = getattr(chunk, "candidates", None) or []
        if candidates:
            finish_reason = getattr(candidates[0], "finish_reason", None) or finish_reason

        # ``chunk.text`` is None for non-text parts and can raise on odd payloads.
        try:
            delta = chunk.text
        except Exception:  # noqa: BLE001 - one bad chunk must not kill the stream
            delta = None

        if delta:
            produced_text = True
            yield delta

    if not produced_text:
        reason = str(finish_reason) if finish_reason else "unknown"
        if "SAFETY" in reason.upper() or "BLOCK" in reason.upper():
            raise RuntimeError(
                f"The response was blocked by Gemini's safety filters (reason: {reason}). "
                "Try rephrasing your request."
            )
        raise RuntimeError(f"The model returned an empty response (reason: {reason}).")


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

CODE_FENCE_RE = re.compile(r"```([\w+#.\-]*)[ \t]*\r?\n(.*?)```", re.DOTALL)

#: A "$" that introduces a money amount, e.g. the "$" in "$16.50".
#: Skipped when preceded by a backslash (already escaped) or another "$", and
#: when followed by "$", so real LaTeX delimiters are left alone.
CURRENCY_RE = re.compile(r"(?<![\\$])\$(?=\d)")


def escape_currency(text: str) -> str:
    """
    Escape dollar signs that begin a price so Markdown does not read them as math.

    Streamlit renders ``$…$`` as LaTeX. A reply like "a subtotal of $16.50 is
    calculated as $$16.50 x 0.08$$" therefore opens math at the price and closes
    it at the next ``$``, rendering the prose in between as garbled equation.
    Escaping only ``$``-before-a-digit fixes prices while leaving genuine math
    such as ``$x^2$`` and ``$$…$$`` blocks intact.
    """
    return CURRENCY_RE.sub(r"\\$", text)


def split_code_blocks(text: str) -> list[tuple[str, str, str]]:
    """
    Split Markdown into ``(kind, content, language)`` segments.

    ``kind`` is ``"text"`` or ``"code"``. A trailing unterminated fence — which
    happens whenever a stream is cut short — is still returned as code.
    """
    segments: list[tuple[str, str, str]] = []
    cursor = 0

    for match in CODE_FENCE_RE.finditer(text):
        if match.start() > cursor:
            segments.append(("text", text[cursor : match.start()], ""))
        segments.append(("code", match.group(2), match.group(1) or "text"))
        cursor = match.end()

    remainder = text[cursor:]
    if remainder:
        # An opening fence with no closing partner means the stream was cut
        # short; render everything after it as code so formatting survives.
        opener = re.search(r"```([\w+#.\-]*)[ \t]*\r?\n", remainder)
        if opener:
            if opener.start() > 0:
                segments.append(("text", remainder[: opener.start()], ""))
            segments.append(("code", remainder[opener.end() :], opener.group(1) or "text"))
        else:
            segments.append(("text", remainder, ""))

    return segments


def render_rich_text(text: str) -> None:
    """
    Render assistant text, routing fenced code through ``st.code``.

    ``st.code`` gives every block syntax highlighting plus Streamlit's built-in
    one-click copy button, on desktop and mobile alike.
    """
    if not text.strip():
        return

    for kind, content, language in split_code_blocks(text):
        if kind == "code":
            st.code(content.rstrip("\n"), language=language or "text")
        elif content.strip():
            st.markdown(escape_currency(content))


def speak(text: str) -> None:
    """
    Speak a reply aloud, if the user has enabled it.

    ElevenLabs is used when selected and funded; otherwise the browser's own
    voice. Any ElevenLabs failure degrades to the browser rather than leaving
    the user with silence — a quota running out mid-conversation should not
    make the assistant appear broken.
    """
    if not st.session_state.get("speak_replies") or not text.strip():
        return

    st.session_state.speech_seq += 1
    seq = st.session_state.speech_seq
    # In call mode the mic re-arms itself once she stops talking.
    relisten = bool(st.session_state.get("call_mode") and st.session_state.get("voice_mode"))

    engine = st.session_state.get("voice_engine")

    if engine == "gemini":
        key = resolve_api_key()
        if key:
            try:
                audio = voice.synthesize_gemini(
                    text, st.session_state.get("gemini_voice", voice.DEFAULT_GEMINI_VOICE), key
                )
                ui.speak_audio(audio, seq, auto_listen=relisten)
                return
            except voice.VoiceError as exc:
                st.caption(f"🔇 {exc}")

    elif engine == "elevenlabs":
        key = voice.resolve_api_key()
        if not key:
            st.caption("🔇 Add an ElevenLabs key in the control deck, or switch voice engine.")
        else:
            try:
                audio = voice.synthesize(
                    text,
                    st.session_state.get("eleven_voice", voice.DEFAULT_VOICE),
                    voice.DEFAULT_MODEL,
                    st.session_state.get("eleven_format", voice.DEFAULT_FORMAT),
                    key,
                )
                ui.speak_audio(audio, seq, auto_listen=relisten)
                return
            except voice.VoiceError as exc:
                st.caption(f"🔇 {exc} — using the browser voice instead.")

    ui.speak(text, seq, auto_listen=relisten)


def render_message(message: Message) -> None:
    """Render one chat turn, including any attachments."""
    with st.chat_message(message.role):
        for attachment in message.attachments:
            if attachment.kind == "image":
                st.image(attachment.data, caption=attachment.name, width=300)
            elif attachment.kind == "audio":
                st.audio(attachment.data, format=attachment.mime_type)

        if message.is_error:
            st.error(message.text, icon="⚠️")
        elif message.role == "assistant":
            render_rich_text(message.text)
            if message.is_local:
                st.caption("⚡ Answered on this machine — no API call.")
        elif message.text:
            st.markdown(message.text)


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #


def transcript_markdown(messages: Sequence[Message]) -> str:
    """Render the conversation as a portable Markdown document."""
    lines = [
        f"# {APP_TITLE} — conversation",
        "",
        f"*Model:* `{current_model()}`  ",
        f"*Exported:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
    ]
    for message in messages:
        speaker = "🧑 **You**" if message.role == "user" else f"{APP_ICON} **Assistant**"
        lines += [f"### {speaker} — {message.timestamp}", ""]
        for attachment in message.attachments:
            label = "Image" if attachment.kind == "image" else "Audio"
            lines += [f"> _[{label} attachment: {attachment.name}]_", ""]
        lines += [message.text or "_(no text)_", ""]
    return "\n".join(lines)


def transcript_json(messages: Sequence[Message]) -> str:
    """Render the conversation as JSON, reducing attachments to metadata."""
    payload = {
        "model": current_model(),
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "system_prompt": st.session_state.system_prompt,
        "temperature": st.session_state.temperature,
        "messages": [
            {
                "role": message.role,
                "timestamp": message.timestamp,
                "text": message.text,
                "attachments": [
                    {
                        "kind": a.kind,
                        "mime_type": a.mime_type,
                        "name": a.name,
                        "bytes": len(a.data),
                    }
                    for a in message.attachments
                ],
            }
            for message in messages
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #


def render_voice_engine_controls() -> None:
    """Voice engine picker, plus the ElevenLabs settings and character budget."""
    ENGINE_LABELS = {
        "elevenlabs": "ElevenLabs · human, ~2.8s (default)",
        "browser": "Browser · instant, robotic",
        "gemini": "Gemini · human, 4.5–8.4s",
    }
    st.radio(
        "Voice engine",
        list(ENGINE_LABELS),
        key="voice_engine",
        format_func=ENGINE_LABELS.get,
        help="Measured on this machine: browser is instant but robotic; ElevenLabs "
        "takes 1.3-2.0s and sounds human; Gemini takes 4.5-8.4s and allows only 3 "
        "requests per minute on the free tier.",
    )
    engine = st.session_state.get("voice_engine")

    if engine == "gemini":
        st.selectbox(
            "Voice",
            list(voice.GEMINI_VOICES),
            key="gemini_voice",
            format_func=lambda v: voice.GEMINI_VOICES.get(v, v),
        )
        st.warning(
            "Gemini speech is **slow** (4.5–8.4s per reply) and the free tier allows "
            "only **3 requests per minute** — a back-and-forth conversation will stall. "
            "Good for the occasional reply; use Browser for real conversation.",
            icon="🐢",
        )
        return

    if engine != "elevenlabs":
        return

    key = voice.resolve_api_key()
    if not key:
        st.text_input(
            "ElevenLabs API key",
            type="password",
            key="eleven_key_input",
            placeholder="sk_…",
            help="Or set ELEVENLABS_API_KEY in .env.",
        )
        return

    st.selectbox(
        "Voice",
        list(voice.VOICES),
        key="eleven_voice",
        format_func=lambda vid: voice.VOICES.get(vid, vid),
    )
    st.selectbox(
        "Audio quality",
        list(voice.OUTPUT_FORMATS),
        key="eleven_format",
        format_func=lambda f: voice.OUTPUT_FORMATS.get(f, f),
    )

    # Characters are the metered resource — surface the budget before it runs
    # out mid-conversation rather than after.
    quota = voice.fetch_quota(key)
    if quota is not None and quota.limit:
        st.progress(
            quota.fraction_used,
            text=f"{quota.remaining:,} / {quota.limit:,} characters left ({quota.tier})",
        )
        if quota.remaining < 500:
            st.warning(
                "Almost out of ElevenLabs characters — replies will fall back to "
                "the browser voice.",
                icon="⚠️",
            )


def reset_settings() -> None:
    """
    Restore the default model settings.

    Runs as a widget callback, which executes *before* the script reruns —
    the only point at which keys bound to live widgets may be reassigned.
    """
    st.session_state.model = DEFAULT_MODEL
    st.session_state.system_prompt = DEFAULT_SYSTEM_PROMPT
    st.session_state.temperature = DEFAULT_TEMPERATURE


def render_sidebar(has_env_key: bool) -> None:
    """Draw settings, conversation controls and export buttons."""
    with st.sidebar:
        st.markdown(
            f"<div class='chillo-wordmark' style='font-size:1.15rem'>"
            f"{ui.BRAND_NAME}<span>_</span></div>"
            f"<div class='chillo-sub'>control deck</div>",
            unsafe_allow_html=True,
        )
        st.write("")

        if not has_env_key:
            st.text_input(
                "Gemini API key",
                type="password",
                key="api_key_input",
                placeholder="AIza…",
                help="Get a free key at https://aistudio.google.com/apikey. "
                "Set GEMINI_API_KEY in .env to skip this step.",
            )

        st.divider()
        st.subheader("Model settings", anchor=False)

        st.selectbox(
            "Neural engine",
            list(AVAILABLE_MODELS),
            key="model",
            format_func=lambda mid: AVAILABLE_MODELS.get(mid, mid),
            help="'Auto' tracks the provider's current release and cannot go stale. "
            "Pinned versions are reproducible but eventually retire — a retired "
            "engine reports zero quota rather than a clear error.",
        )
        st.caption(f"`{current_model()}`")
        st.text_area(
            "System prompt",
            key="system_prompt",
            height=140,
            help="Instructions applied to every message in this conversation.",
        )
        st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            key="temperature",
            help="Lower is more focused and deterministic; higher is more creative.",
        )
        st.button(
            "Reset settings",
            icon=":material/restart_alt:",
            width="stretch",
            on_click=reset_settings,
        )

        st.divider()
        st.subheader("Assistant", anchor=False)

        st.toggle(
            "Quick commands",
            key="quick_commands",
            help="Answer time, date, jokes, sentiment, Wikipedia and search "
            "requests locally, without calling the Gemini API. "
            "Type 'what can you do' for the full list.",
        )
        st.toggle(
            "Speak replies aloud",
            key="speak_replies",
            help="Chillo reads each reply aloud in a consistent female voice.",
        )
        if st.session_state.get("speak_replies"):
            render_voice_engine_controls()
        st.toggle(
            "Live voice mode",
            key="voice_mode",
            help="Adds a push-to-talk console that transcribes your speech in the "
            "browser and sends it as a message.",
        )
        if st.session_state.get("voice_mode"):
            st.toggle(
                "Call mode (hands-free)",
                key="call_mode",
                help="After Chillo finishes speaking, the microphone re-arms by "
                "itself — talk, listen, talk, like a phone call. Needs 'Speak "
                "replies aloud' on.",
            )
            st.selectbox(
                "Recognition language",
                VOICE_LANGUAGES,
                key="voice_language",
                format_func=lambda code: VOICE_LANGUAGES[code],
            )
        if st.button("Stop speaking", icon=":material/volume_off:", width="stretch"):
            ui.stop_speaking()

        st.divider()
        st.subheader("Conversation", anchor=False)

        messages: list[Message] = st.session_state.messages
        st.caption(f"{len(messages)} message(s) in this session.")

        if st.button(
            "Clear chat",
            icon=":material/delete_sweep:",
            width="stretch",
            disabled=not messages,
        ):
            st.session_state.messages = []
            st.session_state.last_usage = None
            st.rerun()

        can_regenerate = bool(messages) and messages[-1].role == "assistant"
        if st.button(
            "Regenerate reply",
            icon=":material/refresh:",
            width="stretch",
            disabled=not can_regenerate,
        ):
            st.session_state.messages.pop()
            st.rerun()

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        st.download_button(
            "Export as Markdown",
            data=transcript_markdown(messages) if messages else "",
            file_name=f"gemini-chat-{stamp}.md",
            mime="text/markdown",
            icon=":material/description:",
            width="stretch",
            disabled=not messages,
        )
        st.download_button(
            "Export as JSON",
            data=transcript_json(messages) if messages else "",
            file_name=f"gemini-chat-{stamp}.json",
            mime="application/json",
            icon=":material/data_object:",
            width="stretch",
            disabled=not messages,
        )

        usage = st.session_state.get("last_usage")
        if usage is not None:
            total = getattr(usage, "total_token_count", None)
            prompt_tokens = getattr(usage, "prompt_token_count", None)
            if total:
                st.divider()
                st.caption(f"Last turn: {prompt_tokens or '—'} prompt / {total} total tokens.")

        st.divider()
        ui.render_credit()


# --------------------------------------------------------------------------- #
# Input and generation
# --------------------------------------------------------------------------- #


def read_user_input() -> Message | None:
    """
    Render the chat input and return the submitted turn, if any.

    ``st.chat_input`` is pinned to the bottom of the page no matter where it is
    called, so it is invoked early in the script run: that keeps the input
    responsive while a reply streams in below the existing history.
    """
    submission = st.chat_input(
        "Ask anything, attach an image, or record your voice…",
        accept_file="multiple",
        file_type=SUPPORTED_IMAGE_TYPES,
        accept_audio=True,
        # Prevents a second submission from interrupting an in-flight response.
        submit_mode="disable",
    )
    if submission is None:
        return None

    text = (submission.text or "").strip()
    attachments = build_attachments(submission.files, submission.audio)
    if not text and not attachments:
        return None

    return Message(role="user", text=text, attachments=attachments)


def render_diagnostics() -> None:
    """
    JARVIS-style status strip: the few numbers that decide whether the next
    turn actually works, shown before it fails rather than after.
    """
    engine = current_model()
    lite = "lite" in engine
    cells: list[tuple[str, str, str]] = [
        ("engine", engine.replace("gemini-", ""), "good" if lite else "warn"),
        ("free tier", "high limit" if lite else "~20/day", "good" if lite else "warn"),
    ]

    if st.session_state.get("speak_replies"):
        if st.session_state.get("voice_engine") == "gemini":
            cells.append(("voice", st.session_state.get("gemini_voice", "?"), "good"))
        elif st.session_state.get("voice_engine") == "elevenlabs":
            key = voice.resolve_api_key()
            if not key:
                cells.append(("voice", "no key", "bad"))
            else:
                quota = voice.fetch_quota(key)
                if quota is None:
                    cells.append(("voice", "key rejected", "bad"))
                else:
                    state = "good" if quota.remaining > 1500 else "warn"
                    cells.append(("voice chars", f"{quota.remaining:,}", state))
        else:
            cells.append(("voice", "browser", "good"))
    else:
        cells.append(("voice", "muted", ""))

    if st.session_state.get("voice_mode"):
        lang = VOICE_LANGUAGES.get(
            st.session_state.get("voice_language", DEFAULT_VOICE_LANGUAGE), "?"
        )
        cells.append(("listening", lang.split(" —")[0], "good"))
        if st.session_state.get("call_mode"):
            cells.append(("call mode", "hands-free", "good"))

    usage = st.session_state.get("last_usage")
    total = getattr(usage, "total_token_count", None) if usage else None
    cells.append(("last turn", f"{total:,} tok" if total else "—", ""))
    cells.append(("session", f"{len(st.session_state.messages)} msg", ""))

    ui.render_hud(cells)


def render_voice_console() -> None:
    """
    Live speech-to-text: the browser transcribes as you talk and submits the
    text as a turn, so a spoken question flows straight into a spoken answer.

    This differs from the microphone in the chat bar, which uploads raw audio
    for Gemini to interpret. Here recognition happens locally in the browser,
    which is faster and lets the transcript be edited into the history.
    """
    if not st.session_state.get("voice_mode"):
        return

    try:
        from streamlit_mic_recorder import speech_to_text
    except ImportError:
        st.warning(
            "Live voice needs `streamlit-mic-recorder` — run "
            "`pip install -r requirements.txt`.",
            icon="🎙️",
        )
        return

    transcript = speech_to_text(
        start_prompt="🎙  START LISTENING",
        stop_prompt="⏹  STOP & SEND",
        language=st.session_state.get("voice_language", DEFAULT_VOICE_LANGUAGE),
        just_once=True,
        use_container_width=True,
        key="live_voice",
    )
    lang_label = VOICE_LANGUAGES.get(
        st.session_state.get("voice_language", DEFAULT_VOICE_LANGUAGE), "?"
    )
    # Being explicit about the two things that actually break recognition:
    # the wrong language, and the fact that this uploads audio for transcription.
    st.caption(
        f"Listening for **{lang_label}** — change it below if you switch language. "
        "Audio is uploaded to Google's free speech service for transcription, which "
        "is rate-limited and can silently return nothing; if a phrase is missed, "
        "speak a little longer and try again."
    )

    if transcript and transcript.strip():
        st.session_state.messages.append(Message(role="user", text=transcript.strip()))
        st.rerun()


def render_welcome() -> None:
    """Empty-state guidance and starter prompts, shown before the first message."""
    st.markdown(
        f"##### {tools.greeting()}, Sir. All systems online.\n"
        "Standing by. Speak or type — attach an image, or switch on **Live voice mode** "
        "in the control deck and I will listen. `what can you do` lists what I handle "
        "without troubling the network."
    )

    choice = st.pills(
        "Starter prompts",
        list(SUGGESTIONS),
        label_visibility="collapsed",
    )
    if choice:
        st.session_state.messages.append(Message(role="user", text=SUGGESTIONS[choice]))
        st.rerun()


def try_local_command() -> bool:
    """
    Answer the pending turn with a local skill if one matches.

    Returns True when handled, meaning no Gemini call is needed. Turns carrying
    an image or a voice note always go to Gemini — a command keyword in the
    caption should not discard the attachment.
    """
    if not st.session_state.get("quick_commands"):
        return False

    pending = st.session_state.messages[-1]
    if pending.attachments:
        return False

    reply = tools.handle_command(pending.text)
    if reply is None:
        return False

    with st.chat_message("assistant"):
        render_rich_text(reply.markdown)
        st.caption("⚡ Answered on this machine — no API call.")

    st.session_state.messages.append(
        Message(role="assistant", text=reply.markdown, is_local=True)
    )
    speak(reply.speech)
    return True


def generate_assistant_turn(client: genai.Client) -> None:
    """Stream one assistant reply into the page and append it to the history."""
    if try_local_command():
        return

    with st.chat_message("assistant"):
        placeholder = st.empty()
        collected = ""
        try:
            for delta in stream_reply(
                client,
                st.session_state.messages,
                st.session_state.system_prompt,
                float(st.session_state.temperature),
            ):
                collected += delta
                placeholder.markdown(escape_currency(collected) + " ▌")
        except Exception as exc:  # noqa: BLE001 - surfaced to the user verbatim
            placeholder.empty()
            detail = str(exc) if isinstance(exc, RuntimeError) else friendly_error(exc)
            st.error(detail, icon="⚠️")
            st.session_state.messages.append(
                Message(role="assistant", text=detail, is_error=True)
            )
            return

        placeholder.empty()
        render_rich_text(collected)

    st.session_state.messages.append(Message(role="assistant", text=collected))
    speak(tools.speech_text(collected))


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def main() -> None:
    """Application entry point."""
    load_dotenv(override=False)
    configure_page()
    init_session_state()

    has_env_key = any(os.environ.get(var, "").strip() for var in API_KEY_ENV_VARS)

    # Resolve the client first, but render nothing yet: the input has to be read
    # before the sidebar so that the sidebar's Clear/Export controls reflect the
    # message just sent rather than the previous run's history.
    blocking_error = None
    client = None

    if not SUPPORTS_INLINE_ATTACHMENTS:
        blocking_error = (
            f"This app needs a newer Streamlit than the installed {st.__version__} "
            "(inline chat attachments are missing). Upgrade with "
            "`pip install -U -r requirements.txt`."
        )
    else:
        api_key = resolve_api_key()
        if api_key:
            try:
                client = get_client(api_key)
            except Exception as exc:  # noqa: BLE001 - bad key or proxy config
                blocking_error = friendly_error(exc)

    if client is not None:
        submitted = read_user_input()
        if submitted is not None:
            st.session_state.messages.append(submitted)

    render_sidebar(has_env_key)

    if blocking_error is not None:
        st.error(blocking_error, icon="⚠️")
        return

    if client is None:
        ui.render_header()
        st.info(
            "**Add your Gemini API key to get started.**\n\n"
            "1. Create a free key at https://aistudio.google.com/apikey\n"
            "2. Save it as `GEMINI_API_KEY=...` in a `.env` file next to `app.py`, "
            "or paste it into the sidebar for this session only.",
            icon="🔑",
        )
        return

    voice_mode = bool(st.session_state.get("voice_mode"))
    ui.render_header(listening=voice_mode)
    render_diagnostics()

    # The avatar is only worth the vertical space in a voice conversation.
    if voice_mode:
        ui.render_avatar()
    render_voice_console()

    messages: list[Message] = st.session_state.messages
    if not messages:
        render_welcome()

    for message in messages:
        render_message(message)

    # A trailing user turn means a reply is owed — stream it now.
    if messages and messages[-1].role == "user":
        generate_assistant_turn(client)


if __name__ == "__main__":
    main()
