"""
Tests for review state persistence via app.storage.user (NiceGUI per-user storage).

These tests verify that:
  1. Review state is saved to app.storage.user when a card is shown / state changes.
  2. Review state is restored from app.storage.user on ReviewTab initialisation
     (i.e. after a browser/connection refresh).
  3. Progress through a session (current_index, current_completed, item_dict,
     due_review_ids) persists correctly across a simulated refresh.

The tests work by:
  - Mocking `nicegui.app.storage.user` as a plain dict.
  - Using a MagicMock SrsApp whose review-state attributes can be freely set.
  - Directly exercising the storage helper functions that ReviewTab delegates to.
"""

import pytest
from unittest.mock import MagicMock

from src.review_storage import (
    STORAGE_KEY,
    save_review_state,
    load_review_state,
    clear_review_state,
    has_review_state,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_storage():
    """A plain dict standing in for app.storage.user."""
    return {}


@pytest.fixture
def mock_srs_app():
    """MagicMock SrsApp with the review-state attributes ReviewTab uses."""
    m = MagicMock()
    m.current_index = 0
    m.current_completed = 0
    m.len_review_ids = 0
    m.stop_updating_review = False
    m.current_reviews = []
    m.due_review_ids = []
    return m


@pytest.fixture
def sample_reviews():
    """Two minimal review card dicts (one reading, one meaning)."""
    return [
        {
            "ID": 1,
            "AssociatedVocab": "食べる",
            "AssociatedKanji": None,
            "Readings": "たべる",
            "Meanings": "to eat",
            "review_type": "vocab",
            "card_type": "reading",
            "prompt": "食べる",
            "expected_answer": "たべる",
        },
        {
            "ID": 1,
            "AssociatedVocab": "食べる",
            "AssociatedKanji": None,
            "Readings": "たべる",
            "Meanings": "to eat",
            "review_type": "vocab",
            "card_type": "meaning",
            "prompt": "食べる",
            "expected_answer": "to eat",
        },
    ]


# ---------------------------------------------------------------------------
# save_review_state
# ---------------------------------------------------------------------------

class TestSaveReviewState:
    def test_saves_current_reviews(self, mock_storage, mock_srs_app, sample_reviews):
        mock_srs_app.current_reviews = sample_reviews
        save_review_state(mock_storage, mock_srs_app, item_dict={})
        assert mock_storage[STORAGE_KEY]["current_reviews"] == sample_reviews

    def test_saves_current_index(self, mock_storage, mock_srs_app, sample_reviews):
        mock_srs_app.current_reviews = sample_reviews
        mock_srs_app.current_index = 1
        save_review_state(mock_storage, mock_srs_app, item_dict={})
        assert mock_storage[STORAGE_KEY]["current_index"] == 1

    def test_saves_current_completed(self, mock_storage, mock_srs_app, sample_reviews):
        mock_srs_app.current_reviews = sample_reviews
        mock_srs_app.current_completed = 3
        save_review_state(mock_storage, mock_srs_app, item_dict={})
        assert mock_storage[STORAGE_KEY]["current_completed"] == 3

    def test_saves_len_review_ids(self, mock_storage, mock_srs_app, sample_reviews):
        mock_srs_app.current_reviews = sample_reviews
        mock_srs_app.len_review_ids = 10
        save_review_state(mock_storage, mock_srs_app, item_dict={})
        assert mock_storage[STORAGE_KEY]["len_review_ids"] == 10

    def test_saves_due_review_ids(self, mock_storage, mock_srs_app, sample_reviews):
        mock_srs_app.current_reviews = sample_reviews
        mock_srs_app.due_review_ids = [5, 6, 7]
        save_review_state(mock_storage, mock_srs_app, item_dict={})
        assert mock_storage[STORAGE_KEY]["due_review_ids"] == [5, 6, 7]

    def test_saves_stop_updating_review(self, mock_storage, mock_srs_app, sample_reviews):
        mock_srs_app.current_reviews = sample_reviews
        mock_srs_app.stop_updating_review = True
        save_review_state(mock_storage, mock_srs_app, item_dict={})
        assert mock_storage[STORAGE_KEY]["stop_updating_review"] is True

    def test_saves_item_dict(self, mock_storage, mock_srs_app, sample_reviews):
        mock_srs_app.current_reviews = sample_reviews
        item_dict = {1: [1, 0]}
        save_review_state(mock_storage, mock_srs_app, item_dict=item_dict)
        assert mock_storage[STORAGE_KEY]["item_dict"] == {1: [1, 0]}

    def test_does_not_save_when_no_active_session(self, mock_storage, mock_srs_app):
        """When current_reviews is empty, nothing should be written to storage."""
        mock_srs_app.current_reviews = []
        save_review_state(mock_storage, mock_srs_app, item_dict={})
        assert STORAGE_KEY not in mock_storage

    def test_overwrites_existing_state(self, mock_storage, mock_srs_app, sample_reviews):
        mock_srs_app.current_reviews = sample_reviews
        mock_srs_app.current_index = 0
        save_review_state(mock_storage, mock_srs_app, item_dict={})

        mock_srs_app.current_index = 1
        save_review_state(mock_storage, mock_srs_app, item_dict={})

        assert mock_storage[STORAGE_KEY]["current_index"] == 1


# ---------------------------------------------------------------------------
# load_review_state
# ---------------------------------------------------------------------------

class TestLoadReviewState:
    def test_returns_none_when_no_state_in_storage(self, mock_storage, mock_srs_app):
        result = load_review_state(mock_storage, mock_srs_app, {})
        assert result is None

    def test_restores_current_reviews(self, mock_storage, mock_srs_app, sample_reviews):
        mock_storage[STORAGE_KEY] = {
            "current_reviews": sample_reviews,
            "current_index": 0,
            "current_completed": 0,
            "len_review_ids": 2,
            "due_review_ids": [],
            "stop_updating_review": False,
            "item_dict": {},
        }
        item_dict = {}
        load_review_state(mock_storage, mock_srs_app, item_dict)
        assert mock_srs_app.current_reviews == sample_reviews

    def test_restores_current_index(self, mock_storage, mock_srs_app, sample_reviews):
        mock_storage[STORAGE_KEY] = {
            "current_reviews": sample_reviews,
            "current_index": 1,
            "current_completed": 1,
            "len_review_ids": 2,
            "due_review_ids": [],
            "stop_updating_review": False,
            "item_dict": {},
        }
        item_dict = {}
        load_review_state(mock_storage, mock_srs_app, item_dict)
        assert mock_srs_app.current_index == 1

    def test_restores_current_completed(self, mock_storage, mock_srs_app, sample_reviews):
        mock_storage[STORAGE_KEY] = {
            "current_reviews": sample_reviews,
            "current_index": 0,
            "current_completed": 4,
            "len_review_ids": 2,
            "due_review_ids": [],
            "stop_updating_review": False,
            "item_dict": {},
        }
        item_dict = {}
        load_review_state(mock_storage, mock_srs_app, item_dict)
        assert mock_srs_app.current_completed == 4

    def test_restores_len_review_ids(self, mock_storage, mock_srs_app, sample_reviews):
        mock_storage[STORAGE_KEY] = {
            "current_reviews": sample_reviews,
            "current_index": 0,
            "current_completed": 0,
            "len_review_ids": 7,
            "due_review_ids": [],
            "stop_updating_review": False,
            "item_dict": {},
        }
        item_dict = {}
        load_review_state(mock_storage, mock_srs_app, item_dict)
        assert mock_srs_app.len_review_ids == 7

    def test_restores_due_review_ids(self, mock_storage, mock_srs_app, sample_reviews):
        mock_storage[STORAGE_KEY] = {
            "current_reviews": sample_reviews,
            "current_index": 0,
            "current_completed": 0,
            "len_review_ids": 3,
            "due_review_ids": [10, 11],
            "stop_updating_review": False,
            "item_dict": {},
        }
        item_dict = {}
        load_review_state(mock_storage, mock_srs_app, item_dict)
        assert mock_srs_app.due_review_ids == [10, 11]

    def test_restores_stop_updating_review(self, mock_storage, mock_srs_app, sample_reviews):
        mock_storage[STORAGE_KEY] = {
            "current_reviews": sample_reviews,
            "current_index": 0,
            "current_completed": 0,
            "len_review_ids": 2,
            "due_review_ids": [],
            "stop_updating_review": True,
            "item_dict": {},
        }
        item_dict = {}
        load_review_state(mock_storage, mock_srs_app, item_dict)
        assert mock_srs_app.stop_updating_review is True

    def test_restores_item_dict(self, mock_storage, mock_srs_app, sample_reviews):
        mock_storage[STORAGE_KEY] = {
            "current_reviews": sample_reviews,
            "current_index": 0,
            "current_completed": 0,
            "len_review_ids": 2,
            "due_review_ids": [],
            "stop_updating_review": False,
            "item_dict": {1: [1, 0]},
        }
        item_dict = {}
        load_review_state(mock_storage, mock_srs_app, item_dict)
        assert item_dict == {1: [1, 0]}

    def test_returns_state_dict_on_success(self, mock_storage, mock_srs_app, sample_reviews):
        state = {
            "current_reviews": sample_reviews,
            "current_index": 0,
            "current_completed": 0,
            "len_review_ids": 2,
            "due_review_ids": [],
            "stop_updating_review": False,
            "item_dict": {},
        }
        mock_storage[STORAGE_KEY] = state
        item_dict = {}
        result = load_review_state(mock_storage, mock_srs_app, item_dict)
        assert result == state

    def test_item_dict_keys_converted_to_int(self, mock_storage, mock_srs_app, sample_reviews):
        """
        JSON serialisation (used by NiceGUI storage) converts int dict keys to
        strings; load_review_state must convert them back to ints.
        """
        mock_storage[STORAGE_KEY] = {
            "current_reviews": sample_reviews,
            "current_index": 0,
            "current_completed": 0,
            "len_review_ids": 2,
            "due_review_ids": [],
            "stop_updating_review": False,
            "item_dict": {"1": [1, 0]},  # string key (as from JSON)
        }
        item_dict = {}
        load_review_state(mock_storage, mock_srs_app, item_dict)
        assert 1 in item_dict
        assert item_dict[1] == [1, 0]


# ---------------------------------------------------------------------------
# clear_review_state
# ---------------------------------------------------------------------------

class TestClearReviewState:
    def test_removes_key_from_storage(self, mock_storage, sample_reviews):
        mock_storage[STORAGE_KEY] = {"current_reviews": sample_reviews}
        clear_review_state(mock_storage)
        assert STORAGE_KEY not in mock_storage

    def test_no_error_when_storage_already_empty(self, mock_storage):
        clear_review_state(mock_storage)  # must not raise


# ---------------------------------------------------------------------------
# has_review_state
# ---------------------------------------------------------------------------

class TestHasReviewState:
    def test_returns_false_when_no_state(self, mock_storage):
        assert has_review_state(mock_storage) is False

    def test_returns_false_when_state_has_empty_reviews(self, mock_storage):
        mock_storage[STORAGE_KEY] = {"current_reviews": []}
        assert has_review_state(mock_storage) is False

    def test_returns_true_when_state_has_reviews(self, mock_storage, sample_reviews):
        mock_storage[STORAGE_KEY] = {"current_reviews": sample_reviews}
        assert has_review_state(mock_storage) is True


# ---------------------------------------------------------------------------
# Round-trip: save then load reproduces identical state
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_save_load_roundtrip(self, mock_storage, mock_srs_app, sample_reviews):
        mock_srs_app.current_reviews = sample_reviews
        mock_srs_app.current_index = 1
        mock_srs_app.current_completed = 2
        mock_srs_app.len_review_ids = 5
        mock_srs_app.due_review_ids = [3, 4]
        mock_srs_app.stop_updating_review = False
        original_item_dict = {1: [1, 0], 2: [0]}

        save_review_state(mock_storage, mock_srs_app, item_dict=original_item_dict)

        # simulate a fresh SrsApp (as after a page refresh)
        fresh_srs_app = MagicMock()
        fresh_srs_app.current_reviews = []
        fresh_srs_app.current_index = 0
        fresh_srs_app.current_completed = 0
        fresh_srs_app.len_review_ids = 0
        fresh_srs_app.due_review_ids = []
        fresh_srs_app.stop_updating_review = False
        restored_item_dict = {}

        load_review_state(mock_storage, fresh_srs_app, restored_item_dict)

        assert fresh_srs_app.current_reviews == sample_reviews
        assert fresh_srs_app.current_index == 1
        assert fresh_srs_app.current_completed == 2
        assert fresh_srs_app.len_review_ids == 5
        assert fresh_srs_app.due_review_ids == [3, 4]
        assert fresh_srs_app.stop_updating_review is False
        assert restored_item_dict == original_item_dict

    def test_clear_then_has_state_is_false(self, mock_storage, mock_srs_app, sample_reviews):
        mock_srs_app.current_reviews = sample_reviews
        save_review_state(mock_storage, mock_srs_app, item_dict={})
        assert has_review_state(mock_storage) is True
        clear_review_state(mock_storage)
        assert has_review_state(mock_storage) is False
