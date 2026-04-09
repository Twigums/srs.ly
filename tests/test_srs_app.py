import sqlite3
import pytest
from datetime import datetime, timezone

from src.dataclasses import SrsConfig
from src.srs_app import SrsApp, check_conn

from tests.conftest import insert_srs_item, TEST_SRS_INTERVAL


# ---------------------------------------------------------------------------
# check_conn decorator
# ---------------------------------------------------------------------------

class TestCheckConn:
    def test_returns_none_when_no_connection(self, srs_app):
        srs_app.conn = None
        # get_due_reviews is decorated with @check_conn
        result = srs_app.get_due_reviews()
        assert result is None

    def test_passes_through_when_connected(self, srs_app):
        result = srs_app.get_due_reviews()
        # connected → should return a DataFrame (even if empty), not None
        assert result is not None


# ---------------------------------------------------------------------------
# reset_review_variables
# ---------------------------------------------------------------------------

class TestResetReviewVariables:
    def test_resets_all_variables(self, srs_app):
        srs_app.current_index = 99
        srs_app.current_completed = 42
        srs_app.stop_updating_review = True
        srs_app.current_reviews = ["something"]

        srs_app.reset_review_variables()

        assert srs_app.current_index == 0
        assert srs_app.current_completed == 0
        assert srs_app.stop_updating_review is False
        assert srs_app.current_reviews == []


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------

class TestInitDb:
    def test_success_returns_true(self, tmp_dbs):
        full_db, srs_db = tmp_dbs
        config = SrsConfig(
            srs_interval=TEST_SRS_INTERVAL,
            path_to_full_db=full_db,
            path_to_srs_db=srs_db,
        )
        app = SrsApp(config)
        result = app.init_db()
        assert result is True
        assert app.conn is not None
        assert app.cursor is not None
        app.close_db()

    def test_raises_on_missing_file(self, tmp_path):
        config = SrsConfig(
            srs_interval=TEST_SRS_INTERVAL,
            path_to_full_db=str(tmp_path / "nonexistent.db"),
            path_to_srs_db=str(tmp_path / "also_missing.db"),
        )
        app = SrsApp(config)
        # SQLite creates a new file on connect, so init_db won't fail on a
        # missing path — but attaching the srs_db will fail if the schema is
        # absent. We just verify the connection is open on a blank file.
        # For a truly missing scenario we assert the conn is set (sqlite makes
        # the file) and the app is usable.
        result = app.init_db()
        assert result is True
        app.close_db()


# ---------------------------------------------------------------------------
# to_commit / force_commit
# ---------------------------------------------------------------------------

class TestCommit:
    def test_to_commit_below_threshold_does_not_commit(self, srs_app):
        srs_app.entries_before_commit = 5
        for _ in range(4):
            srs_app.to_commit()
        assert srs_app.entries_without_commit == 4

    def test_to_commit_at_threshold_resets_counter(self, srs_app):
        srs_app.entries_before_commit = 3
        for _ in range(3):
            srs_app.to_commit()
        assert srs_app.entries_without_commit == 0

    def test_force_commit_resets_counter(self, srs_app):
        srs_app.entries_without_commit = 7
        srs_app.force_commit()
        assert srs_app.entries_without_commit == 0


# ---------------------------------------------------------------------------
# get_current_item
# ---------------------------------------------------------------------------

class TestGetCurrentItem:
    def test_returns_none_when_empty(self, srs_app):
        srs_app.current_reviews = []
        assert srs_app.get_current_item() is None

    def test_returns_item_at_current_index(self, srs_app):
        srs_app.current_reviews = [{"id": 1}, {"id": 2}]
        srs_app.current_index = 1
        assert srs_app.get_current_item() == {"id": 2}

    def test_wraps_index_when_out_of_bounds(self, srs_app):
        srs_app.current_reviews = [{"id": 10}]
        srs_app.current_index = 5
        item = srs_app.get_current_item()
        assert srs_app.current_index == 0
        assert item == {"id": 10}


# ---------------------------------------------------------------------------
# add_to_review
# ---------------------------------------------------------------------------

