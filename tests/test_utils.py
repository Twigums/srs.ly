import pytest
from src.utils import expand_meanings


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
