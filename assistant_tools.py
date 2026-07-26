"""
Local "quick command" skills, answered without calling the Gemini API.

Inspired by classic desktop voice assistants (time, date, jokes, Wikipedia
lookups, sentiment analysis, web searches), adapted for a web app:

* Nothing here touches the host machine. A desktop assistant can launch Chrome
  or close an app because it runs on the same computer as the user; this app may
  be served from Streamlit Cloud, so "open YouTube" returns a link the *browser*
  follows instead of launching a process on the server.
* Speech is produced in the browser (see ``speech_text`` and the Web Speech API
  call in ``app.py``), not with a server-side engine such as ``pyttsx3``.

Matching is deliberately strict: every pattern is anchored to the start of the
message, so ordinary questions ("what is the best time to visit Japan?") fall
through to Gemini instead of being hijacked by the ``time`` command.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote, quote_plus

import httpx

# Wikipedia's API requires a descriptive User-Agent and rejects generic ones.
WIKI_USER_AGENT = "GeminiAIAssistant/1.0 (Streamlit sample app)"
WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
WIKI_TIMEOUT = 10.0

#: VADER's documented cut-offs for labelling a compound score.
SENTIMENT_POSITIVE = 0.05
SENTIMENT_NEGATIVE = -0.05


@dataclass
class ToolReply:
    """A locally produced answer: Markdown for the page, plain text for speech."""

    markdown: str
    speech: str


# --------------------------------------------------------------------------- #
# Speech helpers
# --------------------------------------------------------------------------- #

_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
_IMAGE_MD = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK_MD = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
_EMPHASIS = re.compile(r"[*_~`>#|]+")


def speech_text(markdown_text: str, limit: int = 700) -> str:
    """
    Reduce Markdown to something worth reading aloud.

    Code blocks are announced rather than spelled out — a screen reader working
    through ``s[::-1]`` character by character helps nobody. The result is
    truncated so one long answer cannot monopolise the speech queue.
    """
    text = _CODE_FENCE.sub(" (code block omitted) ", markdown_text)
    text = _IMAGE_MD.sub(" ", text)
    text = _LINK_MD.sub(r"\1", text)
    text = _HEADING.sub("", text)
    text = _TABLE_ROW.sub(" ", text)
    text = _EMPHASIS.sub(" ", text)
    text = text.replace("\\$", "$")
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > limit:
        # Prefer cutting at a sentence end so speech does not stop mid-word.
        clipped = text[:limit]
        boundary = max(clipped.rfind(". "), clipped.rfind("! "), clipped.rfind("? "))
        text = (clipped[: boundary + 1] if boundary > limit // 2 else clipped).rstrip() + " …"
    return text


def greeting(now: datetime | None = None) -> str:
    """Return a time-of-day greeting."""
    hour = (now or datetime.now()).hour
    if 5 <= hour < 12:
        return "Good morning"
    if 12 <= hour < 17:
        return "Good afternoon"
    if 17 <= hour < 22:
        return "Good evening"
    return "Hello"


# --------------------------------------------------------------------------- #
# Individual skills
# --------------------------------------------------------------------------- #


def tell_time(_: re.Match) -> ToolReply:
    """Current local time of the machine running the app."""
    now = datetime.now()
    return ToolReply(
        markdown=f"🕒 It is **{now.strftime('%H:%M')}** ({now.strftime('%I:%M %p').lstrip('0')}).",
        speech=f"It is {now.strftime('%I:%M %p').lstrip('0')}.",
    )


def tell_date(_: re.Match) -> ToolReply:
    """Today's date."""
    today = datetime.now()
    pretty = today.strftime("%A, %d %B %Y").replace(" 0", " ")
    return ToolReply(markdown=f"📅 Today is **{pretty}**.", speech=f"Today is {pretty}.")


