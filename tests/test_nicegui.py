import sqlite3
import pytest
from datetime import datetime, timezone
from types import SimpleNamespace

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
# edit_review_item  (called by NiceGUI EditTab)
# ---------------------------------------------------------------------------

class TestEditReviewItem:
    def _make_edit_item(self, item_id, *, type_="vocab", kanji="食べる",
                        meanings="to eat", readings="たべる",
                        current_grade=0, next_answer="2099-01-01 00:00:00"):
        return {
            "item_id": item_id,
            "type": type_,
            "kanji":         SimpleNamespace(value=kanji),
            "meanings":      SimpleNamespace(value=meanings),
            "readings":      SimpleNamespace(value=readings),
            "current_grade": SimpleNamespace(value=current_grade),
            "meaning_notes": SimpleNamespace(value=""),
            "reading_notes": SimpleNamespace(value=""),
            "next_answer":   SimpleNamespace(value=next_answer),
        }

    def _fetch_row(self, tmp_dbs, item_id):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM SrsEntrySet WHERE ID = ?", (item_id,)
        ).fetchone()
        conn.close()
        return dict(row)

    def test_edit_updates_meanings(self, srs_app, tmp_dbs):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        item_id = insert_srs_item(conn, associated_vocab="食べる", meanings="to eat")
        conn.close()

        srs_app.edit_review_item(self._make_edit_item(item_id, meanings="to consume"))
        assert self._fetch_row(tmp_dbs, item_id)["Meanings"] == "to consume"

    def test_edit_updates_readings(self, srs_app, tmp_dbs):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        item_id = insert_srs_item(conn, associated_vocab="食べる", readings="たべる")
        conn.close()

        srs_app.edit_review_item(self._make_edit_item(item_id, readings="たべ"))
        assert self._fetch_row(tmp_dbs, item_id)["Readings"] == "たべ"

    def test_edit_updates_grade(self, srs_app, tmp_dbs):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        item_id = insert_srs_item(conn, associated_vocab="食べる", current_grade=0)
        conn.close()

        srs_app.edit_review_item(self._make_edit_item(item_id, current_grade=5))
        assert self._fetch_row(tmp_dbs, item_id)["CurrentGrade"] == 5


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
# TestReviewFlow  (end-to-end: models the NiceGUI ReviewTab cycle)
# ---------------------------------------------------------------------------

class TestReviewFlow:
    def _fetch_row(self, tmp_dbs, item_id):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM SrsEntrySet WHERE ID = ?", (item_id,)
        ).fetchone()
        conn.close()
        return dict(row)

    def test_correct_answer_advances_grade(self, srs_app, tmp_dbs):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        item_id = insert_srs_item(conn, associated_vocab="食べる",
                                  current_grade=0,
                                  next_answer_date="2000-01-01 00:00:00")
        conn.close()

        srs_app.start_review_session()
        srs_app.update_review_item(item_id, True)

        row = self._fetch_row(tmp_dbs, item_id)
        assert row["CurrentGrade"] == 1
        assert row["SuccessCount"] == 1

    def test_wrong_answer_keeps_grade_at_floor(self, srs_app, tmp_dbs):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        item_id = insert_srs_item(conn, associated_vocab="食べる",
                                  current_grade=0, failure_count=0,
                                  next_answer_date="2000-01-01 00:00:00")
        conn.close()

        srs_app.start_review_session()
        srs_app.update_review_item(item_id, False)

        row = self._fetch_row(tmp_dbs, item_id)
        assert row["CurrentGrade"] == 0   # floor, does not go negative
        assert row["FailureCount"] == 1

    def test_answered_item_leaves_due_queue(self, srs_app, tmp_dbs):
        """After a correct answer the item's next date is in the future."""
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        item_id = insert_srs_item(conn, associated_vocab="食べる",
                                  next_answer_date="2000-01-01 00:00:00")
        conn.close()

        srs_app.start_review_session()
        srs_app.update_review_item(item_id, True)

        df = srs_app.get_due_reviews()
        assert df.empty

    def test_session_replenishes_from_queue(self, srs_app, tmp_dbs):
        """update_review_session adds the next queued item once one is completed."""
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        for i in range(3):
            insert_srs_item(conn, associated_vocab=f"vocab{i}",
                            next_answer_date="2000-01-01 00:00:00")
        conn.close()

        srs_app.max_reviews_at_once = 2
        srs_app.start_review_session()

        # 2 items loaded → 4 cards; 1 item still in the back queue
        assert len(srs_app.current_reviews) == 4
        assert len(srs_app.due_review_ids) == 1

        srs_app.update_review_session()

        # the queued item was pulled in → 6 cards, queue now empty
        assert len(srs_app.current_reviews) == 6
        assert len(srs_app.due_review_ids) == 0

    def test_stop_flag_prevents_replenishment(self, srs_app, tmp_dbs):
        """Setting stop_updating_review prevents update_review_session from loading more items."""
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        for i in range(3):
            insert_srs_item(conn, associated_vocab=f"vocab{i}",
                            next_answer_date="2000-01-01 00:00:00")
        conn.close()

        srs_app.max_reviews_at_once = 2
        srs_app.start_review_session()
        srs_app.stop_updating_review = True

        count_before = len(srs_app.current_reviews)
        srs_app.update_review_session()
        assert len(srs_app.current_reviews) == count_before
