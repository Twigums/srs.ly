import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.transcriber import Transcriber


@pytest.fixture
def fake_whisper(monkeypatch):
    """Stand-in for faster_whisper so the tests never load a real model."""
    model = MagicMock()
    model.transcribe.return_value = ([SimpleNamespace(text=" 帰ります"), SimpleNamespace(text="。 ")], None)
    whisper_model = MagicMock(return_value=model)
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=whisper_model))
    return whisper_model, model


class TestTranscriber:
    """Issue #43: speech-to-text for spoken review answers."""

    def test_model_not_loaded_on_init(self, fake_whisper):
        whisper_model, _ = fake_whisper
        Transcriber("small")
        whisper_model.assert_not_called()

    def test_model_loaded_once(self, fake_whisper):
        whisper_model, _ = fake_whisper
        transcriber = Transcriber("small")
        transcriber.load()
        transcriber.transcribe(b"audio", "ja")
        whisper_model.assert_called_once_with("small", device="cpu", compute_type="int8")

    def test_segments_joined_and_stripped(self, fake_whisper):
        assert Transcriber("small").transcribe(b"audio", "ja") == "帰ります。"

    def test_language_forced_and_silence_filtered(self, fake_whisper):
        _, model = fake_whisper
        Transcriber("small").transcribe(b"audio", "en")

        audio_file = model.transcribe.call_args.args[0]
        kwargs = model.transcribe.call_args.kwargs
        assert audio_file.read() == b"audio"
        assert kwargs["language"] == "en"
        assert kwargs["vad_filter"] is True
        assert kwargs["condition_on_previous_text"] is False
