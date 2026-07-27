"""
Presentation layer for Chillo AI Assistant — "terminal noir" styling.

Split out of ``app.py`` so the chat/API logic stays readable. Base colours,
fonts and radii live in ``.streamlit/config.toml`` (Streamlit applies those to
its own widgets); this module adds only what the theme system cannot express:

* a restrained dark surface and the brand header,
* the brand header and live status strip,
* the browser speech engine, which pins one consistent female voice.
"""

from __future__ import annotations

import base64
import json

import streamlit as st

# --------------------------------------------------------------------------- #
# Brand
# --------------------------------------------------------------------------- #

BRAND_NAME = "CHILLO"
BRAND_SUFFIX = "AI ASSISTANT"
CREATOR_NAME = "Malik Kashif"
CREATOR_TITLE = "Software Engineer"
CREATOR_LOCATION = "Lahore, Pakistan"

ACCENT = "#00E5A0"
ACCENT_DIM = "rgba(0, 229, 160, 0.55)"
CYAN = "#22D3EE"


# --------------------------------------------------------------------------- #
# Styling
# --------------------------------------------------------------------------- #

CHILLO_CSS = f"""
<style>

:root {{
    --chillo-accent: {ACCENT};
    --chillo-cyan: {CYAN};
}}

/* ---------- Backdrop ----------
   Deliberately plain. An earlier version layered an engineering grid and
   scanlines over everything; at real text sizes that competes with the
   content instead of framing it. One soft glow at the top is enough to
   stop the page reading as flat black. */
[data-testid="stAppViewContainer"] {{
    background-color: #06080C;
    background-image:
        radial-gradient(ellipse 70% 45% at 50% -15%, rgba(0, 229, 160, 0.06), transparent 70%);
}}

[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 1.6rem; padding-bottom: 6rem; max-width: 1040px; }}

/* Inter carries no emoji glyphs, so replies containing emoji render as tofu
   boxes unless a colour-emoji font is listed before the generic fallback.
   Per-glyph fallback means Latin text still comes from Inter. */
[data-testid="stMarkdownContainer"],
[data-testid="stChatMessageContent"],
[data-testid="stChatInput"] textarea,
.chillo-header, .chillo-credit {{
    font-family: 'Inter', 'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji',
                 system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
}}

/* ---------- Brand header ----------
   One quiet line: wordmark on the left, status on the right. The boxed,
   glowing panel it replaced ate ~120px of vertical space to say very little. */
.chillo-header {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
    padding: 0 0 0.75rem 0;
    margin-bottom: 0.9rem;
    border-bottom: 1px solid #16202B;
}}
.chillo-wordmark {{
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    font-size: 1.15rem;
    letter-spacing: 0.02em;
    color: #EAF2EE;
    line-height: 1.1;
    margin: 0;
}}
.chillo-wordmark span {{ color: var(--chillo-accent); }}
.chillo-sub {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.6rem;
    letter-spacing: 0.16em;
    color: #586B7C;
    margin-top: 0.15rem;
    text-transform: uppercase;
}}

/* Status: a dot and a word. No pill, no border, no background. */
.chillo-status {{
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.62rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #6E8697;
}}
.chillo-dot {{
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--chillo-accent);
    box-shadow: 0 0 8px var(--chillo-accent);
    animation: chillo-pulse 1.9s ease-in-out infinite;
}}
.chillo-status.is-listening {{
    color: var(--chillo-cyan);
}}
.chillo-status.is-listening .chillo-dot {{
    background: var(--chillo-cyan);
    box-shadow: 0 0 10px var(--chillo-cyan);
    animation-duration: 0.85s;
}}
@keyframes chillo-pulse {{
    0%, 100% {{ opacity: 1; transform: scale(1); }}
    50%      {{ opacity: 0.35; transform: scale(0.8); }}
}}

/* ---------- Chat ---------- */
/* Messages sit on the page rather than in boxes; only the assistant gets a
   thin accent rail so the two speakers are still instantly distinguishable. */
[data-testid="stChatMessage"] {{
    background: transparent;
    border: none;
    border-left: 2px solid #1C2733;
    border-radius: 0;
    padding-left: 0.9rem;
}}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {{
    border-left-color: var(--chillo-accent);
}}

[data-testid="stChatInput"] {{
    border: 1px solid #1E2C3A;
    box-shadow: none;
}}
[data-testid="stChatInput"]:focus-within {{
    border-color: rgba(0, 229, 160, 0.55);
    box-shadow: none;
}}

[data-testid="stCode"], .stCodeBlock {{ border: 1px solid #1B2A38; }}

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {{ border-right: 1px solid #16202B; }}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
    font-family: 'JetBrains Mono', ui-monospace, monospace !important;
    font-size: 0.72rem !important;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #6F8799 !important;
}}

.chillo-credit {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.64rem;
    line-height: 1.85;
    color: #63798B;
    border-top: 1px dashed #1D2A36;
    padding-top: 0.7rem;
    margin-top: 0.4rem;
}}
.chillo-credit b {{ color: var(--chillo-accent); font-weight: 500; }}

/* ---------- Mobile ---------- */
@media (max-width: 768px) {{
    .block-container {{ padding: 0.8rem 0.8rem 5.5rem 0.8rem; }}
    .chillo-wordmark {{ font-size: 1.05rem; }}
    .stButton > button, .stDownloadButton > button {{ min-height: 2.9rem; font-size: 1rem; }}
    [data-testid="stChatMessageContent"] p {{ font-size: 1rem; line-height: 1.55; }}
}}

@media (prefers-reduced-motion: reduce) {{ .chillo-dot {{ animation: none; }} }}
</style>
"""


