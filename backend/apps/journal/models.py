import re

from django.db import models

from .entries import JournalEntry  # noqa: F401  (registered via this module)
from .wellness import DailyMetrics  # noqa: F401  (registered via this module)

from apps.athletes.models import OwnedByAthlete


class DailyLog(OwnedByAthlete):
    """Free-text daily entry — what you ate, drank, how you slept, how you feel.

    The raw text is the record and is never overwritten. Structured fields are a
    best-effort extraction on top of it, so a better parser (or an LLM) can be run
    over the history later without losing anything the athlete actually wrote.
    """

    log_date = models.DateField(db_index=True)
    text = models.TextField()

    # Extracted, not authored. `extraction_version` records how they were derived so
    # a re-parse can find rows that predate an improved extractor.
    alcohol_units = models.FloatField(null=True, blank=True)
    sleep_hours = models.FloatField(null=True, blank=True)
    felt = models.CharField(max_length=12, blank=True)

    # Pain is the highest-value thing in a training log: injury ends more first
    # training blocks than anything else, and it is always mentioned in passing
    # before it becomes serious. The body part is captured so a recurring niggle in
    # one place is visible rather than buried in prose.
    # People describe sleep in words far more often than in hours. "slept late",
    # "up half the night", "couldn't switch off" all carry the same signal as a
    # number, and ignoring them made the log feel broken when it was merely literal.
    sleep_quality = models.CharField(max_length=12, blank=True, help_text="short | poor | good")

    pain_area = models.CharField(max_length=24, blank=True)
    illness = models.BooleanField(default=False)
    stressed = models.BooleanField(default=False)
    travel = models.BooleanField(default=False)

    extraction_version = models.PositiveSmallIntegerField(default=2)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-log_date", "-created_at"]
        indexes = [models.Index(fields=["athlete", "log_date"])]
        constraints = [
            models.UniqueConstraint(fields=["athlete", "log_date"], name="uniq_athlete_log_day")
        ]

    def __str__(self):
        return f"{self.log_date}: {self.text[:40]}"

    def save(self, *args, **kwargs):
        extracted = extract(self.text)
        self.alcohol_units = extracted["alcohol_units"]
        self.sleep_hours = extracted["sleep_hours"]
        self.felt = extracted["felt"]
        self.sleep_quality = extracted["sleep_quality"]
        self.pain_area = extracted["pain_area"]
        self.illness = extracted["illness"]
        self.stressed = extracted["stressed"]
        self.travel = extracted["travel"]
        super().save(*args, **kwargs)


EXTRACTION_VERSION = 3

# Rough standard-drink equivalents. Deliberately coarse — the goal is "did you drink
# and roughly how much", which is all the correlation analysis can support anyway.
# Singular forms only — the matcher appends an optional plural, so "whisky" also
# catches "whiskys" and "whiskies" without needing every spelling listed.
DRINK_UNITS = {
    "beer": 1.0, "pint": 1.4, "lager": 1.0, "ale": 1.0, "cider": 1.4,
    "wine": 1.5, "glass": 1.5,
    "whisky": 1.0, "whiskey": 1.0, "vodka": 1.0, "rum": 1.0, "gin": 1.0,
    "tequila": 1.0, "brandy": 1.0, "shot": 1.0, "peg": 1.0,
    "cocktail": 1.5, "drink": 1.0,
}

# Body parts worth tracking for a runner, with the words people actually type.
BODY_PARTS = {
    "knee": ["knee", "knees", "patella"],
    "shin": ["shin", "shins", "shin splint", "shin splints"],
    "achilles": ["achilles", "heel", "heels"],
    "calf": ["calf", "calves"],
    "hamstring": ["hamstring", "hamstrings"],
    "hip": ["hip", "hips", "glute", "glutes"],
    "foot": ["foot", "feet", "arch", "plantar", "toe", "toes"],
    "ankle": ["ankle", "ankles"],
    "back": ["back", "lower back"],
    "it_band": ["it band", "itb", "iliotibial"],
}

