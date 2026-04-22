import sqlite3
from types import SimpleNamespace

import pytest

from tests.conftest import insert_srs_item


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
# filter_study_items reading/meaning search — issue #31
# The edit tab builds LIKE conditions; these tests verify the correct
# substring-match pattern finds items that the old exact-token pattern missed.
# ---------------------------------------------------------------------------

class TestFilterStudyItemsSearch:
    def _seed(self, tmp_dbs, *, readings, meanings="test meaning", type_="vocab"):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        if type_ == "vocab":
            item_id = insert_srs_item(conn, associated_vocab="テスト", readings=readings, meanings=meanings)
        else:
            item_id = insert_srs_item(conn, associated_kanji="食", readings=readings, meanings=meanings)
        conn.close()
        return item_id

    # --- reading search: substring match ---

    def test_reading_search_matches_exact_single_reading(self, srs_app, tmp_dbs):
        self._seed(tmp_dbs, readings="chou")
        df = srs_app.filter_study_items("vocab", condition="Readings LIKE '%chou%'")
        assert len(df) == 1

    def test_reading_search_matches_reading_among_multiple(self, srs_app, tmp_dbs):
        self._seed(tmp_dbs, readings="chou,ちょう")
        df = srs_app.filter_study_items("vocab", condition="Readings LIKE '%chou%'")
        assert len(df) == 1

    def test_reading_search_matches_reading_at_end_of_list(self, srs_app, tmp_dbs):
        self._seed(tmp_dbs, readings="ちょう,chou")
        df = srs_app.filter_study_items("vocab", condition="Readings LIKE '%chou%'")
        assert len(df) == 1

    def test_reading_search_partial_prefix_matches(self, srs_app, tmp_dbs):
        self._seed(tmp_dbs, readings="chou")
        df = srs_app.filter_study_items("vocab", condition="Readings LIKE '%cho%'")
        assert len(df) == 1

    def test_reading_search_no_match_returns_empty(self, srs_app, tmp_dbs):
        self._seed(tmp_dbs, readings="たべる")
        df = srs_app.filter_study_items("vocab", condition="Readings LIKE '%chou%'")
        assert df.empty

    def test_reading_search_excludes_non_matching_items(self, srs_app, tmp_dbs):
        self._seed(tmp_dbs, readings="chou,ちょう")
        self._seed(tmp_dbs, readings="たべる")
        df = srs_app.filter_study_items("vocab", condition="Readings LIKE '%chou%'")
        assert len(df) == 1

    # --- meaning search: substring match ---

    def test_meaning_search_matches_single_meaning(self, srs_app, tmp_dbs):
        self._seed(tmp_dbs, readings="r", meanings="to eat")
        df = srs_app.filter_study_items("vocab", condition="Meanings LIKE '%eat%'")
        assert len(df) == 1

    def test_meaning_search_matches_meaning_among_multiple(self, srs_app, tmp_dbs):
        self._seed(tmp_dbs, readings="r", meanings="to eat,to consume")
        df = srs_app.filter_study_items("vocab", condition="Meanings LIKE '%eat%'")
        assert len(df) == 1

    def test_meaning_search_partial_prefix_matches(self, srs_app, tmp_dbs):
        self._seed(tmp_dbs, readings="r", meanings="eating")
        df = srs_app.filter_study_items("vocab", condition="Meanings LIKE '%eat%'")
        assert len(df) == 1

    def test_meaning_search_no_match_returns_empty(self, srs_app, tmp_dbs):
        self._seed(tmp_dbs, readings="r", meanings="to drink")
        df = srs_app.filter_study_items("vocab", condition="Meanings LIKE '%eat%'")
        assert df.empty
