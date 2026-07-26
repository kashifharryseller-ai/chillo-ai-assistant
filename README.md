# ◈ CHILLO — AI Assistant

A production-ready, cross-platform multimodal AI assistant with a "terminal noir" interface,
built with **Streamlit** and the official **`google-genai`** SDK on Google's Gemini Flash models.

> Designed & built by **Malik Kashif** — Software Engineer, Lahore, Pakistan.

Chillo has a real persona: she introduces herself, credits her creator, replies in English,
Urdu or Roman Urdu depending on how you write, and can speak every answer aloud in a
consistent female voice.

One codebase, three platforms:

| Platform | Support |
| --- | --- |
| **macOS** 12 Monterey or newer | ✅ `setup_mac.sh` (Python 3.10+) |
| **Windows** 10 / 11 | ✅ `setup_win.bat` |
| **Mobile** — iOS Safari, Android Chrome | ✅ Responsive UI, via Streamlit Community Cloud |

---

## Features

- **Streaming chat** — replies render token-by-token via `generate_content_stream`.
- **Image analysis** — attach JPEG/PNG/WebP files (or shoot a photo on mobile) and ask
  questions about them. Images are EXIF-rotated and downscaled before upload.
- **Voice input** — record straight from the microphone; the audio is sent natively to
  Gemini, with no separate transcription step.
- **Multi-turn memory** — the full conversation, including images and audio, is replayed
  as context on every turn.
- **Code blocks with one-click copy** — fenced code is rendered through `st.code`, giving
  syntax highlighting and a copy button on every block.
- **Customisation** — editable system prompt and a 0.0–1.0 temperature slider.
- **Chat management** — clear, regenerate, and export to Markdown or JSON.
- **"Terminal noir" interface** — neon-on-black, engineering grid, scanlines and glow, with
  an Orbitron wordmark and a live status strip. Colours, fonts and radii come from
  `.streamlit/config.toml` so Streamlit's own widgets inherit them natively.
- **Live voice mode** — push-to-talk console that transcribes your speech *in the browser*
  and sends it as a message, so a spoken question flows into a spoken answer. Supports
  English, Urdu, Punjabi, Hindi and Arabic recognition.
- **Consistent female voice** — replies are spoken with one pinned voice, chosen from a
  platform-aware preference list so Chillo never changes voice mid-conversation.
- **Auto-collapsing sidebar** and large tap targets on phones.
- **Quick commands** — time, date, jokes, sentiment analysis, Wikipedia summaries and
  search links, answered instantly on your own machine without spending an API call.

### Quick commands

Toggle these on or off under **Assistant** in the sidebar; type `what can you do` in the
app for the same list.

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
questions such as *"what is the best time to visit Japan?"* or *"how do I open a file in
Python?"* still go to Gemini. Any message with an image or voice note always goes to Gemini.

> **Why links instead of launching apps?** Desktop assistants can call `webbrowser.open()`
> or `AppOpener` because they run on your computer. This app may be served from Streamlit
> Cloud, where that code would run on Google's server rather than your device — so it hands
> the browser a link instead. Speech works the same way: it is synthesised in your browser,
> not by a server-side engine like `pyttsx3`.

---

## 1. Get a free API key from Google AI Studio

1. Go to **<https://aistudio.google.com/apikey>**.
2. Sign in with any Google account.
3. Click **Create API key**, then **Create API key in new project**.
4. Copy the key — it starts with `AIza…`.

The free tier is generous enough for personal use of the Flash models; no credit card or
billing account is required. Treat the key like a password.

