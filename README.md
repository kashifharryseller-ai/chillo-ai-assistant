# ◈ CHILLO — AI Assistant

A cross-platform, multimodal AI assistant with a "terminal noir" interface, a real
persona, and a talking animated avatar. Built with **Streamlit** and the official
**`google-genai`** SDK, with optional **ElevenLabs** speech.

> Designed & built by **Malik Kashif** — Software Engineer, Lahore, Pakistan.

Chillo introduces herself, credits her creator, replies in English, Urdu or Roman Urdu
depending on how you write, speaks every answer aloud in a consistent female voice, and
lip-syncs an on-screen avatar to her own audio.

| Platform | Support |
| --- | --- |
| **macOS** 12 Monterey or newer | ✅ `setup_mac.sh` (Python 3.10+) |
| **Windows** 10 / 11 | ✅ `setup_win.bat` |
| **Mobile** — iOS Safari, Android Chrome | ✅ responsive UI (see the microphone note) |

---

## Features

**Conversation**
- Streaming replies rendered token-by-token
- Image analysis — attach JPEG/PNG/WebP, or shoot a photo on mobile
- Voice notes — record audio and send it straight to the model
- Multi-turn memory, with attachment replay pruned to protect your quota
- Code blocks with syntax highlighting and one-click copy

**Voice**
- **Live voice mode** — the browser transcribes your speech locally and sends it as text
- **Call mode** — after Chillo finishes speaking the microphone re-arms itself, so you can
  talk → listen → talk without touching anything, like a phone call
- **Two voice engines** — the browser's built-in synthesis (free, unlimited) or
  **ElevenLabs** (far more natural, metered)
- **Animated avatar** that blinks, pulses while listening, and lip-syncs while speaking.
  With ElevenLabs the mouth is driven by the *actual* audio waveform via a Web Audio
  `AnalyserNode`; with browser speech it follows word-boundary events.

**Instant commands** — answered on your own machine, costing no API call at all:
time, date, jokes, sentiment analysis, Wikipedia summaries, and search links.

**Control**
- Selectable engine, editable system prompt, temperature slider
- Clear / regenerate / export chat (Markdown or JSON)
- Dark theme, auto-collapsing sidebar, large touch targets on phones

---

## 1. Get a Gemini API key (required, free)

1. Go to **<https://aistudio.google.com/apikey>**
2. Sign in and click **Create API key**
3. Copy the key