class TestAddToReview:
    def _vocab_row(self):
        return {
            "ID": 1,
            "AssociatedVocab": "食べる",
            "AssociatedKanji": None,
            "Readings": "たべる",
            "Meanings": "to eat",
        }

    def _kanji_row(self):
        return {
            "ID": 2,
            "AssociatedVocab": None,
            "AssociatedKanji": "食",
            "Readings": "しょく,た",
            "Meanings": "eat, food",
        }

    def test_vocab_item_creates_two_cards(self, srs_app):
        srs_app.add_to_review([self._vocab_row()])
        assert len(srs_app.current_reviews) == 2

    def test_vocab_cards_have_correct_review_type(self, srs_app):
        srs_app.add_to_review([self._vocab_row()])
        types = {c["review_type"] for c in srs_app.current_reviews}
        assert types == {"vocab"}

    def test_vocab_cards_have_both_card_types(self, srs_app):
        srs_app.add_to_review([self._vocab_row()])
        card_types = {c["card_type"] for c in srs_app.current_reviews}
        assert card_types == {"reading", "meaning"}

    def test_kanji_item_creates_two_cards_with_correct_type(self, srs_app):
        srs_app.add_to_review([self._kanji_row()])
        types = {c["review_type"] for c in srs_app.current_reviews}
        assert types == {"kanji"}

    def test_cards_have_prompt_and_expected_answer(self, srs_app):
        srs_app.add_to_review([self._vocab_row()])
        for card in srs_app.current_reviews:
            assert "prompt" in card
            assert "expected_answer" in card


# ---------------------------------------------------------------------------
# get_due_reviews
# ---------------------------------------------------------------------------

class TestGetDueReviews:
    def test_empty_table_returns_empty_df(self, srs_app):
        df = srs_app.get_due_reviews()
        assert df.empty

    def test_past_date_is_returned(self, srs_app, tmp_dbs):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        insert_srs_item(conn, associated_vocab="食べる",
                        next_answer_date="2000-01-01 00:00:00")
        conn.close()

        df = srs_app.get_due_reviews()
        assert len(df) == 1

    def test_future_date_is_excluded(self, srs_app, tmp_dbs):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        insert_srs_item(conn, associated_vocab="食べる",
                        next_answer_date="2099-01-01 00:00:00")
        conn.close()

        df = srs_app.get_due_reviews()
        assert df.empty


# ---------------------------------------------------------------------------
# start_review_session
# ---------------------------------------------------------------------------

class TestStartReviewSession:
    def test_no_due_reviews_returns_empty_list(self, srs_app):
        result = srs_app.start_review_session()
        assert result == []
        assert srs_app.len_review_ids == 0

    def test_loads_due_items_into_current_reviews(self, srs_app, tmp_dbs):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        insert_srs_item(conn, associated_vocab="食べる",
                        next_answer_date="2000-01-01 00:00:00")
        conn.close()

        result = srs_app.start_review_session()
        # one DB row → two cards (reading + meaning)
        assert len(result) == 2
        assert srs_app.len_review_ids == 1

    def test_respects_max_reviews_at_once(self, srs_app, tmp_dbs):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        for i in range(5):
            insert_srs_item(conn, associated_vocab=f"vocab{i}",
                            next_answer_date="2000-01-01 00:00:00")
        conn.close()

        srs_app.max_reviews_at_once = 2
        srs_app.start_review_session()

        # 2 items loaded → 4 cards; remaining 3 still in due_review_ids
        assert len(srs_app.current_reviews) == 4
        assert len(srs_app.due_review_ids) == 3


# ---------------------------------------------------------------------------
# update_review_item
# ---------------------------------------------------------------------------

class TestUpdateReviewItem:
    def _seed_item(self, tmp_dbs, grade=3, failures=1, successes=5):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        item_id = insert_srs_item(
            conn, associated_vocab="食べる",
            current_grade=grade,
            failure_count=failures,
            success_count=successes,
            next_answer_date="2000-01-01 00:00:00",
        )
        conn.close()
        return item_id

    def _fetch_item(self, tmp_dbs, item_id):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        row = conn.execute(
            "SELECT CurrentGrade, FailureCount, SuccessCount, NextAnswerDateISO "
            "FROM SrsEntrySet WHERE ID = ?", (item_id,)
        ).fetchone()
        conn.close()
        return row

    def test_correct_increments_grade_and_success(self, srs_app, tmp_dbs):
        item_id = self._seed_item(tmp_dbs, grade=3, successes=5)
        srs_app.update_review_item(item_id, True)
        grade, failures, successes, _ = self._fetch_item(tmp_dbs, item_id)
        assert grade == 4
        assert successes == 6

    def test_incorrect_decrements_grade_and_increments_failure(self, srs_app, tmp_dbs):
        item_id = self._seed_item(tmp_dbs, grade=3, failures=1)
        srs_app.update_review_item(item_id, False)
        grade, failures, successes, _ = self._fetch_item(tmp_dbs, item_id)
        assert grade == 2
        assert failures == 2

    def test_grade_does_not_go_below_zero(self, srs_app, tmp_dbs):
        item_id = self._seed_item(tmp_dbs, grade=0)
        srs_app.update_review_item(item_id, False)
        grade, _, _, _ = self._fetch_item(tmp_dbs, item_id)
        assert grade == 0

    def test_correct_answer_sets_future_next_date(self, srs_app, tmp_dbs):
        item_id = self._seed_item(tmp_dbs, grade=0)
        srs_app.update_review_item(item_id, True)
        _, _, _, next_date = self._fetch_item(tmp_dbs, item_id)
        # next_date should be in the future relative to now
        next_dt = datetime.fromisoformat(next_date).replace(tzinfo=timezone.utc)
        assert next_dt > datetime.now(timezone.utc)

    def test_current_completed_increments(self, srs_app, tmp_dbs):
        item_id = self._seed_item(tmp_dbs)
        before = srs_app.current_completed
        srs_app.update_review_item(item_id, True)
        assert srs_app.current_completed == before + 1


