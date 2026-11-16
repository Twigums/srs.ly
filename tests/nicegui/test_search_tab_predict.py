import asyncio
import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.dataclasses import AppConfig
from src.nicegui.search_tab import SearchTab


# ---------------------------------------------------------------------------
# SearchTab.predict with Google credentials
# `vision` was only imported inside __init__, so predict() raised NameError
# ---------------------------------------------------------------------------

PNG = b"fake png bytes"


def _run(coro):
    # a private loop: asyncio.run() would unset the main thread's loop for later tests
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def search_tab(mock_srs_app, monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/not/read/in/tests.json")
    config = AppConfig(keybinds = {}, srs_app = mock_srs_app)

    with patch("src.nicegui.search_tab.ui") as mock_ui, \
         patch("google.cloud.vision.ImageAnnotatorClient") as mock_client_cls:
        mock_ui.run_javascript = AsyncMock(return_value = "data:image/png;base64," + base64.b64encode(PNG).decode())
        yield SearchTab(config), mock_client_cls.return_value


class TestPredict:
    def test_sends_drawing_to_vision_and_shows_text(self, search_tab):
        tab, vision_client = search_tab
        vision_client.text_detection.return_value = MagicMock(text_annotations = [MagicMock(description = " 食べる\n")])

        _run(tab.predict())

        assert vision_client.text_detection.call_args.kwargs["image"].content == PNG
        assert tab.prediction_label.text == "食べる"

    def test_no_detected_text_clears_label(self, search_tab):
        tab, vision_client = search_tab
        vision_client.text_detection.return_value = MagicMock(text_annotations = [])

        _run(tab.predict())

        assert tab.prediction_label.text == ""