def inject_theme() -> None:
    """Apply the Chillo styling. Call once, immediately after set_page_config."""
    st.markdown(CHILLO_CSS, unsafe_allow_html=True)


def render_header(listening: bool = False) -> None:
    """
    Draw the brand header with a live status strip.

    The underlying model provider is deliberately not shown — Chillo is the
    product, and which engine powers it is an implementation detail that belongs
    in settings, not in the product chrome.
    """
    status_class = "chillo-status is-listening" if listening else "chillo-status"
    status_text = "listening" if listening else "online"

    st.markdown(
        f"""
        <div class="chillo-header">
            <div>
                <div class="chillo-wordmark">{BRAND_NAME}<span>_</span></div>
                <div class="chillo-sub">{BRAND_SUFFIX}</div>
            </div>
            <div class="{status_class}"><span class="chillo-dot"></span>{status_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


HUD_CSS = """
<style>
/* Readouts as inline "label value" pairs that wrap naturally. The previous
   fixed grid clipped longer values ("flash-lite-la…") and boxed each one in
   its own cell, which was a lot of chrome for six short facts. */
.chillo-hud {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem 1.5rem;
    margin: 0 0 1.4rem 0;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.68rem;
}
.chillo-cell { display: flex; align-items: baseline; gap: 0.45rem; }
.chillo-cell .k {
    font-size: 0.6rem; letter-spacing: 0.12em; text-transform: uppercase; color: #4E6274;
}
.chillo-cell .v { color: #9FB4C2; }        /* no truncation — values wrap */
.chillo-cell .v.good { color: #00E5A0; }
.chillo-cell .v.warn { color: #E0A85C; }
.chillo-cell .v.bad  { color: #E86A6A; }
@media (max-width: 768px) { .chillo-hud { gap: 0.3rem 1rem; font-size: 0.64rem; } }
</style>
"""


def render_hud(cells: list[tuple[str, str, str]]) -> None:
    """
    Draw the diagnostics strip: a row of (label, value, state) readouts.

    ``state`` is "", "good", "warn" or "bad" and only tints the value. This is
    the JARVIS conceit made useful — the numbers that actually decide whether
    the next turn works (engine, quota, voice) sit on screen instead of being
    discovered through a failure.
    """
    tiles = "".join(
        f'<div class="chillo-cell"><div class="k">{k}</div>'
        f'<div class="v {state}">{v}</div></div>'
        for k, v, state in cells
    )
    st.markdown(f'{HUD_CSS}<div class="chillo-hud">{tiles}</div>', unsafe_allow_html=True)


def render_credit() -> None:
    """Creator credit for the sidebar footer."""
    st.markdown(
        f"""
        <div class="chillo-credit">
            <div>◈ <b>{BRAND_NAME} AI ASSISTANT</b></div>
            <div>designed &amp; built by</div>
            <div><b>{CREATOR_NAME}</b></div>
            <div>{CREATOR_TITLE} — {CREATOR_LOCATION}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# Avatar
# --------------------------------------------------------------------------- #

# st.html() runs a strict sanitiser that drops <style>, <svg> and even plain
# <div> subtrees — only <script> survives. st.markdown(unsafe_allow_html=True)
# keeps markup and styles (the brand header proves it), so the avatar is split:
# presentation through markdown, behaviour through st.html.
AVATAR_MARKUP = """
<style>
.chillo-stage {
    display: flex; flex-direction: column; align-items: center;
    gap: 0.55rem; padding: 1.1rem 0 0.4rem 0;
}
.chillo-avatar { position: relative; width: 168px; height: 168px; }

/* Concentric rings: slow drift when idle, urgent pulse while listening. */
.chillo-ring {
    position: absolute; inset: 0; border-radius: 50%;
    border: 1px solid rgba(0,229,160,0.28);
    animation: chillo-ring 3.4s ease-out infinite;
}
.chillo-ring:nth-child(2) { animation-delay: 1.1s; }
.chillo-ring:nth-child(3) { animation-delay: 2.2s; }
@keyframes chillo-ring {
    0%   { transform: scale(0.82); opacity: 0.85; }
    100% { transform: scale(1.22); opacity: 0; }
}
.chillo-avatar[data-state="listening"] .chillo-ring {
    border-color: rgba(34,211,238,0.5); animation-duration: 1.35s;
}
.chillo-avatar[data-state="speaking"] .chillo-ring {
    border-color: rgba(0,229,160,0.55); animation-duration: 1.9s;
}

/* The face is built from <div>s, not SVG: Streamlit's st.html sanitiser strips
   <svg> subtrees entirely, so an SVG avatar renders as an empty box. */
.chillo-face {
    position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
    width: 104px; height: 122px;
    background: linear-gradient(180deg, #0E2A2A 0%, #08161C 100%);
    border: 1.4px solid rgba(0,229,160,0.75);
    border-radius: 48% 48% 44% 44% / 52% 52% 48% 48%;
    box-shadow: 0 0 18px rgba(0,229,160,0.28), inset 0 -14px 26px rgba(0,0,0,0.45);
}
.chillo-hair {
    position: absolute; left: -7px; right: -7px; top: -8px; height: 54px;
    background: linear-gradient(135deg, #00E5A0, #22D3EE);
    border-radius: 50% 50% 42% 42% / 74% 74% 26% 26%;
    opacity: 0.9;
}
.chillo-hair::after {                      /* side sweep, softens the helmet look */
    content: ""; position: absolute; left: 4px; right: 4px; top: 32px; height: 30px;
    background: linear-gradient(135deg, #00E5A0, #22D3EE);
    border-radius: 50% 50% 60% 60% / 20% 20% 80% 80%;
    opacity: 0.35;
}
.chillo-brow {
    position: absolute; top: 52px; width: 20px; height: 2px; border-radius: 2px;
    background: rgba(0,229,160,0.8);
}
.chillo-brow.left  { left: 16px; transform: rotate(-8deg); }
.chillo-brow.right { right: 16px; transform: rotate(8deg); }

.chillo-eye {
    position: absolute; top: 62px; width: 21px; height: 14px;
    background: #031418; border: 1.2px solid #22D3EE; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    transform-origin: center; animation: chillo-blink 5.2s infinite;
}
.chillo-eye.left  { left: 15px; }
.chillo-eye.right { right: 15px; animation-delay: 0.08s; }
.chillo-pupil {
    width: 8px; height: 8px; border-radius: 50%; background: #22D3EE;
    box-shadow: 0 0 6px #22D3EE, inset 1.5px -1.5px 0 rgba(234,255,248,0.9);
}
@keyframes chillo-blink {
    0%, 92%, 100% { transform: scaleY(1); }
    95%           { transform: scaleY(0.08); }
}
.chillo-avatar[data-state="listening"] .chillo-eye { animation-duration: 3.1s; }

.chillo-nose {
    position: absolute; top: 78px; left: 50%; transform: translateX(-50%);
    width: 7px; height: 12px;
    border-left: 1.2px solid rgba(0,229,160,0.45);
    border-bottom: 1.2px solid rgba(0,229,160,0.45);
    border-radius: 0 0 0 6px;
}

/* Height is driven from JS during speech; this is the closed resting mouth. */
.chillo-mouth {
    position: absolute; top: 98px; left: 50%; transform: translateX(-50%);
    width: 30px; height: 4px;
    background: #0B2A28; border: 1.3px solid #00E5A0; border-radius: 50%;
    transition: height 70ms ease-out, width 70ms ease-out;
    box-shadow: 0 0 8px rgba(0,229,160,0.35);
}

.chillo-ear {
    position: absolute; top: 62px; width: 11px; height: 22px;
    background: #0B2A28; border: 1.2px solid #22D3EE; border-radius: 5px; opacity: 0.85;
}
.chillo-ear.left  { left: -9px; }
.chillo-ear.right { right: -9px; }
.chillo-band {
    position: absolute; left: -9px; right: -9px; top: -12px; height: 46px;
    border: 1.5px solid rgba(34,211,238,0.55);
    border-bottom: none; border-radius: 50% 50% 0 0 / 100% 100% 0 0;
}

.chillo-caption {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.63rem; letter-spacing: 0.22em; text-transform: uppercase;
    color: #6C8296;
}
.chillo-avatar[data-state="speaking"] ~ .chillo-caption { color: #00E5A0; }
.chillo-avatar[data-state="listening"] ~ .chillo-caption { color: #22D3EE; }

@media (prefers-reduced-motion: reduce) {
    .chillo-ring, .chillo-eye { animation: none; }
}
@media (max-width: 768px) { .chillo-avatar { width: 132px; height: 132px; } }
</style>

<div class="chillo-stage">
  <div class="chillo-avatar" id="chillo-avatar" data-state="idle">
    <div class="chillo-ring"></div><div class="chillo-ring"></div><div class="chillo-ring"></div>
    <div class="chillo-face">
      <div class="chillo-band"></div>
      <div class="chillo-ear left"></div>
      <div class="chillo-ear right"></div>
      <div class="chillo-hair"></div>
      <div class="chillo-brow left"></div>
      <div class="chillo-brow right"></div>
      <div class="chillo-eye left"><div class="chillo-pupil"></div></div>
      <div class="chillo-eye right"><div class="chillo-pupil"></div></div>
      <div class="chillo-nose"></div>
      <div class="chillo-mouth" id="chillo-mouth"></div>
    </div>
  </div>
  <div class="chillo-caption" id="chillo-caption">standing by</div>
</div>
"""

AVATAR_SCRIPT = """
<script>
(function () {
    // Idempotent: Streamlit re-runs the script on every interaction, but the
    // controller must survive so an in-flight animation is not restarted.
    if (window.chilloAvatar) { window.chilloAvatar.rebind(); return; }

    const CAPTIONS = {idle: 'standing by', listening: 'listening', speaking: 'speaking'};
    let timer = null;

    const api = {
        el: null,
        mouth: null,
        caption: null,
        rebind() {
            this.el = document.getElementById('chillo-avatar');
            this.mouth = document.getElementById('chillo-mouth');
            this.caption = document.getElementById('chillo-caption');
        },
        setState(state) {
            this.rebind();
            if (!this.el) return;
            this.el.dataset.state = state;
            if (this.caption) this.caption.textContent = CAPTIONS[state] || state;
            if (state !== 'speaking') this.closeMouth();
        },
        closeMouth() {
            if (timer) { clearInterval(timer); timer = null; }
            if (this.mouth) { this.mouth.style.height = '4px'; this.mouth.style.width = '30px'; }
        },
        // Amplitude-free lip-sync: speechSynthesis exposes no waveform, so the
        // mouth is driven by a jittered oscillation started on utterance start
        // and nudged on every word boundary. It tracks real speech timing.
        startMouth() {
            this.rebind();
            if (timer) { clearInterval(timer); timer = null; }
            if (!this.mouth) return;
            const m = this.mouth;
            timer = setInterval(() => {
                const open = 3 + Math.random() * 15;      // 3px .. 18px
                const wide = 26 + Math.random() * 8;      // narrows on tall vowels
                m.style.height = open.toFixed(0) + 'px';
                m.style.width = wide.toFixed(0) + 'px';
            }, 95);
        },
        nudge() {   // called on word boundaries for a visible consonant beat
            if (!this.mouth || !timer) return;
            this.mouth.style.height = '17px';
            this.mouth.style.width = '27px';
        },
        // True lip-sync: `level` is the RMS amplitude (0..~0.4) of the audio
        // actually playing, sampled per animation frame. Only usable with real
        // audio (ElevenLabs) — speechSynthesis exposes no waveform.
        setMouth(level) {
            this.rebind();
            if (!this.mouth) return;
            if (timer) { clearInterval(timer); timer = null; }
            const open = Math.min(1, level * 6);
            this.mouth.style.height = (3 + open * 17).toFixed(0) + 'px';
            this.mouth.style.width = (30 - open * 5).toFixed(0) + 'px';
        }
    };

    api.rebind();
    window.chilloAvatar = api;
})();
</script>
"""


def render_avatar() -> None:
    """Render the animated assistant avatar (idle / listening / speaking)."""
    st.markdown(AVATAR_MARKUP, unsafe_allow_html=True)
    st.html(AVATAR_SCRIPT, unsafe_allow_javascript=True)


def set_avatar_state(state: str) -> None:
    """Push a state change (``idle`` | ``listening`` | ``speaking``) to the avatar."""
    st.html(
        f"<script>window.chilloAvatar && window.chilloAvatar.setState({json.dumps(state)});</script>",
        unsafe_allow_javascript=True,
    )


# --------------------------------------------------------------------------- #
# Speech
# --------------------------------------------------------------------------- #

#: Known-female English voices, best first. Names differ per platform, so this
#: spans macOS/iOS (Samantha, Karen…), Chrome (Google … Female) and Windows
#: (Microsoft Zira/Aria). The first one present is pinned for the whole session
#: so Chillo never changes voice mid-conversation.
FEMALE_VOICES = [
    "Google UK English Female",
    "Microsoft Aria Online (Natural) - English (United States)",
    "Microsoft Zira - English (United States)",
    "Samantha",
    "Karen",
    "Moira",
    "Tessa",
    "Fiona",
    "Victoria",
    "Serena",
    "Allison",
    "Ava",
    "Susan",
    "Google US English",
]


def speak(text: str, seq: int, auto_listen: bool = False) -> None:
    """
    Speak ``text`` in the browser with a pinned female voice.

    Speech must happen client-side: a server-side engine would play audio on the
    host, which is the wrong machine once this is deployed. ``seq`` makes the
    element unique so Streamlit re-renders it instead of treating two identical
    replies as unchanged.

    Voice lists load asynchronously in most browsers, so the first call may find
    ``getVoices()`` empty; the ``voiceschanged`` listener retries once.
    """
    payload = json.dumps(text)
    preferred = json.dumps(FEMALE_VOICES)

    st.html(
        f"""
        <!-- chillo utterance {seq} -->
        <script>
        (function () {{
            const synth = window.speechSynthesis;
            if (!synth) return;
            const PREFERRED = {preferred};
{AUTO_LISTEN_JS}

            function choose(voices) {{
                for (const name of PREFERRED) {{
                    const hit = voices.find(v => v.name === name);
                    if (hit) return hit;
                }}
                const female = voices.find(
                    v => /female|woman|zira|aria|samantha|karen|tessa/i.test(v.name)
                         && /^en/i.test(v.lang));
                if (female) return female;
                return voices.find(v => /^en/i.test(v.lang)) || voices[0] || null;
            }}

            function say(attempt) {{
                const voices = synth.getVoices();
                if (!voices.length) {{
                    if (attempt === 0) {{
                        synth.addEventListener('voiceschanged', () => say(1), {{once: true}});
                    }}
                    return;
                }}
                if (!window.__chilloVoice) {{
                    const picked = choose(voices);
                    window.__chilloVoice = picked ? picked.name : null;
                }}
                synth.cancel();
                const utterance = new SpeechSynthesisUtterance({payload});
                const voice = voices.find(v => v.name === window.__chilloVoice);
                if (voice) {{
                    utterance.voice = voice;
                    utterance.lang = voice.lang;
                }}
                utterance.rate = 1.02;
                utterance.pitch = 1.08;   // slightly bright, keeps the tone consistent

                // Drive the avatar from the real utterance lifecycle so the
                // mouth starts and stops exactly with the audio.
                const avatar = window.chilloAvatar;
                utterance.onstart = () => {{
                    if (avatar) {{ avatar.setState('speaking'); avatar.startMouth(); }}
                }};
                utterance.onboundary = () => {{ if (avatar) avatar.nudge(); }};
                const done = () => {{
                    if (avatar) avatar.setState('idle');
                    if ({str(bool(auto_listen)).lower()}) setTimeout(chilloRelisten, 450);
                }};
                utterance.onend = done;
                utterance.onerror = done;

                synth.speak(utterance);
            }}

            say(0);
        }})();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


#: Hands-free loop. After Chillo stops talking, the browser's own microphone
#: button is clicked again so the user can just keep speaking, like a call.
#: The mic lives inside the streamlit-mic-recorder iframe, which is same-origin
#: (Streamlit serves it), so its button is reachable from the parent document.
AUTO_LISTEN_JS = """
            function chilloRelisten() {
                for (const frame of document.querySelectorAll('iframe')) {
                    let doc = null;
                    try { doc = frame.contentDocument; } catch (e) { continue; }
                    if (!doc) continue;
                    for (const btn of doc.querySelectorAll('button')) {
                        if (/START|LISTEN/i.test(btn.textContent || '')) {
                            btn.click();
                            return true;
                        }
                    }
                }
                return false;
            }
"""


def speak_audio(mp3_bytes: bytes, seq: int, auto_listen: bool = False) -> None:
    """
    Play ElevenLabs audio and drive the avatar from its real waveform.

    The MP3 is embedded as a data URI because ``st.html`` strips everything but
    ``<script>`` — there is no element to point an ``<audio src>`` at. A Web
    Audio ``AnalyserNode`` samples the playing signal each frame, so the mouth
    tracks actual speech amplitude rather than a synthetic oscillation.
    """
    payload = base64.b64encode(mp3_bytes).decode("ascii")

    st.html(
        f"""
        <!-- chillo audio {seq} -->
        <script>
        (function () {{
            const avatar = window.chilloAvatar;

            // Stop whatever was playing before starting the new reply.
            if (window.__chilloAudio) {{
                try {{ window.__chilloAudio.pause(); }} catch (e) {{}}
            }}
            if (window.speechSynthesis) window.speechSynthesis.cancel();

            const audio = new Audio("data:audio/mpeg;base64,{payload}");
            window.__chilloAudio = audio;

{AUTO_LISTEN_JS}
            const autoListen = {str(bool(auto_listen)).lower()};

            let raf = null;
            let stopped = false;
            function stop() {{
                if (stopped) return;          // onended and onerror can both fire
                stopped = true;
                if (raf) cancelAnimationFrame(raf);
                raf = null;
                if (avatar) {{ avatar.closeMouth(); avatar.setState('idle'); }}
                // Small gap so the mic doesn't capture the tail of her own voice.
                if (autoListen) setTimeout(chilloRelisten, 450);
            }}

            try {{
                const Ctx = window.AudioContext || window.webkitAudioContext;
                // One context per page: browsers cap how many can exist.
                const ctx = window.__chilloCtx || (window.__chilloCtx = new Ctx());
                if (ctx.state === 'suspended') ctx.resume();

                const source = ctx.createMediaElementSource(audio);
                const analyser = ctx.createAnalyser();
                analyser.fftSize = 256;
                source.connect(analyser);
                analyser.connect(ctx.destination);
                const buf = new Uint8Array(analyser.fftSize);

                function tick() {{
                    analyser.getByteTimeDomainData(buf);
                    let sum = 0;
                    for (let i = 0; i < buf.length; i++) {{
                        const v = (buf[i] - 128) / 128;
                        sum += v * v;
                    }}
                    if (avatar) avatar.setMouth(Math.sqrt(sum / buf.length));
                    raf = requestAnimationFrame(tick);
                }}

                audio.onplay = () => {{
                    if (avatar) avatar.setState('speaking');
                    tick();
                }};
            }} catch (e) {{
                // Web Audio unavailable — still play, just without lip-sync.
                audio.onplay = () => {{ if (avatar) avatar.setState('speaking'); }};
            }}

            audio.onended = stop;
            audio.onerror = stop;
            audio.play().catch(() => stop());   // autoplay blocked before any gesture
        }})();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def stop_speaking() -> None:
    """Cancel any in-flight browser speech and reset the avatar."""
    st.html(
        "<script>"
        "window.speechSynthesis && window.speechSynthesis.cancel();"
        "if (window.__chilloAudio) { try { window.__chilloAudio.pause(); } catch (e) {} }"
        "window.chilloAvatar && window.chilloAvatar.setState('idle');"
        "</script>",
        unsafe_allow_javascript=True,
    )