def tell_joke(_: re.Match) -> ToolReply:
    """A random offline joke."""
    try:
        import pyjokes
    except ImportError:
        return ToolReply(
            markdown="Jokes need the `pyjokes` package — run `pip install -r requirements.txt`.",
            speech="The jokes package is not installed.",
        )
    joke = pyjokes.get_joke()
    return ToolReply(markdown=f"😄 {joke}", speech=joke)


def analyse_sentiment(match: re.Match) -> ToolReply:
    """
    Score a phrase with VADER and label it positive, negative or neutral.

    The original desktop assistant averaged VADER with TextBlob. TextBlob needs a
    separate ``download_corpora`` step that would break one-command setup on a
    fresh machine, so this uses VADER alone — it ships its own lexicon, is pure
    Python, and is the stronger of the two on short, informal text.
    """
    phrase = (match.group("arg") or "").strip()
    if not phrase:
        return ToolReply(
            markdown="Give me a sentence to analyse, e.g. `sentiment: I love this app`.",
            speech="Please give me a sentence to analyse.",
        )

    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    except ImportError:
        return ToolReply(
            markdown="Sentiment analysis needs `vaderSentiment` — run "
            "`pip install -r requirements.txt`.",
            speech="The sentiment package is not installed.",
        )

    scores = SentimentIntensityAnalyzer().polarity_scores(phrase)
    compound = scores["compound"]
    if compound >= SENTIMENT_POSITIVE:
        label, icon = "Positive", "🙂"
    elif compound <= SENTIMENT_NEGATIVE:
        label, icon = "Negative", "🙁"
    else:
        label, icon = "Neutral", "😐"

    markdown = (
        f"{icon} **{label}** sentiment (compound score `{compound:+.3f}`)\n\n"
        f"> {phrase}\n\n"
        f"| positive | neutral | negative |\n| --- | --- | --- |\n"
        f"| {scores['pos']:.0%} | {scores['neu']:.0%} | {scores['neg']:.0%} |"
    )
    return ToolReply(markdown=markdown, speech=f"That sentence sounds {label.lower()}.")


def wikipedia_lookup(match: re.Match) -> ToolReply:
    """
    Fetch a short Wikipedia summary via the official REST API.

    Uses the REST endpoint directly rather than the PyPI ``wikipedia`` package,
    which has been unmaintained since 2014 and scrapes rendered HTML.
    """
    topic = (match.group("arg") or "").strip(" ?.!")
    if not topic:
        return ToolReply(
            markdown="What should I look up? Try `wikipedia quantum computing`.",
            speech="What should I look up?",
        )

    url = WIKI_SUMMARY_URL.format(quote(topic.replace(" ", "_"), safe=""))
    try:
        response = httpx.get(
            url,
            timeout=WIKI_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": WIKI_USER_AGENT, "Accept": "application/json"},
        )
    except httpx.HTTPError:
        return ToolReply(
            markdown=f"Could not reach Wikipedia to look up **{topic}**.",
            speech="I could not reach Wikipedia.",
        )

    if response.status_code == 404:
        search = f"https://en.wikipedia.org/w/index.php?search={quote_plus(topic)}"
        return ToolReply(
            markdown=f"No Wikipedia page called **{topic}**. [Search instead]({search})",
            speech=f"I found no Wikipedia page for {topic}.",
        )
    if response.status_code != 200:
        return ToolReply(
            markdown=f"Wikipedia returned an error ({response.status_code}) for **{topic}**.",
            speech="Wikipedia returned an error.",
        )

    data = response.json()
    extract = (data.get("extract") or "").strip()
    if not extract:
        return ToolReply(
            markdown=f"Wikipedia has no summary for **{topic}**.",
            speech=f"Wikipedia has no summary for {topic}.",
        )

    title = data.get("title", topic)
    page = (data.get("content_urls", {}).get("desktop", {}) or {}).get("page", "")

    if data.get("type") == "disambiguation":
        markdown = f"**{title}** can mean several things — {extract}"
        if page:
            markdown += f"\n\n[Open on Wikipedia]({page})"
        return ToolReply(markdown=markdown, speech=f"{title} can mean several things.")

    markdown = f"📖 **{title}**\n\n{extract}"
    if page:
        markdown += f"\n\n[Read more on Wikipedia]({page})"
    return ToolReply(markdown=markdown, speech=extract)