# Qualitative sleep, as regexes rather than fixed phrases. People write "sleeping a
# bit late" and "went to bed really late", so up to two filler words are allowed
# inside each pattern — exact substrings missed the way anyone actually types.
_FILL = r"(?:\w+\s+){0,2}"

SLEEP_SHORT = [
    # sle(?:ep|pt) because "slept" is not "sleep" plus a suffix — a plain sleep\w*
    # silently missed the single commonest way people write this.
    rf"sle(?:ep|pt)\w*\s+{_FILL}late",   # slept late / sleeping a bit late
    rf"(?:up|awake)\s+{_FILL}late",       # up late / up really late
    rf"(?:went to bed|bed)\s+{_FILL}late",
    r"late\s+night", r"stayed up", r"short night", r"early start",
    rf"(?:not much|little|hardly any|barely any)\s+sleep",
    r"(?:hardly|barely)\s+slept",
    rf"only\s+{_FILL}hours?\s+(?:of\s+)?sleep",
]
SLEEP_POOR = [
    r"(?:did ?n[o']?t|could ?n[o']?t)\s+sleep",
    rf"sle(?:ep|pt)\w*\s+{_FILL}(?:badly|poorly|terribly)",
    r"(?:bad|poor|broken|rough|terrible|awful)\s+(?:night|sleep)",
    r"rough night", r"restless", r"kept waking", r"tossing and turning",
    r"sleep was (?:bad|poor|terrible|awful)",
]
SLEEP_GOOD = [
    rf"slept\s+{_FILL}(?:well|great|brilliantly)",
    r"(?:good|great|solid|deep)\s+sleep", r"slept like a log",
    r"(?:well|fully)\s+rested",
]

PAIN_WORDS = ["pain", "hurt", "hurts", "sore", "ache", "aches", "aching", "tight",
              "tightness", "niggle", "twinge", "stiff", "strain", "sprain", "swollen"]

ILLNESS_WORDS = ["sick", "ill", "unwell", "cold", "flu", "fever", "cough",
                 "sore throat", "infection", "food poisoning", "stomach bug"]

STRESS_WORDS = ["stress", "stressed", "stressful", "anxious", "overwhelmed",
                "deadline", "exhausting day", "long day at work"]

TRAVEL_WORDS = ["flight", "flying", "flew", "travel", "travelling", "traveling",
                "airport", "train journey", "road trip", "jet lag", "jetlag"]

FEELINGS = {
    "great": "great", "good": "good", "fine": "ok", "ok": "ok", "okay": "ok",
    "tired": "tired", "exhausted": "tired", "sore": "sore", "heavy": "sore",
    "sick": "unwell", "ill": "unwell", "unwell": "unwell", "rough": "unwell",
}

_NUM_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8,
}


def _to_number(token: str) -> float | None:
    token = token.strip().lower()
    if token in _NUM_WORDS:
        return float(_NUM_WORDS[token])
    try:
        return float(token)
    except ValueError:
        return None


