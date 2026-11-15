from unittest.mock import patch

import pytest

from src.dataclasses import AppConfig
from src.nicegui.search_tab import SearchTab


# ---------------------------------------------------------------------------
# SearchTab without Google credentials — issue #26
# The missing-key hint used to be a ui.notify sent while the page was still
# being built (before the browser connects), on every page load. It is now a
# label inside the Search tab, so the rest of the page is the same with or
# without the key.
# ---------------------------------------------------------------------------

@pytest.fixture
def config(mock_srs_app):
    return AppConfig(keybinds = {}, srs_app = mock_srs_app)


class TestSearchTabWithoutCredentials:
    def test_does_not_notify_while_page_is_built(self, config, monkeypatch):
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising = False)

        with patch("src.nicegui.search_tab.ui") as mock_ui:
            SearchTab(config)

        mock_ui.notify.assert_not_called()

    def test_explains_how_to_enable_search_inside_the_tab(self, config, monkeypatch):
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising = False)

        with patch("src.nicegui.search_tab.ui") as mock_ui:
            tab = SearchTab(config)

        mock_ui.label.assert_called_once()
        assert "GOOGLE_APPLICATION_CREDENTIALS" in mock_ui.label.call_args.args[0]
        assert tab.vision_client is None
