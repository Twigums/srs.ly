import asyncio
import base64
from types import MethodType, SimpleNamespace
from unittest.mock import MagicMock, patch

from nicegui.events import KeyEventArguments, KeyboardAction, KeyboardKey, KeyboardModifiers

from src.nicegui.review_tab import ReviewTab


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_voice_tab(card_type="reading", transcript=""):
    """Minimal fake ReviewTab with the state the voice methods (and handle_key) use."""
    tab = SimpleNamespace(
        current_item={"ID": 1, "card_type": card_type},
        incorrect_message="❌",
        res_display=SimpleNamespace(text=""),
        text_buffer="",
        kana_output="",
        user_romaji=SimpleNamespace(text=""),
        user_hiragana=SimpleNamespace(text=""),
        voice_status=SimpleNamespace(text=""),
        voice_state="idle",
        voice_card=None,
        voice_max_record_seconds=8,
        transcriber=MagicMock(),
        key_voice_input="`",
        key_ignore_answer="Backspace",
        key_add_as_valid_response="=",
        key_quit_after_current_set="e",
        alphabet=" ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!?-",
    )
    tab.transcriber.transcribe.return_value = transcript
    tab.toggle_voice = MethodType(ReviewTab.toggle_voice, tab)
    tab.voice_card_is_current = MethodType(ReviewTab.voice_card_is_current, tab)
    return tab


def _make_key_event(key_name):
    return KeyEventArguments(
        sender=MagicMock(),
        client=MagicMock(),
        action=KeyboardAction(keydown=True, keyup=False, repeat=False),
        key=KeyboardKey(name=key_name, code=f"Key{key_name.upper()}", location=0),
        modifiers=KeyboardModifiers(alt=False, ctrl=False, meta=False, shift=False),
    )


async def _run_inline(func, *args):
    """Replacement for nicegui's run.io_bound that calls the function directly."""
    return func(*args)


def _run_coroutine(coroutine):
    """Run a coroutine on a private loop; asyncio.run() would clear the thread's current
    event loop, which breaks the discord bot fixtures in later test modules."""
    loop = asyncio.new_event_loop()

    try:
        return loop.run_until_complete(coroutine)

    finally:
        loop.close()


def _record_and_transcribe(tab, before_audio=None):
    """Start recording on the current card, then deliver the recorded audio like the browser would."""
    event = SimpleNamespace(args={"audio": base64.b64encode(b"recorded audio").decode()})

    with patch("src.nicegui.review_tab.ui") as mock_ui:
        with patch("src.nicegui.review_tab.run", SimpleNamespace(io_bound=_run_inline)):
            tab.toggle_voice()

            if before_audio:
                before_audio()

            result = _run_coroutine(ReviewTab.handle_voice_audio(tab, event))

    return result, mock_ui


# ---------------------------------------------------------------------------
# TestToggleVoice  (issue #43)
# ---------------------------------------------------------------------------

class TestToggleVoice:

    def test_first_press_starts_recording_for_current_card(self):
        tab = _make_voice_tab()

        with patch("src.nicegui.review_tab.ui") as mock_ui:
            result = tab.toggle_voice()

        assert result == "start recording"
        assert tab.voice_state == "recording"
        assert tab.voice_card == (1, "reading")
        mock_ui.run_javascript.assert_called_once_with("srslyVoice.start(8)")

    def test_second_press_stops_recording(self):
        tab = _make_voice_tab()
        tab.voice_state = "recording"

        with patch("src.nicegui.review_tab.ui") as mock_ui:
            result = tab.toggle_voice()

        assert result == "stop recording"
        mock_ui.run_javascript.assert_called_once_with("srslyVoice.stop()")

    def test_ignored_while_transcribing(self):
        tab = _make_voice_tab()
        tab.voice_state = "transcribing"

        with patch("src.nicegui.review_tab.ui") as mock_ui:
            assert tab.toggle_voice() is None

        mock_ui.run_javascript.assert_not_called()

    def test_ignored_while_acknowledging_wrong_answer(self):
        tab = _make_voice_tab()
        tab.res_display.text = "❌"

        with patch("src.nicegui.review_tab.ui") as mock_ui:
            assert tab.toggle_voice() is None

        assert tab.voice_state == "idle"
        mock_ui.run_javascript.assert_not_called()

    def test_voice_key_starts_recording(self):
        tab = _make_voice_tab()

        with patch("src.nicegui.review_tab.ui"):
            result = ReviewTab.handle_key(tab, _make_key_event("`"))

        assert result == "start recording"
        assert tab.voice_state == "recording"

    def test_voice_key_does_nothing_without_transcriber(self):
        tab = _make_voice_tab()
        tab.transcriber = None

        with patch("src.nicegui.review_tab.ui"):
            result = ReviewTab.handle_key(tab, _make_key_event("`"))

        assert result is None
        assert tab.voice_state == "idle"


