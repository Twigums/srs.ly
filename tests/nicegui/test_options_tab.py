"""
Tests for the Refresh button in the NiceGUI options tab.

These tests verify that the refresh handler:
  1. Calls clear_review_state on the storage when invoked.
  2. Triggers a page reload (via ui.navigate.reload) after clearing storage.
  3. Behaves identically when storage is already empty (idempotent).

The tests work by:
  - Using a plain dict as a stand-in for app.storage.user.
  - Mocking ui.navigate.reload so no real NiceGUI runtime is needed.
  - Importing and calling the handler function from the options tab module.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.review_storage import STORAGE_KEY


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def storage_with_state():
    """A plain dict standing in for app.storage.user, pre-populated with review state."""
    return {
        STORAGE_KEY: {
            "current_reviews": [{"ID": 1, "card_type": "reading"}],
            "current_index": 0,
            "current_completed": 0,
            "len_review_ids": 1,
            "due_review_ids": [],
            "stop_updating_review": False,
            "item_dict": {},
        }
    }


@pytest.fixture
def empty_storage():
    """A plain dict with no review state saved."""
    return {}


# ---------------------------------------------------------------------------
# Unit tests for the refresh handler function
# ---------------------------------------------------------------------------

class TestRefreshHandler:
    """Tests for the standalone refresh handler used by the options tab button."""

    def test_clear_review_state_called_with_storage(self, storage_with_state):
        """clear_review_state must be called with the provided storage dict."""
        from src.nicegui.options_tab import handle_refresh

        mock_reload = MagicMock()
        with patch("src.nicegui.options_tab.ui") as mock_ui:
            mock_ui.navigate.reload = mock_reload
            handle_refresh(storage_with_state)

        assert STORAGE_KEY not in storage_with_state

    def test_reload_triggered_after_clear(self, storage_with_state):
        """ui.navigate.reload must be called after clearing storage."""
        from src.nicegui.options_tab import handle_refresh

        mock_reload = MagicMock()
        with patch("src.nicegui.options_tab.ui") as mock_ui:
            mock_ui.navigate.reload = mock_reload
            handle_refresh(storage_with_state)

        mock_reload.assert_called_once()

    def test_reload_called_even_when_storage_empty(self, empty_storage):
        """Refresh is idempotent: reload fires even when no state exists in storage."""
        from src.nicegui.options_tab import handle_refresh

        mock_reload = MagicMock()
        with patch("src.nicegui.options_tab.ui") as mock_ui:
            mock_ui.navigate.reload = mock_reload
            handle_refresh(empty_storage)

        mock_reload.assert_called_once()

    def test_storage_key_absent_after_refresh_with_state(self, storage_with_state):
        """After refresh the STORAGE_KEY must not exist in storage."""
        from src.nicegui.options_tab import handle_refresh

        with patch("src.nicegui.options_tab.ui"):
            handle_refresh(storage_with_state)

        assert STORAGE_KEY not in storage_with_state

    def test_storage_unchanged_when_already_empty(self, empty_storage):
        """Calling refresh on empty storage must not raise and leave storage empty."""
        from src.nicegui.options_tab import handle_refresh

        with patch("src.nicegui.options_tab.ui"):
            handle_refresh(empty_storage)  # must not raise

        assert STORAGE_KEY not in empty_storage

    def test_clear_happens_before_reload(self, storage_with_state):
        """Storage must be cleared before the reload is triggered (ordering check)."""
        from src.nicegui.options_tab import handle_refresh

        call_order = []

        def track_clear(storage):
            call_order.append("clear")

        def track_reload():
            call_order.append("reload")

        with patch("src.nicegui.options_tab.clear_review_state", side_effect=track_clear), \
             patch("src.nicegui.options_tab.ui") as mock_ui:
            mock_ui.navigate.reload = track_reload
            handle_refresh(storage_with_state)

        assert call_order == ["clear", "reload"], (
            f"Expected ['clear', 'reload'], got {call_order}"
        )