> **Key formats.** New keys start with **`AQ.`** ("auth keys"). The older `AIza…` format
> ("standard keys") is being retired — Google began rejecting unrestricted standard keys on
> 19 June 2026. Both work with this app; prefer a new `AQ.` key.
> See [Using Gemini API keys](https://ai.google.dev/gemini-api/docs/api-key).

## 2. Set up your `.env` file

Copy the template and paste your key in:

```bash
cp .env.example .env      # macOS / Linux
copy .env.example .env    # Windows
```

Then edit `.env` so it reads:

```env
GEMINI_API_KEY=AIzaSyYourActualKeyHere
```

> `.env` is listed in `.gitignore`, so it will never be committed.
>
> **Prefer not to use a file?** Skip this step and paste the key into the app's sidebar
> instead — it is kept in memory for that browser session only.

## 3. Run it

### macOS 12+

```bash
chmod +x setup_mac.sh
./setup_mac.sh
```

The script verifies Python 3.10+, creates `.venv`, installs the pinned dependencies, and
launches the app at <http://localhost:8501>. Re-running it reuses the environment and skips
installation when `requirements.txt` is unchanged.

> macOS 12 ships Python 3.8 at `/usr/bin/python3`, which is **too old** for the SDK. The
> script searches for a newer interpreter automatically. If none is found, install one:
>
> ```bash
> brew install python@3.12
> ```
>
> …or download an installer from <https://www.python.org/downloads/macos/>.

### Windows 10 / 11

Double-click **`setup_win.bat`**, or run it from a terminal:

```bat
setup_win.bat
```

It does the same thing using the `py` launcher. If Python is missing, install it with
`winget install Python.Python.3.12` or from
<https://www.python.org/downloads/windows/> — and be sure to tick
**"Add python.exe to PATH"** in the installer.

### Manual setup (any platform)

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

---

## 4. Host it free on Streamlit Community Cloud (for phone access)

This is the easiest way to use the assistant on iOS or Android — you get a public HTTPS URL
and never have to keep a computer running.

1. **Push this folder to a GitHub repository.**

   ```bash
   git init
   git add .
   git commit -m "Gemini AI Assistant"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```

   Double-check that `.env` is **not** in the commit — `.gitignore` already excludes it.

2. **Deploy.** Go to <https://share.streamlit.io>, sign in with GitHub, and click
   **Create app → Deploy a public app from GitHub**. Select your repository, set the branch
   to `main` and the main file path to `app.py`, then click **Deploy**.

3. **Add your API key as a secret.** In the app's **⋮ → Settings → Secrets** panel, paste:

   ```toml
   GEMINI_API_KEY = "AIzaSyYourActualKeyHere"
   ```

   Save. The app reads `st.secrets` automatically and will restart with the key applied.

4. **Open it on your phone** at `https://<your-app>.streamlit.app` and add it to your home
   screen (Safari: *Share → Add to Home Screen*; Chrome: *⋮ → Add to Home screen*) for a
   full-screen, app-like experience.

> **Microphone note:** browsers only grant microphone access over **HTTPS** or on
> `localhost`. Voice input therefore works on Streamlit Cloud and on your own machine, but
> **not** when a phone connects to your computer's plain-HTTP LAN address
> (`http://192.168.x.x:8501`). Use the Cloud deployment for voice on mobile.

---

## Project structure

```
.
├── app.py              # Chat flow + Gemini logic
├── ui.py               # Terminal-noir styling, brand header, speech engine
├── assistant_tools.py  # Local quick-command skills + speech helpers
├── requirements.txt    # Pinned dependencies
├── setup_mac.sh        # macOS 12+ setup and launcher
├── setup_win.bat       # Windows 10/11 setup and launcher
├── .env.example        # Template for your API key
├── .gitignore          # Keeps .env and .venv out of git
├── .streamlit/
│   └── config.toml     # Dark theme, upload limit
└── README.md
```

## Configuration reference

| Setting | Where | Default |
| --- | --- | --- |
| API key | `.env`, `st.secrets`, or the sidebar | — |
| System prompt | Sidebar | Concise, code-fencing assistant |
| Temperature | Sidebar slider | `0.7` |
| Model | Sidebar dropdown (`AVAILABLE_MODELS` in `app.py`) | `gemini-flash-latest` |
| Max image edge | `MAX_IMAGE_EDGE` in `app.py` | `1568` px |
| Images per turn | `MAX_IMAGES_PER_TURN` in `app.py` | `4` |
| Upload size cap | `.streamlit/config.toml` | `25` MB |
| Quick commands | Sidebar toggle | on |
| Speak replies | Sidebar toggle | off |
| Live voice mode | Sidebar toggle | off |
| Recognition language | Sidebar (voice mode on) | English (US) |
| Persona | `DEFAULT_SYSTEM_PROMPT` in `app.py` | Chillo / Malik Kashif |
| Brand + colours | `ui.py` and `.streamlit/config.toml` | neon mint `#00E5A0` |
| Voice preference list | `FEMALE_VOICES` in `ui.py` | Google UK English Female first |

The app reads `GEMINI_API_KEY` first and falls back to `GOOGLE_API_KEY`.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Authentication failed` | The key is wrong or the Gemini API is not enabled for it. Regenerate it at <https://aistudio.google.com/apikey>. |
| `Rate limit or quota exceeded` | Free-tier limit hit. Wait a minute, or lower your request rate. |
| 429 with **`limit: 0`** | Almost always a **retired model**, not an exhausted quota — a deprecated model keeps appearing in `models.list()` but reports zero quota. Pick another model in the sidebar. Only if *every* model fails is it a billing/project issue. |
| `Model … is not available` (404) | That model is not served to your key's tier. Choose another in the sidebar. |
| `Python 3.10 or newer is required` | Install a newer Python (see the macOS/Windows notes above) and re-run the setup script. |
| Microphone button does nothing | Grant the browser mic permission, and make sure you are on HTTPS or `localhost` (see the note above). |
| `This app needs a newer Streamlit` | Run `pip install -U -r requirements.txt` — inline chat attachments need Streamlit 1.60. |
| Port 8501 already in use | `streamlit run app.py --server.port 8502` |
| Windows: `'py' is not recognized` | Reinstall Python with **"Add python.exe to PATH"** ticked. |

## Requirements

Python **3.10+** and the four pinned packages in `requirements.txt`:
`google-genai`, `streamlit`, `pillow`, `python-dotenv`. All ship prebuilt wheels for macOS
(Intel and Apple Silicon) and Windows, so no compiler is needed.

## License

Provided as-is for personal and commercial use. Google's Gemini API is governed by the
[Gemini API Terms of Service](https://ai.google.dev/gemini-api/terms).