def web_search(match: re.Match) -> ToolReply:
    """Return a Google search link (the browser navigates; the server does not)."""
    query = (match.group("arg") or "").strip()
    if not query:
        return ToolReply(markdown="What should I search for?", speech="What should I search for?")
    url = f"https://www.google.com/search?q={quote_plus(query)}"
    return ToolReply(
        markdown=f"🔎 [Search Google for **{query}**]({url})",
        speech=f"Here is a Google search for {query}.",
    )


def youtube_search(match: re.Match) -> ToolReply:
    """Return a YouTube search link."""
    query = (match.group("arg") or "").strip()
    if not query:
        return ToolReply(markdown="What should I find on YouTube?", speech="What should I find?")
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    return ToolReply(
        markdown=f"▶️ [Search YouTube for **{query}**]({url})",
        speech=f"Here is a YouTube search for {query}.",
    )


_SITE_SAFE = re.compile(r"^[A-Za-z0-9.\-]+$")


def open_website(match: re.Match) -> ToolReply:
    """
    Turn "open github" into a link to https://github.com.

    Only a bare hostname is accepted, so a message cannot smuggle in a path,
    credentials or a javascript: URL.
    """
    raw = (match.group("arg") or "").strip().strip("/").lower()
    raw = re.sub(r"^https?://", "", raw)
    site = raw.split("/")[0]

    if not site or not _SITE_SAFE.match(site) or site.startswith(".") or site.endswith("."):
        return ToolReply(
            markdown=f"`{raw or 'that'}` does not look like a website name.",
            speech="That does not look like a website name.",
        )
    if "." not in site:
        site += ".com"

    return ToolReply(
        markdown=f"🌐 [Open {site}](https://{site})", speech=f"Here is a link to {site}."
    )


def show_help(_: re.Match) -> ToolReply:
    """List the locally handled commands."""
    markdown = (
        "**Quick commands** — answered instantly, without using the Gemini API:\n\n"
        "| Command | Example |\n| --- | --- |\n"
        "| Time | `time` |\n"
        "| Date | `date` |\n"
        "| Joke | `tell me a joke` |\n"
        "| Sentiment | `sentiment: I love this app` |\n"
        "| Wikipedia | `wikipedia black holes` |\n"
        "| Web search | `search for python tutorials` |\n"
        "| YouTube | `youtube lofi beats` |\n"
        "| Open a site | `open github` |\n\n"
        "Anything else goes to Gemini, including images and voice notes."
    )
    return ToolReply(markdown=markdown, speech="Here are the quick commands I handle myself.")


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #

#: Separator between a trigger word and its argument: whitespace, or a colon or
#: dash with optional spaces. Requiring one is what stops "sentimental" from
#: being read as the "sentiment" command with the argument "al".
_SEP = r"(?:\s*[:\-]\s*|\s+)"

#: Trailing punctuation permitted on a command with no argument.
_END = r"\s*[?.!]*\s*$"

#: Refuses arguments that open like a sentence, so "wikipedia is a great
#: resource, why?" is treated as conversation rather than a lookup of the
#: article "is a great resource". A real topic ("wikipedia the beatles")
#: does not start with one of these.
_NOT_SENTENCE = (
    r"(?!(?:is|are|was|were|isn't|aren't|why|how|does|do|did|can|could|should"
    r"|would|has|have|had|will|won't)\b)"
)


def _no_arg(trigger: str) -> re.Pattern:
    """Compile a command that takes no argument and must be the whole message."""
    return re.compile(rf"^\s*(?:{trigger}){_END}", re.I)