def extract(text: str) -> dict:
    """Keyword extraction from a free-text entry.

    Intentionally simple and conservative: it returns None rather than guessing.
    Swap for an LLM call when an API key is configured — the raw text is retained
    precisely so that upgrade can be applied retroactively.
    """
    if not text:
        return {"alcohol_units": None, "sleep_hours": None, "sleep_quality": "",
                "felt": "", "pain_area": "", "illness": False,
                "stressed": False, "travel": False}

    lower = text.lower()

    # Collect every drink mention with its span, then merge overlapping or adjacent
    # ones. "three pegs of whisky" is one drink phrase, not a peg plus a whisky —
    # counting both gave 4 units for 3 drinks, and alcohol feeds the readiness rules.
    matches = []
    for word, units in DRINK_UNITS.items():
        # Plurals without listing every spelling. Words ending in -y also take the
        # y->ies form ("whisky" -> "whiskies"), which a plain suffix cannot produce.
        stem = re.escape(word)
        plural = (rf"(?:{stem}(?:s)?|{re.escape(word[:-1])}ies)"
                  if word.endswith("y") else rf"{stem}(?:s|es)?")
        pattern = rf"(\b[\w.]+\s+)?{plural}\b"
        for match in re.finditer(pattern, lower):
            qty_text = (match.group(1) or "").strip()
            qty = _to_number(qty_text) if qty_text else None
            matches.append({
                "start": match.start(), "end": match.end(),
                "units": units, "qty": qty, "explicit": qty is not None,
            })

    matches.sort(key=lambda m: m["start"])
    merged: list[dict] = []
    for m in matches:
        prev = merged[-1] if merged else None
        # Merge only across a genuine measure-of-drink phrase — "pegs of whisky",
        # "glasses of wine". A character-distance window was too blunt: it also
        # swallowed "a beer and two whiskys", counting three drinks as one.
        gap = lower[prev["end"]:m["start"]] if prev else ""
        joins = bool(re.fullmatch(r"\s*(of\s+(a|the|some)?\s*)?", gap))
        if prev and joins:
            if m["explicit"] and not prev["explicit"]:
                prev["qty"], prev["explicit"] = m["qty"], True
            prev["units"] = max(prev["units"], m["units"])
            prev["end"] = max(prev["end"], m["end"])
            continue
        merged.append(dict(m))

    alcohol = None
    for m in merged:
        alcohol = (alcohol or 0.0) + (m["qty"] if m["explicit"] else 1.0) * m["units"]
    if alcohol is None and re.search(r"\b(no alcohol|didn'?t drink|sober|teetotal)\b", lower):
        alcohol = 0.0

    sleep = None
    sleep_match = re.search(r"(?:slept|sleep)\D{0,12}(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hours)?", lower)
    if not sleep_match:
        sleep_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hours)\s*(?:of\s*)?sleep", lower)
    if sleep_match:
        value = float(sleep_match.group(1))
        if 0 < value <= 16:
            sleep = value

    felt = ""
    for word, label in FEELINGS.items():
        if re.search(rf"\b{word}\b", lower):
            felt = label
            break

    # A body part only counts as pain when a pain word appears near it — "ran on my
    # feet" is not a foot injury, and flagging it would train the athlete to ignore
    # the warnings that matter.
    pain_area = ""
    if any(re.search(rf"\b{re.escape(w)}\b", lower) for w in PAIN_WORDS):
        for area, words in BODY_PARTS.items():
            for word in words:
                match = re.search(rf"\b{re.escape(word)}\b", lower)
                if not match:
                    continue
                window = lower[max(0, match.start() - 45): match.end() + 45]
                if any(re.search(rf"\b{re.escape(p)}\b", window) for p in PAIN_WORDS):
                    pain_area = area
                    break
            if pain_area:
                break

    # Only consulted when no number was given — an explicit "slept 7 hours" beats
    # any adjective in the same sentence.
    sleep_quality = ""
    if sleep is None:
        if any(re.search(p, lower) for p in SLEEP_POOR):
            sleep_quality = "poor"
        elif any(re.search(p, lower) for p in SLEEP_SHORT):
            sleep_quality = "short"
        elif any(re.search(p, lower) for p in SLEEP_GOOD):
            sleep_quality = "good"

    illness = any(re.search(rf"\b{re.escape(w)}\b", lower) for w in ILLNESS_WORDS)
    stressed = any(re.search(rf"\b{re.escape(w)}\b", lower) for w in STRESS_WORDS)
    travel = any(re.search(rf"\b{re.escape(w)}\b", lower) for w in TRAVEL_WORDS)

    return {
        "alcohol_units": alcohol, "sleep_hours": sleep, "sleep_quality": sleep_quality,
        "felt": felt, "pain_area": pain_area, "illness": illness,
        "stressed": stressed, "travel": travel,
    }
