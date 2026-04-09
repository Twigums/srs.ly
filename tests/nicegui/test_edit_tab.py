import sqlite3
from types import SimpleNamespace

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
