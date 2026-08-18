"""Claude-backed reading of a free-text daily log.

The keyword extractor in `models.extract` was always a placeholder — CONTEXT.md
records the intent to swap an LLM in, and the raw text has been stored verbatim
since day one precisely so the swap can be re-run over history. This is that swap.

**The model reads language. It does not make training decisions.**

That split is the whole design and it is not negotiable. Claude turns prose into
structured facts — "my feet hurt while running" becomes an area, a severity, and
*when* it hurt. Everything downstream of that — whether the session is eased, which
exercises are prescribed, how much water to drink — stays in ordinary Python in
`readiness.py`, `exercises.py`, and `fueling.py`, scored against the athlete's own
numbers.

Two reasons, both load-bearing:

- Every claim in this app cites a number the system holds. A model that decided the
  plan directly could not cite anything, and its reasoning could not be reviewed
  after the fact.
- Readiness rules only ever make a session easier. That guarantee is enforced by
  code that a hallucination cannot reach. Handing the plan to a model would be
  handing away the one rule that makes an automated coach safe.

So the failure mode of a bad extraction is a wrong *fact* — visible, correctable by
editing the log — rather than a wrong *prescription*.

Cost and latency are why this runs in a Celery task rather than in the request:
a log must save instantly and must save even when the API is down or unkeyed.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)


class AuthFailed(Exception):
    """The provider rejected the key.

    Separated from a generic failure because it is the one failure mode the athlete
    can actually fix, and "couldn't read this entry" gives them nothing to act on.
    """


class RateLimited(Exception):
    """The provider is out of quota for now.

    Distinct from a failure on purpose: a failure means this entry could not be
    read, a rate limit means it has not been read *yet*. Recording the two the same
    way tells the athlete their note was unreadable when the truth is "try again in
    a minute", and stops any sweep from ever picking it back up.
    """

# Two backends, one schema. Which one runs is decided by whichever key is present,
# or forced with LOG_AI_PROVIDER=anthropic|gemini.
#
# Gemini is the default in practice because it has a free tier and this app is a
# personal project that should not require a billing relationship to work. Claude is
# kept because the schema was written against it and it reads casual, code-switched
# Indian English more reliably — worth the pennies if credits ever exist.
#
# The two agree on the schema dialect this file uses: `anyOf`, `enum`, `required`
# and `additionalProperties: false` are honoured by both, so nothing below is
# provider-specific except the transport.
ANTHROPIC_MODEL = "claude-opus-5"
GEMINI_MODEL = "gemini-3.7-flash"

# The log is a sentence or two, and the box is interactive — the athlete is watching
# for the chips to fill in. Opus 5 is unusually strong at the low end of the effort
# range, and this is a short scoped extraction rather than a reasoning problem.
# (Anthropic only; Gemini has no equivalent knob on this call.)
EFFORT = "medium"

# Bumped when the schema or the prompt changes materially, so `reparse_logs` can find
# the rows that predate the change. Keep ahead of the keyword extractor's version.
AI_EXTRACTION_VERSION = 11

# Matches `models.BODY_PARTS` so the two extractors are interchangeable downstream
# and `niggles.py` keeps working unchanged.
PAIN_AREAS = [
    "knee", "shin", "achilles", "calf", "hamstring", "hip",
    "foot", "ankle", "back", "it_band", "quad", "groin", "chest", "other",
]

FEELINGS = ["great", "good", "ok", "tired", "sore", "unwell"]


def _nullable(inner: dict) -> dict:
    """`inner`, or null.

    Spelled as `anyOf` rather than a `["string", "null"]` type array: structured
    outputs document `anyOf` and the basic types, and the union-array form is not
    among them. Being able to answer "I don't know" is the point — a model required
    to pick one of six feelings will invent one — so every optional field needs a
    null it is allowed to return.
    """
    return {"anyOf": [inner, {"type": "null"}]}


def _enum(values: list[str]) -> dict:
    return _nullable({"type": "string", "enum": values})


# Structured outputs reject numeric range keywords (`minimum`/`maximum`) and length
# constraints, so bounded integers are spelled as enums instead.
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "applies_to_offset_days", "date_reason", "summary",
        "sleep_hours", "sleep_quality", "alcohol_units", "caffeine_late",
        "felt", "illness", "stressed", "travel",
        "pain", "meals", "hydration_note", "training", "unparsed",
    ],
    "properties": {
        # The question the athlete asked for by name: is this entry about today or
        # about tomorrow? A note typed at 23:40 saying "early run in the morning" is
        # about tomorrow's session; "knee was sore on the run" is about today.
        "applies_to_offset_days": {
            "type": "integer", "enum": [-1, 0, 1],
            "description": (
                "Which day's TRAINING SESSION this entry bears on, relative to the "
                "date it was written. Not which calendar day the words refer to — "
                "which session's readiness it should affect.\n"
                "0 = the day it was written. This includes anything about LAST "
                "NIGHT's sleep, food, or drink: a bad night is what you carry into "
                "today's session, so 'last night I slept badly' or 'couldn't sleep' "
                "is 0, NOT -1.\n"
                "-1 = it reports on a session or event that already happened before "
                "the day of writing ('yesterday I ran 3k', 'Monday's run felt "
                "awful').\n"
                "1 = it is about a session still to come, written the evening "
                "before ('early run tomorrow', 'heading to bed, race in the "
                "morning').\n"
                "When an entry mixes days, choose the session the content most "
                "affects. Default to 0 when unclear."
            ),
        },
        "date_reason": {
            "type": "string",
            "description": "One short sentence naming the words that decided the day.",
        },
        "summary": {
            "type": "string",
            "description": "One plain sentence restating the entry. No advice, no interpretation.",
        },
        "sleep_hours": {
            **_nullable({"type": "number"}),
            "description": "Hours slept, only when a duration is stated or directly implied by times given ('1am to 7am' = 6). Null otherwise.",
        },
        "sleep_quality": {
            **_enum(["short", "poor", "good"]),
            "description": "Qualitative sleep when no number is given. 'short' = too little, 'poor' = broken or unrefreshing, 'good' = slept well.",
        },
        "alcohol_units": {
            **_nullable({"type": "number"}),
            "description": "UK-style standard units. A beer or single spirit is 1, a large glass of wine or a pint is 1.5. 0 when they say they did not drink. Null when alcohol is not mentioned.",
        },
        "caffeine_late": {
            "type": "boolean",
            "description": "True only when coffee, tea, or an energy drink is mentioned in the evening or close to bedtime.",
        },
        "felt": {**_enum(FEELINGS), "description": "Overall how they say they feel."},
        "illness": {"type": "boolean", "description": "Any sickness, fever, infection, or stomach upset."},
        "stressed": {"type": "boolean", "description": "Work or life stress, anxiety, or being overwhelmed."},
        "travel": {"type": "boolean", "description": "Flights, long journeys, or jet lag."},

        "pain": {
            "type": "array",
            "description": (
                "One entry per distinct body area that hurts. Empty when nothing "
                "hurts. Only include a body part when the text actually says it "
                "hurts — 'ran on tired legs' is not leg pain."
            ),
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["area", "severity", "when", "side", "quote"],
                "properties": {
                    "area": {"type": "string", "enum": PAIN_AREAS},
                    "severity": {
                        "type": "integer", "enum": [1, 2, 3, 4, 5],
                        "description": "1 = barely noticed, 2 = niggle, 3 = clearly sore, 4 = hurts to run, 5 = hurts to walk.",
                    },
                    "when": {
                        "type": "string",
                        "enum": ["running", "after_running", "walking", "rest", "unclear"],
                        "description": "When it hurt. 'running' means during the run itself — the most serious case.",
                    },
                    "side": {"type": "string", "enum": ["left", "right", "both", "unspecified"]},
                    "quote": {"type": "string", "description": "The athlete's own words, verbatim."},
                },
            },
        },

        "meals": {
            "type": "array",
            "description": (
                "Food and drink worth a hydration or fuelling note. Skip anything "
                "unremarkable — plain rice, fruit, water. Include restaurant meals, "
                "fried or oily food, and anything heavily salted or spiced."
            ),
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["food", "salt", "richness", "spice", "timing", "quote"],
                "properties": {
                    "food": {"type": "string", "description": "The dish, as named or briefly described."},
                    "salt": {
                        "type": "string", "enum": ["low", "moderate", "high"],
                        "description": "Sodium load. Restaurant, fried, processed, and pickled foods are high.",
                    },
                    "richness": {
                        "type": "string", "enum": ["light", "moderate", "heavy"],
                        "description": "Fat and overall heaviness. Biryani, fried food, and creamy curries are heavy.",
                    },
                    "spice": {"type": "string", "enum": ["mild", "medium", "hot"]},
                    "timing": {
                        "type": "string", "enum": ["morning", "midday", "evening", "late_night", "unclear"],
                    },
                    "quote": {"type": "string", "description": "The athlete's own words, verbatim."},
                },
            },
        },

        "hydration_note": {
            **_nullable({"type": "string"}),
            "description": "Anything they say about drinking water or feeling thirsty or dehydrated. Null when not mentioned.",
        },

        "training": {
            "type": "object",
            "additionalProperties": False,
            "required": ["did_session", "skipped_session", "note"],
            "properties": {
                "did_session": {"type": "boolean", "description": "They say they ran, walked, or trained."},
                "skipped_session": {"type": "boolean", "description": "They say they missed or skipped the session."},
                "note": {**_nullable({"type": "string"}), "description": "How the session went, in one sentence. Null when no session is mentioned."},
            },
        },

        # An explicit place for "I read this and don't know what to do with it" is
        # what stops the model quietly folding an unrecognised sentence into a field
        # where it does not belong.
        "unparsed": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Anything in the entry that is training-relevant but fits none of the fields above. Empty when everything was captured.",
        },
    },
}


SYSTEM = """\
You read a runner's short daily training log and turn it into structured data.

