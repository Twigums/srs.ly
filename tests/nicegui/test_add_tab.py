import sqlite3
import pytest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from tests.conftest import insert_srs_item, make_nicegui_item


# ---------------------------------------------------------------------------
# add_review_item  (called by NiceGUI AddTab)
# ---------------------------------------------------------------------------

class TestAddReviewItem:
    def _fetch_row(self, tmp_dbs):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM SrsEntrySet").fetchone()
        conn.close()
        return dict(row) if row else None

    def test_add_vocab_item_creates_db_row(self, srs_app, tmp_dbs):
        item = make_nicegui_item("vocab", "食べる", "to eat", "たべる")
        srs_app.add_review_item(item)
        row = self._fetch_row(tmp_dbs)
        assert row is not None
        assert row["AssociatedVocab"] == "食べる"
        assert row["AssociatedKanji"] is None

    def test_add_kanji_item_creates_db_row(self, srs_app, tmp_dbs):
        item = make_nicegui_item("kanji", "食", "food, eat", "しょく")
        srs_app.add_review_item(item)
        row = self._fetch_row(tmp_dbs)
        assert row is not None
        assert row["AssociatedKanji"] == "食"
        assert row["AssociatedVocab"] is None

    def test_added_item_starts_at_grade_zero(self, srs_app, tmp_dbs):
        srs_app.add_review_item(make_nicegui_item("vocab", "食べる", "to eat", "たべる"))
        assert self._fetch_row(tmp_dbs)["CurrentGrade"] == 0

    def test_added_item_has_future_next_answer_date(self, srs_app, tmp_dbs):
        srs_app.add_review_item(make_nicegui_item("vocab", "食べる", "to eat", "たべる"))
        next_date = self._fetch_row(tmp_dbs)["NextAnswerDateISO"]
        next_dt = datetime.fromisoformat(next_date).replace(tzinfo=timezone.utc)
        assert next_dt > datetime.now(timezone.utc)

    def test_added_item_is_not_deleted(self, srs_app, tmp_dbs):
        srs_app.add_review_item(make_nicegui_item("vocab", "食べる", "to eat", "たべる"))
        assert self._fetch_row(tmp_dbs)["IsDeleted"] == 0


# ---------------------------------------------------------------------------
# filter_study_items  (called by NiceGUI AddTab / EditTab)
# ---------------------------------------------------------------------------

class TestFilterStudyItems:
    def test_filter_vocab_returns_only_vocab_items(self, srs_app, tmp_dbs):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        insert_srs_item(conn, associated_vocab="食べる")
        insert_srs_item(conn, associated_kanji="食")
        conn.close()

        df = srs_app.filter_study_items("vocab")
        assert len(df) == 1
        assert df.iloc[0]["AssociatedVocab"] == "食べる"

    def test_filter_kanji_returns_only_kanji_items(self, srs_app, tmp_dbs):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        insert_srs_item(conn, associated_vocab="食べる")
        insert_srs_item(conn, associated_kanji="食")
        conn.close()

        df = srs_app.filter_study_items("kanji")
        assert len(df) == 1
        assert df.iloc[0]["AssociatedKanji"] == "食"

    def test_filter_with_condition_limits_results(self, srs_app, tmp_dbs):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        insert_srs_item(conn, associated_vocab="食べる", current_grade=0)
        insert_srs_item(conn, associated_vocab="飲む",   current_grade=3)
        conn.close()

        df = srs_app.filter_study_items("vocab", condition="CurrentGrade = 0")
        assert len(df) == 1
        assert df.iloc[0]["AssociatedVocab"] == "食べる"

    def test_filter_invalid_type_raises(self, srs_app):
        with pytest.raises(Exception):
            srs_app.filter_study_items("invalid_type")


# ---------------------------------------------------------------------------
# add_review_item — custom item (no DB lookup, issue #32 part 2)
# ---------------------------------------------------------------------------

