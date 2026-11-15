import pytest
from src.utils import expand_meanings, meaning_match_score

# default match_score_threshold in config.toml; answers must score above it
THRESHOLD = 85


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


class TestMeaningMatchScore:
    """Tests for issue #42: short meanings must be typed exactly."""

    @pytest.mark.parametrize("answer, meaning", [
        ("son", "soon"),    # scored ~85.7 with fuzzy matching and passed
        ("soon", "son"),
        ("bead", "bread"),  # 5 characters is still strict
    ])
    def test_short_meaning_rejects_near_miss(self, answer, meaning):
        assert meaning_match_score(answer, [meaning]) == 0

    def test_short_meaning_accepts_exact_match_ignoring_case_and_spaces(self):
        assert meaning_match_score("  Soon ", ["soon"]) == 100

    def test_longer_meaning_still_allows_typo(self):
        # 6 characters is past the strict cutoff, so fuzzy matching applies
        assert meaning_match_score("frend", ["friend"]) > THRESHOLD

    def test_best_scoring_meaning_wins(self):
        assert meaning_match_score("before lng", ["soon", "before long"]) > THRESHOLD

    def test_blank_answer_never_matches(self):
        assert meaning_match_score("  ", ["", "soon"]) == 0