# ---------------------------------------------------------------------------
# TestHandleVoiceAudio  (issue #43)
# ---------------------------------------------------------------------------

class TestHandleVoiceAudio:

    def test_reading_transcript_filled_in_as_hiragana(self):
        tab = _make_voice_tab("reading", transcript="帰ります。")

        result, _ = _record_and_transcribe(tab)

        assert result == "transcribed"
        assert tab.text_buffer == "かえります"
        assert tab.user_hiragana.text == "かえります"
        assert tab.voice_state == "idle"
        assert tab.voice_status.text == ""

    def test_meaning_transcript_cleaned_up(self):
        tab = _make_voice_tab("meaning", transcript="To compare.")

        _record_and_transcribe(tab)

        assert tab.text_buffer == "to compare"
        assert tab.user_hiragana.text == "to compare"

    def test_audio_transcribed_in_card_language(self):
        reading_tab = _make_voice_tab("reading", transcript="あか")
        meaning_tab = _make_voice_tab("meaning", transcript="red")

        _record_and_transcribe(reading_tab)
        _record_and_transcribe(meaning_tab)

        reading_tab.transcriber.transcribe.assert_called_once_with(b"recorded audio", "ja")
        meaning_tab.transcriber.transcribe.assert_called_once_with(b"recorded audio", "en")

    def test_answer_is_not_submitted(self):
        """The user checks and fixes the transcription before pressing Enter."""
        tab = _make_voice_tab("reading", transcript="かえります")

        _record_and_transcribe(tab)

        assert tab.res_display.text == ""

    def test_typing_edits_the_transcription(self):
        tab = _make_voice_tab("reading", transcript="帰りま")
        _record_and_transcribe(tab)

        with patch("src.nicegui.review_tab.ui"):
            ReviewTab.handle_key(tab, _make_key_event("s"))
            ReviewTab.handle_key(tab, _make_key_event("u"))

        assert tab.user_hiragana.text == "かえります"

        with patch("src.nicegui.review_tab.ui"):
            ReviewTab.handle_key(tab, _make_key_event("Backspace"))

        assert tab.user_hiragana.text == "かえりま"

    def test_recording_for_previous_card_is_discarded(self):
        tab = _make_voice_tab("reading", transcript="かえります")

        def move_to_meaning_card():
            tab.current_item = {"ID": 1, "card_type": "meaning"}

        result, _ = _record_and_transcribe(tab, before_audio=move_to_meaning_card)

        assert result == "stale recording"
        tab.transcriber.transcribe.assert_not_called()
        assert tab.text_buffer == ""
        assert tab.voice_state == "idle"

    def test_card_change_during_transcription_is_discarded(self):
        tab = _make_voice_tab("reading")

        def transcribe_while_user_moves_on(audio, language):
            tab.current_item = {"ID": 2, "card_type": "reading"}
            return "かえります"

        tab.transcriber.transcribe.side_effect = transcribe_while_user_moves_on

        result, _ = _record_and_transcribe(tab)

        assert result == "stale recording"
        assert tab.text_buffer == ""

    def test_no_speech_notifies_user(self):
        tab = _make_voice_tab("reading", transcript="")

        result, mock_ui = _record_and_transcribe(tab)

        assert result == "no speech"
        assert tab.text_buffer == ""
        mock_ui.notify.assert_called_once()

    def test_transcription_error_notifies_and_resets(self):
        tab = _make_voice_tab("reading")
        tab.transcriber.transcribe.side_effect = RuntimeError("model missing")

        result, mock_ui = _record_and_transcribe(tab)

        assert result == "transcription failed"
        assert tab.voice_state == "idle"
        assert "model missing" in mock_ui.notify.call_args.args[0]


# ---------------------------------------------------------------------------
# TestHandleVoiceError  (issue #43)
# ---------------------------------------------------------------------------

class TestHandleVoiceError:

    def test_resets_recording_and_shows_message(self):
        tab = _make_voice_tab()
        tab.voice_state = "recording"
        tab.voice_card = (1, "reading")
        event = SimpleNamespace(args={"message": "Microphone unavailable: NotAllowedError"})

        with patch("src.nicegui.review_tab.ui") as mock_ui:
            ReviewTab.handle_voice_error(tab, event)

        assert tab.voice_state == "idle"
        assert tab.voice_card is None
        mock_ui.notify.assert_called_once_with("Microphone unavailable: NotAllowedError")
