import sqlite3
import pytest
from datetime import datetime, timezone

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