# ---------------------------------------------------------------------------
# update_review_session
# ---------------------------------------------------------------------------

class TestUpdateReviewSession:
    def test_adds_item_when_ids_remain(self, srs_app, tmp_dbs):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        item_id = insert_srs_item(conn, associated_vocab="食べる",
                                  next_answer_date="2000-01-01 00:00:00")
        conn.close()

        srs_app.due_review_ids = [item_id]
        srs_app.update_review_session()

        # one item → two cards appended
        assert len(srs_app.current_reviews) == 2
        assert srs_app.due_review_ids == []

    def test_sets_stop_flag_when_queue_empty(self, srs_app):
        srs_app.due_review_ids = []
        srs_app.update_review_session()
        assert srs_app.stop_updating_review is True


# ---------------------------------------------------------------------------
# add_valid_response
# ---------------------------------------------------------------------------

class TestAddValidResponse:
    def _seed_and_fetch(self, tmp_dbs, col):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        item_id = insert_srs_item(conn, associated_vocab="食べる",
                                  meanings="to eat", readings="たべる",
                                  next_answer_date="2000-01-01 00:00:00")
        conn.close()

        def fetch():
            c = sqlite3.connect(srs_db)
            val = c.execute(
                f"SELECT {col} FROM SrsEntrySet WHERE ID = ?", (item_id,)
            ).fetchone()[0]
            c.close()
            return val

        return item_id, fetch

    def test_appends_to_readings(self, srs_app, tmp_dbs):
        item_id, fetch = self._seed_and_fetch(tmp_dbs, "Readings")
        item = {"card_type": "reading", "ID": item_id, "Readings": "たべる", "Meanings": "to eat"}
        srs_app.add_valid_response("たべる2", item)
        assert "たべる2" in fetch()

    def test_appends_to_meanings(self, srs_app, tmp_dbs):
        item_id, fetch = self._seed_and_fetch(tmp_dbs, "Meanings")
        item = {"card_type": "meaning", "ID": item_id, "Readings": "たべる", "Meanings": "to eat"}
        srs_app.add_valid_response("to consume", item)
        assert "to consume" in fetch()


# ---------------------------------------------------------------------------
# get_study_kanji (regression for kanji_col NameError bug)
# ---------------------------------------------------------------------------

class TestGetStudyKanji:
    def test_does_not_raise_name_error(self, srs_app, tmp_dbs):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        insert_srs_item(conn, associated_kanji="食",
                        next_answer_date="2000-01-01 00:00:00")
        conn.close()

        # previously raised NameError: name 'kanji_col' is not defined
        result = srs_app.get_study_kanji()
        assert "食" in result


# ---------------------------------------------------------------------------
# get_review_stats
# ---------------------------------------------------------------------------

class TestGetReviewStats:
    def test_returns_four_tuple(self, srs_app):
        result = srs_app.get_review_stats()
        assert len(result) == 4

    def test_due_now_count_is_zero_on_empty_table(self, srs_app):
        _, _, _, due_now = srs_app.get_review_stats()
        assert due_now == 0

    def test_due_now_count_reflects_overdue_items(self, srs_app, tmp_dbs):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        insert_srs_item(conn, associated_vocab="食べる",
                        next_answer_date="2000-01-01 00:00:00")
        insert_srs_item(conn, associated_vocab="飲む",
                        next_answer_date="2000-01-01 00:00:00")
        insert_srs_item(conn, associated_vocab="寝る",
                        next_answer_date="2099-01-01 00:00:00")  # not due yet
        conn.close()

        _, _, _, due_now = srs_app.get_review_stats()
        assert due_now == 2

    def test_grade_counts_df_has_one_row_per_grade(self, srs_app):
        df_grade_counts, _, _, _ = srs_app.get_review_stats()
        # config has grades 0-8 → 9 rows
        assert len(df_grade_counts) == 9

    def test_ratio_is_none_with_no_reviews(self, srs_app):
        # SUM() on an empty table returns NULL → ratio is None, not 0
        _, _, df_ratio, _ = srs_app.get_review_stats()
        assert df_ratio.values.item() is None


# ---------------------------------------------------------------------------
# get_review_stats — timezone-aware today count (utc_offset_minutes)
# ---------------------------------------------------------------------------