You are a reader, not a coach. Extract what the athlete said. Do not diagnose, do \
not advise, do not decide anything about their training — separate code does that \
from your output, using their own recorded numbers.

Rules:
- Record only what the text supports. Null and false are correct answers, and are \
always better than a plausible guess. Under-reporting is recoverable; a fact the \
athlete never stated is not.
- Quote fields are verbatim from the entry. Never paraphrase into a quote.
- The athlete writes casually, in Indian English, often mixing languages, often \
with typos and no punctuation. Read for meaning, not spelling.
- Pain is the single most important thing you extract: it is what stops a training \
block. Catch it when it is mentioned in passing, and note whether it happened while \
running — that distinction changes what the plan does next.
- Judge food for its hydration and fuelling consequences, not its cuisine. A heavy, \
salty, or oily meal raises fluid needs the next morning whatever it is called.
"""


def provider() -> Optional[str]:
    """Which backend to use, or None when nothing is configured.

    An explicit LOG_AI_PROVIDER wins and does *not* silently fall through to the
    other one: being quietly billed by a provider you did not choose is worse than
    an entry staying on the keyword extractor.
    """
    forced = os.environ.get("LOG_AI_PROVIDER", "").strip().lower()
    if forced == "anthropic":
        return "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else None
    if forced == "gemini":
        return "gemini" if os.environ.get("GEMINI_API_KEY") else None

    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def configured() -> bool:
    """Whether any backend is available. Nothing here raises when none is."""
    return provider() is not None


# Clients are cached rather than built per call, for two reasons. The Celery worker
# is long-lived, so rebuilding a connection pool for every log entry is waste. More
# importantly, `genai.Client().interactions.create(...)` as a single expression lets
# the client be garbage-collected while the request is still in flight — it closes
# its httpx pool on the way out and the call dies with "client has been closed".
_CLIENTS: dict = {}


def _client(name: str, factory):
    if name not in _CLIENTS:
        _CLIENTS[name] = factory()
    return _CLIENTS[name]


def _call_anthropic(prompt: str) -> Optional[tuple[str, str]]:
    """(raw JSON, model id), or None. Never raises."""
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic SDK not installed")
        return None

    client = _client("anthropic", anthropic.Anthropic)
    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4000,
            system=SYSTEM,
            output_config={
                "format": {"type": "json_schema", "schema": SCHEMA},
                "effort": EFFORT,
            },
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        if _is_auth_error(exc):
            raise AuthFailed(str(exc)[:200])
        if _retry_after(exc) is not None:
            raise RateLimited(str(exc)[:200])
        logger.exception("Claude log extraction failed")
        return None

    # A safety decline arrives as a normal 200 with an empty content list, so the
    # stop reason has to be checked before the content is read.
    if response.stop_reason == "refusal":
        logger.warning("Claude declined to read a log entry: %s", response.stop_details)
        return None

    text = next((b.text for b in response.content if b.type == "text"), None)
    return (text, response.model) if text else None


# "Please retry in 44.745484768s." — the API tells you how long to wait, in prose.
_RETRY_RE = re.compile(r"retry in ([\d.]+)s", re.I)
_MAX_BACKOFF_S = 65.0


def _is_auth_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "'code': 401" in message or "code: 401" in message or "error code: 401" in message
        or "api key not valid" in message or "api_key_invalid" in message
        or "unauthenticated" in message or "permission_denied" in message
    )


def _retry_after(exc: Exception) -> Optional[float]:
    """Seconds to wait, when the exception is a rate limit. None otherwise."""
    message = str(exc)
    if "429" not in message and "too_many_requests" not in message.lower():
        return None
    match = _RETRY_RE.search(message)
    seconds = float(match.group(1)) + 1 if match else 30.0
    return min(seconds, _MAX_BACKOFF_S)


def _call_gemini(prompt: str) -> Optional[tuple[str, str]]:
    """(raw JSON, model id), or None. Never raises.

    The system text is prepended to the input rather than sent as a separate
    instruction: this is a single-turn extraction, the two are equivalent for it,
    and one code path is easier to keep honest than two.
    """
    try:
        from google import genai
    except ImportError:
        logger.warning("google-genai SDK not installed")
        return None

    client = _client("gemini", genai.Client)
    request = dict(
        model=GEMINI_MODEL,
        input=f"{SYSTEM}\n\n---\n\n{prompt}",
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": SCHEMA,
        },
    )

    # The free tier allows 20 requests a minute. One log a day never approaches
    # that, but a history re-parse does, and so does anyone testing. A 429 is a
    # "come back shortly", not a failure — retrying once on the delay the API
    # itself names is the difference between a re-parse that completes and one
    # that marks half the history failed.
    for attempt in (1, 2):
        try:
            interaction = client.interactions.create(**request)
            break
        except Exception as exc:
            if _is_auth_error(exc):
                raise AuthFailed(str(exc)[:200])
            wait = _retry_after(exc)
            if wait is None:
                logger.exception("Gemini log extraction failed")
                return None
            if attempt == 1:
                logger.warning("Gemini rate-limited; retrying in %.0fs", wait)
                time.sleep(wait)
                continue
            # Still limited after backing off — the daily allowance is gone, not
            # just a burst. Say so distinctly so the row is retried later rather
            # than written off.
            raise RateLimited(str(exc)[:200])

    text = getattr(interaction, "output_text", None)
    return (text, GEMINI_MODEL) if text else None


CALLS = {"anthropic": _call_anthropic, "gemini": _call_gemini}


def _context(athlete, written_on: dt.date, session=None) -> str:
    """What the model needs in order to resolve dates and read the entry in context.

    Deliberately small. The model is being asked to read one paragraph — feeding it
    the whole training history would cost tokens and invite it to reason about the
    plan, which is not its job.
    """
    lines = [
        f"The athlete wrote this on {written_on:%A %d %B %Y}.",
        f"Their local time zone is {athlete.timezone or 'UTC'}.",
    ]
    if session is not None:
        lines.append(
            f"That day's prescribed session was: {session.title} ({session.focus})."
        )
    return "\n".join(lines)


def analyse(text: str, athlete, written_on: dt.date, session=None) -> Optional[dict]:
    """Read one entry. Returns None when unavailable — never raises into a save.

    A None here is not an error state the athlete needs to see: the keyword
    extractor has already populated the row, so the log is complete either way.
    """
    if not text or not text.strip():
        return None

    backend = provider()
    if backend is None:
        return None

    prompt = f"{_context(athlete, written_on, session)}\n\nTheir entry:\n\n{text.strip()}"
    result = CALLS[backend](prompt)
    if result is None:
        return None

    raw, model_id = result
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.exception("%s returned unparseable JSON for a log entry", backend)
        return None

    if not isinstance(data, dict):
        logger.warning("%s returned %s rather than an object", backend, type(data).__name__)
        return None

    data["_model"] = model_id
    data["_provider"] = backend
    data["_version"] = AI_EXTRACTION_VERSION
    return data
