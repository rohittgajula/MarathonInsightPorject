import re

from django.db import models

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
    extraction_version = models.PositiveSmallIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-log_date", "-created_at"]
        indexes = [models.Index(fields=["athlete", "log_date"])]

    def __str__(self):
        return f"{self.log_date}: {self.text[:40]}"

    def save(self, *args, **kwargs):
        extracted = extract(self.text)
        self.alcohol_units = extracted["alcohol_units"]
        self.sleep_hours = extracted["sleep_hours"]
        self.felt = extracted["felt"]
        super().save(*args, **kwargs)


EXTRACTION_VERSION = 1

# Rough standard-drink equivalents. Deliberately coarse — the goal is "did you drink
# and roughly how much", which is all the correlation analysis can support anyway.
DRINK_UNITS = {
    "beer": 1.0, "beers": 1.0, "pint": 1.4, "pints": 1.4,
    "wine": 1.5, "glass of wine": 1.5, "glasses of wine": 1.5,
    "whisky": 1.0, "whiskey": 1.0, "vodka": 1.0, "rum": 1.0,
    "gin": 1.0, "cocktail": 1.5, "cocktails": 1.5, "drink": 1.0, "drinks": 1.0,
    "peg": 1.0, "pegs": 1.0,
}

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
        return {"alcohol_units": None, "sleep_hours": None, "felt": ""}

    lower = text.lower()

    alcohol = None
    for word, units in DRINK_UNITS.items():
        for match in re.finditer(rf"(\b[\w.]+\s+)?{re.escape(word)}\b", lower):
            qty = _to_number(match.group(1) or "1") or 1.0
            alcohol = (alcohol or 0.0) + qty * units
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

    return {"alcohol_units": alcohol, "sleep_hours": sleep, "felt": felt}