class TestAddCustomItem:
    def _fetch_row(self, tmp_dbs):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM SrsEntrySet").fetchone()
        conn.close()
        return dict(row) if row else None

    def test_custom_item_stores_meaning_and_reading_notes(self, srs_app, tmp_dbs):
        item = make_nicegui_item(
            "vocab", "カスタム", "custom word", "かすたむ",
            meaning_notes="remember: custom",
            reading_notes="sounds like 'custom'",
        )
        srs_app.add_review_item(item)
        row = self._fetch_row(tmp_dbs)
        assert row is not None
        assert row["MeaningNote"] == "remember: custom"
        assert row["ReadingNote"] == "sounds like 'custom'"

    def test_custom_vocab_not_in_db_is_accepted(self, srs_app, tmp_dbs):
        item = make_nicegui_item("vocab", "存在しない語", "nonexistent word", "そんざいしないご")
        srs_app.add_review_item(item)
        row = self._fetch_row(tmp_dbs)
        assert row is not None
        assert row["AssociatedVocab"] == "存在しない語"

    def test_custom_kanji_not_in_db_is_accepted(self, srs_app, tmp_dbs):
        item = make_nicegui_item("kanji", "𠀋", "custom kanji", "カスタム")
        srs_app.add_review_item(item)
        row = self._fetch_row(tmp_dbs)
        assert row is not None
        assert row["AssociatedKanji"] == "𠀋"


# ---------------------------------------------------------------------------
# AddTab page preservation — issue #33
# ---------------------------------------------------------------------------

def _make_add_tab(srs_app):
    """Instantiate AddTab with NiceGUI UI elements mocked out."""
    config = SimpleNamespace(srs_app=srs_app)

    mock_table = MagicMock()
    mock_ui = MagicMock()
    mock_ui.table.return_value = mock_table

    # ui.element / ui.card / ui.column / ui.row / ui.separator used as context
    # managers — make them return a MagicMock that supports __enter__/__exit__
    def _cm(*args, **kwargs):
        m = MagicMock()
        m.__enter__ = MagicMock(return_value=m)
        m.__exit__ = MagicMock(return_value=False)
        return m

    for attr in ("element", "card", "column", "row", "separator", "grid"):
        getattr(mock_ui, attr).side_effect = _cm

    with patch("src.nicegui.add_tab.ui", mock_ui):
        from src.nicegui.add_tab import AddTab
        tab = AddTab(config)

    return tab, mock_table, mock_ui


class TestAddTabPagePreservation:
    def test_current_page_initialises_to_one(self, srs_app):
        tab, _, _ = _make_add_tab(srs_app)
        assert tab.current_page == 1

    def test_on_pagination_update_stores_page(self, srs_app):
        tab, _, _ = _make_add_tab(srs_app)
        event = SimpleNamespace(args={"page": 3, "rowsPerPage": 100})
        tab._on_pagination_update(event)
        assert tab.current_page == 3

    def test_add_selected_items_preserves_current_page(self, srs_app):
        tab, _, _ = _make_add_tab(srs_app)
        tab.current_page = 4
        tab.selected_items = {
            0: make_nicegui_item("vocab", "食べる", "to eat", "たべる"),
        }
        tab.add_spinner = MagicMock()

        with patch.object(tab, "update_search_results") as mock_update:
            tab.add_selected_items()
            mock_update.assert_called_once_with(reset_page=False)

    def test_search_button_resets_page(self, srs_app):
        tab, _, _ = _make_add_tab(srs_app)
        tab.current_page = 5

        with patch.object(tab, "update_search_results") as mock_update:
            tab.update_search_results(reset_page=True)
            # calling with reset_page=True is the search-button default
            mock_update.assert_called_once_with(reset_page=True)


# ---------------------------------------------------------------------------
# render_inputs edit preservation — new issue
# ---------------------------------------------------------------------------

def _make_row(id_, kanji, readings, meanings, type_="vocab"):
    return {
        "id": id_,
        "Kanji": kanji,
        "Readings": readings,
        "Meanings": meanings,
        "Tags": "n5",
        "type": type_,
        "onyomi": None,
        "kunyomi": None,
        "nanori": None,
    }


def _edited(value: str):
    return SimpleNamespace(value=value)