> **Key formats.** New keys start with **`AQ.`** ("auth keys"). The older `AIza…` format
> ("standard keys") is being retired — Google began rejecting unrestricted standard keys
> on 19 June 2026. Both work here; prefer a new `AQ.` key.
> See [Using Gemini API keys](https://ai.google.dev/gemini-api/docs/api-key).

## 2. Get an ElevenLabs key (optional, for the realistic voice)

Only needed if you want the natural voice and true lip-sync. Without it Chillo uses your
browser's built-in speech, which is free and unlimited.

Grab one at <https://elevenlabs.io/app/settings/api-keys>. **The free tier grants 10,000
characters per month** — roughly 20–30 spoken replies. See [Costs](#costs-and-limits).

## 3. Create your `.env`

```bash
cp .env.example .env      # macOS / Linux
copy .env.example .env    # Windows
```

```env
GEMINI_API_KEY=AQ.your_key_here
ELEVENLABS_API_KEY=sk_your_key_here   # optional
```

`.env` is in `.gitignore` and will never be committed. You can also paste either key into
the sidebar instead — it is then held in memory for that browser session only.

## 4. Run it

### macOS 12+

```bash
chmod +x setup_mac.sh
./setup_mac.sh
```

Verifies Python 3.10+, creates `.venv`, installs pinned dependencies, and launches at
<http://localhost:8501>. Re-running reuses the environment and skips installation when
`requirements.txt` is unchanged.

> macOS 12 ships Python 3.8 at `/usr/bin/python3`, which is **too old**. The script finds a
> newer interpreter automatically; if none exists, install one with
> `brew install python@3.12` or from <https://www.python.org/downloads/macos/>.

### Windows 10 / 11

Double-click **`setup_win.bat`**, or run it from a terminal. If Python is missing, install
it with `winget install Python.Python.3.12` — and tick **"Add python.exe to PATH"**.

### Manual (any platform)

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

---

## Costs and limits

This is the part that bites people, so it is spelled out.

### Gemini free tier — the engine choice matters a lot

Measured against a live free-tier key:

| Engine | Free-tier behaviour |
| --- | --- |
| **Lite** (`gemini-flash-lite-latest`, `gemini-3.5-flash-lite`, …) | Served requests continuously — **the default, and what you want** |
| **Core** (`gemini-flash-latest`, `gemini-3.6-flash`, …) | Capped at roughly **20 requests per _day_** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`). A single conversation exhausts it. |

A Core engine that has hit its daily cap returns `429`, and **waiting does not help** —
it resets the next day. Chillo detects this specific case and tells you to switch to a
Lite engine rather than giving the usual "wait 30 seconds" advice.

For real use, enable billing on the Google Cloud project behind the key.

### ElevenLabs free tier

**10,000 characters per month.** At ~300–500 characters per spoken reply, that is about
20–30 replies. Chillo defends the budget:

- Live character counter in the sidebar
- Every synthesis is cached, so a Streamlit rerun never re-bills the same sentence
- Hard 700-character cap per utterance
- On quota exhaustion — or any ElevenLabs error — it **falls back to the browser voice**
  rather than going silent

### Token efficiency

Older images and voice notes are **not** re-uploaded on every turn (only the most recent
`ATTACHMENT_MEMORY_TURNS` are), with a short placeholder standing in for the rest. Without
this, a six-turn voice conversation sent ~5,800 tokens instead of ~1,700, and the cost
grew with every message.

---

## Instant commands

Answered locally with no API call. Toggle them under **Assistant** in the sidebar, or type
`what can you do` in the app.

| Command | Example | Handled by |
| --- | --- | --- |
| Time | `time`, `what's the time` | local clock |
| Date | `date`, `what day is it today` | local clock |
| Joke | `tell me a joke` | `pyjokes` (offline) |
| Sentiment | `sentiment: I love this app` | `vaderSentiment` |
| Wikipedia | `wikipedia black holes` | Wikipedia REST API |
| Web search | `search for python tutorials` | returns a Google link |
| YouTube | `youtube lofi beats`, `play jazz on youtube` | returns a YouTube link |
| Open a site | `open github` | returns a link to `https://github.com` |

Matching is deliberately strict and anchored to the start of your message, so ordinary
questions — *"what is the best time to visit Japan?"*, *"how do I open a file in Python?"*,
*"wikipedia is a great resource, why?"* — still go to the model. Any message carrying an
image or voice note always goes to the model too.

> **Why links instead of launching apps?** A desktop assistant can call `webbrowser.open()`
> because it runs on your computer. This app may be served from Streamlit Cloud, where that
> code would run on Google's server rather than your device — so it hands the browser a
> link instead. Speech works the same way: it is synthesised in your browser, never by a
> server-side engine.

---

## Voice setup

| Setting | Where | Notes |
| --- | --- | --- |
| Speak replies aloud | Sidebar → Assistant | Master switch |
| Voice engine | Sidebar | `Browser (free)` or `ElevenLabs (realistic)` |
| Voice | Sidebar (ElevenLabs) | Six female voices; default **Jessica** — soft, warm, conversational |
| Audio quality | Sidebar (ElevenLabs) | High quality, or compact for faster loading |
| Live voice mode | Sidebar | Push-to-talk console; browser does the transcription |
| Call mode | Sidebar (voice mode on) | Hands-free loop — mic re-arms after each reply |
| Recognition language | Sidebar (voice mode on) | English, Urdu (PK), Punjabi, Hindi, Arabic |

**Model choice matters for Urdu.** Chillo requests `eleven_v3`, which lists **74 languages
including Urdu**. The commonly-quoted `eleven_multilingual_v2` covers only 29 and does
**not** include Urdu. If `eleven_v3` is unavailable on your account, the code falls back to
`eleven_multilingual_v2` automatically.

Delivery is tuned for warmth rather than narration — lower `stability` for emotional range,
raised `style` for inflection, and slightly under normal speed. See `VOICE_SETTINGS` in
`voice.py`.

> **Microphone note:** browsers only grant microphone access over **HTTPS** or on
> `localhost`. Voice input therefore works on Streamlit Cloud and on your own machine, but
> **not** when a phone connects to your computer's plain-HTTP LAN address
> (`http://192.168.x.x:8501`). Live voice mode is best in Chrome or Edge.

---

## Deploy free on Streamlit Community Cloud

The easiest way to use Chillo on a phone — you get a public HTTPS URL, which also means the
microphone works.

1. **Push to GitHub** (this repository already is). Confirm `.env` is not in the commit —
   `.gitignore` excludes it.
2. **Deploy.** Go to <https://share.streamlit.io>, sign in with GitHub, click
   **Create app → Deploy a public app from GitHub**, select this repo, branch `main`, main
   file `app.py`.
3. **Add secrets.** In **⋮ → Settings → Secrets**:

   ```toml
   GEMINI_API_KEY = "AQ.your_key_here"
   ELEVENLABS_API_KEY = "sk_your_key_here"
   ```

4. **Open on your phone** and add it to the home screen (Safari: *Share → Add to Home
   Screen*; Chrome: *⋮ → Add to Home screen*).

---

## Project structure

```
.
├── app.py              # Chat flow, Gemini calls, session state
├── ui.py               # Terminal-noir styling, brand header, avatar, speech
├── voice.py            # ElevenLabs TTS, voice catalogue, quota tracking
├── assistant_tools.py  # Local instant commands + speech-text helpers
├── requirements.txt    # Pinned dependencies
├── setup_mac.sh        # macOS 12+ setup and launcher
├── setup_win.bat       # Windows 10/11 setup and launcher
├── .env.example        # Template for your keys
├── .gitignore          # Keeps .env and .venv out of git
├── .streamlit/
│   └── config.toml     # Theme, fonts, upload limit
└── README.md
```

## Configuration reference

| Setting | Where | Default |
| --- | --- | --- |
| Gemini key | `.env`, `st.secrets`, or sidebar | — |
| ElevenLabs key | `.env`, `st.secrets`, or sidebar | — (optional) |
| Engine | Sidebar (`AVAILABLE_MODELS` in `app.py`) | `gemini-flash-lite-latest` |
| System prompt / persona | Sidebar (`DEFAULT_SYSTEM_PROMPT` in `app.py`) | Chillo / Malik Kashif |
| Temperature | Sidebar slider | `0.7` |
| Attachment replay depth | `ATTACHMENT_MEMORY_TURNS` in `app.py` | `2` turns |
| History window | `MAX_HISTORY_MESSAGES` in `app.py` | `40` messages |
| Max image edge | `MAX_IMAGE_EDGE` in `app.py` | `1568` px |
| Voice catalogue & tuning | `VOICES` / `VOICE_SETTINGS` in `voice.py` | Jessica, soft profile |
| Brand & colours | `ui.py` and `.streamlit/config.toml` | neon mint `#00E5A0` |

The app reads `GEMINI_API_KEY` first and falls back to `GOOGLE_API_KEY`.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Authentication failed` | Key is wrong or the Gemini API is not enabled for it. Regenerate at <https://aistudio.google.com/apikey>. |
| 429 mentioning **per day** | A Core engine's daily free allowance is gone. Switch to a **Lite** engine, or enable billing. Waiting will not help. |
| 429 without "per day" | Short-window throttling. Wait ~30s, then press **Regenerate reply** — your message is preserved. |
| 429 with **`limit: 0`** | Almost always a **retired model**, not an exhausted quota — a deprecated model keeps appearing in `models.list()` but reports zero quota. Pick another engine. |
| `Model … is not available` (404) | That engine is not served to your key's tier. Choose another. |
| Voice is silent | Check **Speak replies aloud**. If on ElevenLabs, check the character counter — it falls back to the browser voice when exhausted. |
| Microphone does nothing | Grant browser mic permission, and make sure you are on HTTPS or `localhost`. Chrome or Edge recommended. |
| Emoji render as boxes | Fixed in `ui.py` via a colour-emoji font fallback; hard-refresh to clear cached CSS. |
| `This app needs a newer Streamlit` | `pip install -U -r requirements.txt` — inline chat attachments need Streamlit 1.60. |
| Port 8501 in use | `streamlit run app.py --server.port 8502` |
| Edited `ui.py` but nothing changed | Streamlit hot-reloads `app.py` only. Restart the server after editing other modules. |

---

## Known limitations

Being straight about what this does not do yet:

- **No persistence.** Conversations live in Streamlit session state, so a page refresh or
  server restart clears them. Real multi-user use needs a database.
- **No accounts or billing.** Single-user by design.
- **Anthropic Claude is not wired in.** Groundwork exists in the engine picker, but note
  Claude accepts no audio input and rejects the `temperature` parameter on its 5-series
  models, so it needs engine-aware handling rather than a drop-in swap.
- **The mobile layout is unverified on a real device.** The responsive CSS and
  auto-collapsing sidebar are implemented but were not tested on physical hardware.

## Requirements

Python **3.10+** and the pinned packages in `requirements.txt`: `google-genai`,
`streamlit`, `pillow`, `python-dotenv`, `httpx`, `pyjokes`, `vaderSentiment`,
`streamlit-mic-recorder`. All ship prebuilt wheels for macOS (Intel and Apple Silicon) and
Windows, so no compiler is needed.

## License

Provided as-is for personal and commercial use. Google's Gemini API is governed by the
[Gemini API Terms of Service](https://ai.google.dev/gemini-api/terms); ElevenLabs by its
own [terms](https://elevenlabs.io/terms).
