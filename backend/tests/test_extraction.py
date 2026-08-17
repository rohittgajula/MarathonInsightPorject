"""Daily-log extraction.

Locked down with tests because it is keyword matching over free text, which is
exactly the kind of code that silently regresses. Alcohol in particular feeds the
readiness rules that change tomorrow's session, so a double-count is not cosmetic.
"""

import pytest

from apps.journal.models import extract


class TestAlcohol:
    @pytest.mark.parametrize("text,expected", [
        ("two beers and biryani", 2.0),
        ("a glass of wine", 1.5),
        ("two glasses of wine with dinner", 3.0),
        ("four pints at the pub", 5.6),
        ("one shot of tequila", 1.0),
        ("no alcohol today", 0.0),
    ])
    def test_counts_simple_cases(self, text, expected):
        assert extract(text)["alcohol_units"] == pytest.approx(expected)

    @pytest.mark.parametrize("text", ["three pegs of whisky at dinner", "two glasses of wine"])
    def test_measure_of_drink_counts_once(self, text):
        """'pegs of whisky' is one phrase; counting the measure and the drink
        separately reported four units for three drinks."""
        assert extract(text)["alcohol_units"] < 3.5

    @pytest.mark.parametrize("text,expected", [
        ("had a beer and two whiskys", 3.0),
        ("two beers then three whiskies", 5.0),
    ])
    def test_separate_drinks_are_not_merged(self, text, expected):
        """Drinks joined by 'and'/'then' are distinct — only 'X of Y' collapses."""
        assert extract(text)["alcohol_units"] == pytest.approx(expected)

    def test_silence_is_not_zero(self):
        """No mention means unknown, not teetotal — a zero would be a claim."""
        assert extract("felt good today")["alcohol_units"] is None


class TestSleep:
    @pytest.mark.parametrize("text,expected", [
        ("slept 5.5 hours", 5.5),
        ("slept 7 hrs", 7.0),
        ("4 hours of sleep", 4.0),
    ])
    def test_reads_sleep(self, text, expected):
        assert extract(text)["sleep_hours"] == pytest.approx(expected)

    def test_rejects_impossible_values(self):
        assert extract("slept 40 hours")["sleep_hours"] is None


class TestPain:
    @pytest.mark.parametrize("text,area", [
        ("left knee felt tight on the stairs", "knee"),
        ("shin splints again, quite sore", "shin"),
        ("achilles a bit stiff this morning", "achilles"),
    ])
    def test_finds_the_body_part(self, text, area):
        assert extract(text)["pain_area"] == area

    def test_body_part_without_pain_is_not_an_injury(self):
        """'on my feet all day' is not a foot injury. False alarms here would train
        the athlete to ignore the warnings that matter."""
        assert extract("ran on my feet all day at work, no issues")["pain_area"] == ""

    def test_pain_word_alone_needs_a_location(self):
        assert extract("everything aches today")["pain_area"] == ""


class TestOtherSignals:
    def test_illness(self):
        assert extract("coming down with a cold, sore throat")["illness"] is True

    def test_travel(self):
        assert extract("flying to Delhi tomorrow")["travel"] is True

    def test_stress(self):
        assert extract("stressful day, deadline at work")["stressed"] is True

    def test_feeling(self):
        assert extract("felt great, legs fresh")["felt"] == "great"

    def test_plain_text_extracts_nothing(self):
        result = extract("went for a run around the lake")
        assert result["pain_area"] == "" and not result["illness"] and not result["travel"]