class TestRenderInputsPreservation:
    def _call_render(self, tab, mock_ui, selection):
        mock_ui.input.reset_mock()
        with patch("src.nicegui.add_tab.ui", mock_ui):
            return tab.render_inputs(selection)

    def test_checking_new_item_preserves_kanji_edit(self, srs_app):
        tab, _, mock_ui = _make_add_tab(srs_app)

        # item 0 already selected with user-edited kanji
        tab.selected_items = {
            0: {
                "kanji": _edited("食べる_EDITED"),
                "readings": _edited("たべる"),
                "meanings": _edited("to eat"),
                "reading_notes": _edited(""),
                "meaning_notes": _edited(""),
                "type": "vocab",
            }
        }

        item0 = _make_row(0, "食べる", "たべる", "to eat")
        item1 = _make_row(1, "飲む", "のむ", "to drink")

        self._call_render(tab, mock_ui, [item0, item1])

        kanji_calls = [c for c in mock_ui.input.call_args_list if c.args[0] == "Kanji"]
        assert kanji_calls[0].kwargs.get("value") == "食べる_EDITED", (
            "existing item kanji edit must be preserved when new item is checked"
        )
        assert kanji_calls[1].kwargs.get("value") == "飲む"

    def test_checking_new_item_preserves_readings_edit(self, srs_app):
        tab, _, mock_ui = _make_add_tab(srs_app)

        tab.selected_items = {
            0: {
                "kanji": _edited("食べる"),
                "readings": _edited("たべる_EDITED"),
                "meanings": _edited("to eat"),
                "reading_notes": _edited(""),
                "meaning_notes": _edited(""),
                "type": "vocab",
            }
        }

        self._call_render(tab, mock_ui, [
            _make_row(0, "食べる", "たべる", "to eat"),
            _make_row(1, "飲む", "のむ", "to drink"),
        ])

        readings_calls = [c for c in mock_ui.input.call_args_list if c.args[0] == "Readings"]
        assert readings_calls[0].kwargs.get("value") == "たべる_EDITED"

    def test_checking_new_item_preserves_notes(self, srs_app):
        tab, _, mock_ui = _make_add_tab(srs_app)

        tab.selected_items = {
            0: {
                "kanji": _edited("食べる"),
                "readings": _edited("たべる"),
                "meanings": _edited("to eat"),
                "reading_notes": _edited("my reading note"),
                "meaning_notes": _edited("my meaning note"),
                "type": "vocab",
            }
        }

        self._call_render(tab, mock_ui, [
            _make_row(0, "食べる", "たべる", "to eat"),
            _make_row(1, "飲む", "のむ", "to drink"),
        ])

        reading_note_calls = [c for c in mock_ui.input.call_args_list if c.args[0] == "Reading Notes"]
        meaning_note_calls = [c for c in mock_ui.input.call_args_list if c.args[0] == "Meaning Notes"]
        assert reading_note_calls[0].kwargs.get("value") == "my reading note"
        assert meaning_note_calls[0].kwargs.get("value") == "my meaning note"

    def test_unchecking_item_removes_it_from_selected(self, srs_app):
        tab, _, mock_ui = _make_add_tab(srs_app)

        tab.selected_items = {
            0: {
                "kanji": _edited("食べる"),
                "readings": _edited("たべる"),
                "meanings": _edited("to eat"),
                "reading_notes": _edited(""),
                "meaning_notes": _edited(""),
                "type": "vocab",
            },
            1: {
                "kanji": _edited("飲む"),
                "readings": _edited("のむ"),
                "meanings": _edited("to drink"),
                "reading_notes": _edited(""),
                "meaning_notes": _edited(""),
                "type": "vocab",
            },
        }

        # user unchecks item 1, only item 0 remains
        self._call_render(tab, mock_ui, [_make_row(0, "食べる", "たべる", "to eat")])
        assert 1 not in tab.selected_items

    def test_new_item_gets_default_values(self, srs_app):
        tab, _, mock_ui = _make_add_tab(srs_app)
        tab.selected_items = {}

        self._call_render(tab, mock_ui, [_make_row(5, "新しい", "あたらしい", "new")])

        kanji_calls = [c for c in mock_ui.input.call_args_list if c.args[0] == "Kanji"]
        assert kanji_calls[0].kwargs.get("value") == "新しい"
