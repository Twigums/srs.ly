from types import SimpleNamespace
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
