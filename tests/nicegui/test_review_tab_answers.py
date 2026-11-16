from collections import deque
from types import MethodType, SimpleNamespace
from unittest.mock import MagicMock, patch

from nicegui.events import KeyEventArguments, KeyboardAction, KeyboardKey, KeyboardModifiers

from src.nicegui.review_tab import ReviewTab


# ---------------------------------------------------------------------------
# ReviewTab.handle_key, called on a stand-in for the tab
# ---------------------------------------------------------------------------

def _key(name, *, ctrl = False):
    return KeyEventArguments(
        sender = MagicMock(),
        client = MagicMock(),
        action = KeyboardAction(keydown = True, keyup = False, repeat = False),
        key = KeyboardKey(name = name, code = "", location = 0),
        modifiers = KeyboardModifiers(alt = False, ctrl = ctrl, meta = False, shift = False),
    )


def _fake_tab(srs_app, card_type, item_id = 1):
    return SimpleNamespace(
        current_item = {"card_type": card_type, "ID": item_id},
        item_dict = {},
        key_quit_after_current_set = "e",
        key_ignore_answer = "Backspace",
        key_add_as_valid_response = "=",
        res_display = SimpleNamespace(text = ""),
        correct_reading_display = SimpleNamespace(visible = True),
        correct_meaning_display = SimpleNamespace(visible = True),
        text_buffer = "",
        kana_output = "",
        user_hiragana = SimpleNamespace(text = ""),
        user_romaji = SimpleNamespace(text = ""),
        update_review_display = MagicMock(),
        srs_app = srs_app,
        alphabet = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!?-",
        incorrect_message = "❌",
    )


def _type(tab, text):
    with patch("src.nicegui.review_tab.ui"):
        for char in text:
            ReviewTab.handle_key(tab, _key(char))


class TestTypingAnAnswer:
    def test_reading_card_shows_kana(self, mock_srs_app):
        tab = _fake_tab(mock_srs_app, "reading")

        _type(tab, "taberu")

        assert tab.user_hiragana.text == "たべる"
        assert tab.user_romaji.text == "taberu"
        assert tab.kana_output == "たべる"

    def test_meaning_card_shows_what_was_typed(self, mock_srs_app):
        tab = _fake_tab(mock_srs_app, "meaning")

        _type(tab, "to eat")

        assert tab.user_hiragana.text == "to eat"
        assert tab.user_romaji.text == "to eat"

    def test_backspace_on_reading_card_removes_a_whole_kana(self, mock_srs_app):
        tab = _fake_tab(mock_srs_app, "reading")
        _type(tab, "taberu")

        with patch("src.nicegui.review_tab.ui"):
            ReviewTab.handle_key(tab, _key("Backspace"))

        assert tab.user_hiragana.text == "たべ"
        assert tab.text_buffer == "tabe"


# ---------------------------------------------------------------------------
# Recording answers: each correct answer appends 1 to item_dict[item_id] and
# each submitted wrong answer appends 0; when both cards of an item are
# correct, the item is graded (passed only if nothing was ever failed)
# ---------------------------------------------------------------------------

CARD = {"ID": 1, "card_type": "reading", "Readings": "たべる", "Meanings": "to eat"}


def _answering_tab(srs_app, item_dict):
    tab = _fake_tab(srs_app, "reading")
    tab.current_item = dict(CARD)
    tab.item_dict = item_dict
    tab.correct_reading_display = SimpleNamespace(text = "", visible = False)
    tab.correct_meaning_display = SimpleNamespace(text = "", visible = False)
    tab.correct_message = "✅"
    tab.clean_card = MethodType(ReviewTab.clean_card, tab)
    srs_app.current_reviews = deque([dict(CARD), {"ID": 2}])
    return tab


def _answer(tab, answer, will_submit = False):
    with patch("src.nicegui.review_tab.ui"), patch("src.nicegui.review_tab.app"), \
         patch("src.nicegui.review_tab.save_review_state"):
        ReviewTab.process_answer(tab, answer, will_submit = will_submit)


class TestProcessAnswer:
    def test_correct_answer_is_recorded(self, mock_srs_app):
        tab = _answering_tab(mock_srs_app, {})

        _answer(tab, "たべる")

        assert tab.item_dict == {1: [1]}
        assert tab.res_display.text == "✅"
        assert [card["ID"] for card in mock_srs_app.current_reviews] == [2]
        mock_srs_app.update_review_item.assert_not_called()

    def test_wrong_answer_waits_at_the_end_of_the_queue(self, mock_srs_app):
        tab = _answering_tab(mock_srs_app, {})

        _answer(tab, "のむ")

        assert tab.item_dict.get(1, []) == []
        assert tab.res_display.text == "❌"
        assert [card["ID"] for card in mock_srs_app.current_reviews] == [2, 1]

    def test_submitted_wrong_answer_is_recorded_as_a_failure(self, mock_srs_app):
        tab = _answering_tab(mock_srs_app, {})

        _answer(tab, "のむ", will_submit = True)

        assert tab.item_dict == {1: [0]}

    def test_both_cards_right_first_time_passes_the_item(self, mock_srs_app):
        tab = _answering_tab(mock_srs_app, {1: [1]})

        _answer(tab, "たべる")

        mock_srs_app.update_review_item.assert_called_once_with(1, True)
        mock_srs_app.update_review_session.assert_called_once()
        assert 1 not in tab.item_dict

    def test_a_failed_card_fails_the_item(self, mock_srs_app):
        tab = _answering_tab(mock_srs_app, {1: [0, 1]})

        _answer(tab, "たべる")

        mock_srs_app.update_review_item.assert_called_once_with(1, False)
        assert 1 not in tab.item_dict


class TestAddAsValidResponse:
    """The "=" key after a wrong answer: the typed answer becomes valid and counts as correct."""

    def _press_equals(self, mock_srs_app, item_dict):
        tab = _answering_tab(mock_srs_app, item_dict)
        _answer(tab, "のむ")    # wrong: the card moves to the end of the queue
        tab.text_buffer = "nomu"
        tab.user_hiragana.text = "のむ"

        with patch("src.nicegui.review_tab.ui"):
            result = ReviewTab.handle_key(tab, _key("="))

        return tab, result

    def test_adds_the_answer_and_drops_the_wrong_card(self, mock_srs_app):
        tab, result = self._press_equals(mock_srs_app, {})

        assert result == "add answer"
        mock_srs_app.add_valid_response.assert_called_once_with("のむ", tab.current_item)
        assert [card["ID"] for card in mock_srs_app.current_reviews] == [2]
        assert tab.item_dict == {1: [1]}
        assert tab.res_display.text == "Added 'のむ' to reading."

    def test_clears_the_answer_and_shows_the_next_card(self, mock_srs_app):
        tab, _ = self._press_equals(mock_srs_app, {})

        assert (tab.text_buffer, tab.kana_output, tab.user_romaji.text, tab.user_hiragana.text) == ("", "", "", "")
        tab.update_review_display.assert_called_once()

    def test_completes_the_item_when_the_other_card_was_right(self, mock_srs_app):
        tab, _ = self._press_equals(mock_srs_app, {1: [1]})

        mock_srs_app.update_review_item.assert_called_once_with(1, True)
        mock_srs_app.update_review_session.assert_called_once()
        assert 1 not in tab.item_dict