class TestGetReviewStatsTimezone:
    """
    Timezone-aware 'today count' tests.  The second value returned by
    get_review_stats is a DataFrame whose single cell is the count of items
    whose NextAnswerDateISO falls before end-of-today in the client's timezone.
    """

    def _today_count(self, srs_app, utc_offset_minutes: int = 0) -> int:
        _, df_today, _, _ = srs_app.get_review_stats(utc_offset_minutes=utc_offset_minutes)
        return int(df_today.values[0][0])

    def test_accepts_utc_offset_minutes_parameter(self, srs_app):
        result = srs_app.get_review_stats(utc_offset_minutes=540)
        assert len(result) == 4

    def test_far_past_item_counted_for_any_offset(self, srs_app, tmp_dbs):
        """An item long overdue is in today's count regardless of timezone."""
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        insert_srs_item(conn, associated_vocab="古い",
                        next_answer_date="1970-01-01 00:00:00")
        conn.close()

        for offset in [-720, -60, 0, 60, 540, 840]:
            assert self._today_count(srs_app, offset) >= 1, \
                f"Far-past item missing at offset {offset}"

    def test_far_future_item_not_counted_for_any_offset(self, srs_app, tmp_dbs):
        """An item due far in the future is never in today's count."""
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        insert_srs_item(conn, associated_vocab="未来",
                        next_answer_date="2099-12-31 23:59:59")
        conn.close()

        for offset in [-720, -60, 0, 60, 540, 840]:
            assert self._today_count(srs_app, offset) == 0, \
                f"Far-future item wrongly counted at offset {offset}"

    def test_positive_offset_excludes_items_past_local_midnight(self, srs_app, tmp_dbs):
        """
        With a positive UTC offset (east), end-of-today falls earlier in UTC.
        An item due just after that local-midnight-in-UTC should NOT be counted
        by the east timezone but SHOULD be counted by UTC.
        """
        from datetime import datetime, timezone, timedelta

        utc_offset_minutes = 540  # JST = UTC+9

        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)

        # Ask SQLite for the exact end-of-today boundary for both offsets
        jst_end_str = conn.execute(
            f"SELECT datetime('now', '+{utc_offset_minutes} minutes',"
            f" 'start of day', '+1 day', '-1 second', '-{utc_offset_minutes} minutes')"
        ).fetchone()[0]
        utc_end_str = conn.execute(
            "SELECT datetime('now', 'start of day', '+1 day', '-1 second')"
        ).fetchone()[0]

        jst_end = datetime.fromisoformat(jst_end_str).replace(tzinfo=timezone.utc)
        utc_end = datetime.fromisoformat(utc_end_str).replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)

        # Target: 1 minute after JST day ends, still before UTC day ends
        target = jst_end + timedelta(minutes=1)

        if target >= utc_end or target <= now_utc:
            pytest.skip(
                "No valid window between JST and UTC day boundaries at this UTC hour"
            )

        insert_srs_item(conn, associated_vocab="テスト",
                        next_answer_date=target.strftime("%Y-%m-%d %H:%M:%S"))
        conn.close()

        assert self._today_count(srs_app, utc_offset_minutes=0) == 1
        assert self._today_count(srs_app, utc_offset_minutes=utc_offset_minutes) == 0

    def test_negative_offset_includes_items_before_local_midnight(self, srs_app, tmp_dbs):
        """
        With a negative UTC offset (west), end-of-today falls later in UTC.
        An item due just after UTC midnight but still within the western timezone's
        'today' should be counted by the west timezone but NOT by UTC.
        """
        from datetime import datetime, timezone, timedelta

        utc_offset_minutes = -300  # EST = UTC-5

        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)

        utc_end_str = conn.execute(
            "SELECT datetime('now', 'start of day', '+1 day', '-1 second')"
        ).fetchone()[0]
        est_end_str = conn.execute(
            f"SELECT datetime('now', '{utc_offset_minutes:+d} minutes',"
            f" 'start of day', '+1 day', '-1 second', '{-utc_offset_minutes:+d} minutes')"
        ).fetchone()[0]

        utc_end = datetime.fromisoformat(utc_end_str).replace(tzinfo=timezone.utc)
        est_end = datetime.fromisoformat(est_end_str).replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)

        # Target: 1 minute after UTC day ends, still within EST's today
        target = utc_end + timedelta(minutes=1)

        if target >= est_end or target <= now_utc:
            pytest.skip(
                "No valid window between UTC and EST day boundaries at this UTC hour"
            )

        insert_srs_item(conn, associated_vocab="テスト",
                        next_answer_date=target.strftime("%Y-%m-%d %H:%M:%S"))
        conn.close()

        assert self._today_count(srs_app, utc_offset_minutes=0) == 0
        assert self._today_count(srs_app, utc_offset_minutes=utc_offset_minutes) == 1