def _with_arg(trigger: str, arg: str = r"\S.*") -> re.Pattern:
    """
    Compile a command whose argument is optional but, when present, separated.

    The ``\\b`` after the trigger prevents matching a longer word that merely
    starts with it.
    """
    return re.compile(rf"^\s*(?:{trigger})\b(?:{_SEP}(?P<arg>{arg}))?\s*$", re.I)


#: (name, pattern, handler). Order matters — the first match wins, so the
#: "<query> on youtube" phrasings are listed before the bare triggers.
COMMANDS: list[tuple[str, re.Pattern, object]] = [
    ("help", _no_arg(r"/help|/commands|what can you do"), show_help),
    (
        "time",
        _no_arg(
            r"/time|(?:what(?:'s| is)?\s+)?(?:the\s+)?(?:current\s+)?time"
            r"|what time is it(?:\s+now)?|tell me the time"
        ),
        tell_time,
    ),
    (
        "date",
        _no_arg(
            r"/date|(?:what(?:'s| is)?\s+)?(?:the\s+|today'?s\s+)?date"
            r"|what day is it(?:\s+today)?|tell me the date"
        ),
        tell_date,
    ),
    (
        "joke",
        _no_arg(
            r"/joke|(?:tell|say|give)\s+me\s+(?:a|another)\s+joke"
            r"|(?:another\s+)?joke(?:\s+please)?|make me laugh"
        ),
        tell_joke,
    ),
    # "<query> on wikipedia" / "<query> on youtube" — listed first so the
    # trailing-site phrasing wins over the leading-trigger patterns below.
    (
        "wikipedia-suffix",
        re.compile(
            rf"^\s*(?:look\s+up|search(?:\s+for)?)\s+(?P<arg>.+?)\s+on\s+wikipedia{_END}", re.I
        ),
        wikipedia_lookup,
    ),
    (
        "youtube-suffix",
        re.compile(
            rf"^\s*(?:play|search(?:\s+for)?|find)\s+(?P<arg>.+?)\s+on\s+youtube{_END}", re.I
        ),
        youtube_search,
    ),
    (
        "sentiment",
        _with_arg(
            r"/sentiment|sentiment(?:\s+analysis)?(?:\s+(?:of|on|for))?"
            r"|analy[sz]e\s+sentiment(?:\s+of)?"
        ),
        analyse_sentiment,
    ),
    (
        "wikipedia",
        _with_arg(r"/wiki(?:pedia)?|wikipedia|search wikipedia for", arg=_NOT_SENTENCE + r"\S.*"),
        wikipedia_lookup,
    ),
    (
        "youtube",
        _with_arg(r"/youtube|youtube|search youtube for", arg=_NOT_SENTENCE + r"\S.*"),
        youtube_search,
    ),
    # Deliberately narrow: a bare leading "search"/"google" is far more often a
    # normal question ("search algorithms explained") than a command.
    (
        "search",
        re.compile(
            rf"^\s*(?:/search|search\s+(?:the\s+web\s+)?for|search\s+google\s+for"
            rf"|google\s+for){_SEP}?(?P<arg>\S.*)$",
            re.I,
        ),
        web_search,
    ),
    # A single bare token only, so "open a file in python" stays a Gemini question.
    (
        "open",
        _with_arg(r"/open|open(?:\s+the)?(?:\s+(?:website|site))?", arg=r"\S+"),
        open_website,
    ),
]


def handle_command(text: str) -> ToolReply | None:
    """
    Run ``text`` against the local skills.

    Returns ``None`` when nothing matches, which is the signal to fall through
    to Gemini.
    """
    if not text or not text.strip():
        return None

    for _name, pattern, handler in COMMANDS:
        match = pattern.match(text)
        if match is not None:
            return handler(match)  # type: ignore[operator]
    return None
