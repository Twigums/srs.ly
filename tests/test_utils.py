import pytest
from src.utils import expand_meanings, spoken_to_hiragana, spoken_to_meaning


class TestExpandMeanings:
    """Tests for issue #41: split correctly when () are used in meanings."""

    def test_simple_string_no_parens(self):
        assert expand_meanings("simple") == ["simple"]

    def test_multiple_simple_no_parens(self):
        assert expand_meanings("to eat, to consume") == ["to eat", "to consume"]

    def test_parens_with_options_expands(self):
        # "riding (a car, a train, a bike)" -> riding + riding + each option
        result = expand_meanings("riding (a car, a train, a bike)")
        assert result == ["riding", "riding a car", "riding a train", "riding a bike"]

    def test_mixed_parens_and_plain(self):
        # "a (b, c, d), e, f" -> a, a b, a c, a d, e, f
        result = expand_meanings("a (b, c, d), e, f")
        assert result == ["a", "a b", "a c", "a d", "e", "f"]

    def test_parens_only_base_empty(self):
        # "(option1, option2)" with no base -> just the options
        result = expand_meanings("(option1, option2)")
        assert result == ["option1", "option2"]

    def test_whitespace_trimmed(self):
        result = expand_meanings("  to eat  ,  to drink  ")
        assert result == ["to eat", "to drink"]

    def test_single_option_in_parens(self):
        result = expand_meanings("to eat (something)")
        assert result == ["to eat", "to eat something"]

    def test_multiple_groups_with_parens(self):
        # Two paren groups
        result = expand_meanings("ride (a car, a bike), hold (a pen)")
        assert result == ["ride", "ride a car", "ride a bike", "hold", "hold a pen"]

    def test_empty_string(self):
        assert expand_meanings("") == []

    def test_leading_parens_single_option(self):
        # "(foo) bar" -> ["foo bar", "bar"]
        result = expand_meanings("(foo) bar")
        assert result == ["foo bar", "bar"]

    def test_leading_parens_multiple_options(self):
        # "(foo, baz) bar" -> ["foo bar", "baz bar", "bar"]
        result = expand_meanings("(foo, baz) bar")
        assert result == ["foo bar", "baz bar", "bar"]


class TestSpokenToHiragana:
    """Issue #43: Japanese transcripts are checked as hiragana."""

    def test_kanji_converted_to_reading(self):
        assert spoken_to_hiragana("帰ります") == "かえります"

    def test_katakana_converted_to_hiragana(self):
        assert spoken_to_hiragana("コーヒー") == "こーひー"

    def test_punctuation_and_spaces_removed(self):
        assert spoken_to_hiragana(" かえります。") == "かえります"
        assert spoken_to_hiragana("まがります？") == "まがります"

    def test_hiragana_unchanged(self):
        assert spoken_to_hiragana("ほうがいい") == "ほうがいい"

    def test_empty_string(self):
        assert spoken_to_hiragana("") == ""


class TestSpokenToMeaning:
    """Issue #43: English transcripts lose the punctuation whisper adds."""

    def test_lowercased_and_period_removed(self):
        assert spoken_to_meaning("To compare.") == "to compare"

    def test_apostrophes_and_hyphens_kept(self):
        assert spoken_to_meaning("Isn’t it?") == "isn't it"
        assert spoken_to_meaning("Well-known") == "well-known"

    def test_whitespace_collapsed(self):
        assert spoken_to_meaning("  to   go  home ") == "to go home"

    def test_empty_string(self):
        assert spoken_to_meaning("") == ""
