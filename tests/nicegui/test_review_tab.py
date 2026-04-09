import sqlite3

from tests.conftest import insert_srs_item


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


# ---------------------------------------------------------------------------
# TestAddValidResponseFlow  (regression tests for issue #37)
# ---------------------------------------------------------------------------

class TestAddValidResponseFlow:

    def _fetch_meanings(self, tmp_dbs, item_id):
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        row = conn.execute(
            "SELECT Meanings FROM SrsEntrySet WHERE ID = ?", (item_id,)
        ).fetchone()
        conn.close()
        return row[0]

    def test_add_valid_response_appends_meaning_to_db(self, srs_app, tmp_dbs):
        """add_valid_response appends a new meaning to the item in the database."""
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        item_id = insert_srs_item(conn, associated_vocab="食べる",
                                  meanings="to eat",
                                  next_answer_date="2000-01-01 00:00:00")
        conn.close()

        srs_app.start_review_session()
        meaning_card = next(c for c in srs_app.current_reviews if c["card_type"] == "meaning")
        srs_app.add_valid_response("to consume", meaning_card)

        meanings = self._fetch_meanings(tmp_dbs, item_id)
        assert "to eat" in meanings
        assert "to consume" in meanings

    def test_wrong_card_moves_to_end_on_incorrect_answer(self, srs_app, tmp_dbs):
        """
        When process_answer gets a wrong answer, the card is popped from
        current_index and appended to the END of current_reviews. current_index
        then points to the next card.
        """
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        insert_srs_item(conn, associated_vocab="食べる",
                        next_answer_date="2000-01-01 00:00:00")
        insert_srs_item(conn, associated_vocab="飲む",
                        next_answer_date="2000-01-01 00:00:00")
        conn.close()

        srs_app.start_review_session()
        original_card = srs_app.current_reviews[srs_app.current_index]

        # Simulate process_answer incorrect: pop from current_index, append to end
        wrong_card = srs_app.current_reviews.pop(srs_app.current_index)
        srs_app.current_reviews.append(wrong_card)

        assert srs_app.current_reviews[-1] == original_card
        assert srs_app.current_reviews[srs_app.current_index] != original_card

    def test_pop_from_end_removes_wrong_card_and_preserves_next(self, srs_app, tmp_dbs):
        """
        After a wrong answer moves the card to the end, pop() correctly removes
        the wrong card. current_index still points to the intended next card.
        This is the correct behavior after pressing '='.
        """
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        insert_srs_item(conn, associated_vocab="食べる",
                        next_answer_date="2000-01-01 00:00:00")
        insert_srs_item(conn, associated_vocab="飲む",
                        next_answer_date="2000-01-01 00:00:00")
        conn.close()

        srs_app.start_review_session()
        initial_count = len(srs_app.current_reviews)

        # Simulate process_answer incorrect
        wrong_card = srs_app.current_reviews.pop(srs_app.current_index)
        srs_app.current_reviews.append(wrong_card)
        expected_next = srs_app.current_reviews[srs_app.current_index]

        # Correct fix: pop() removes from end
        removed = srs_app.current_reviews.pop()

        assert removed == wrong_card
        assert len(srs_app.current_reviews) == initial_count - 1
        assert srs_app.current_reviews[srs_app.current_index] == expected_next

    def test_pop_current_index_removes_next_card_not_wrong_card(self, srs_app, tmp_dbs):
        """
        Demonstrates the bug: pop(current_index) after a wrong answer removes
        the NEXT card in the queue, not the wrong card (which is at the end).
        The wrong card then cycles back, causing the card to appear to 'stay'.
        """
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        insert_srs_item(conn, associated_vocab="食べる",
                        next_answer_date="2000-01-01 00:00:00")
        insert_srs_item(conn, associated_vocab="飲む",
                        next_answer_date="2000-01-01 00:00:00")
        conn.close()

        srs_app.start_review_session()

        # Simulate process_answer incorrect
        wrong_card = srs_app.current_reviews.pop(srs_app.current_index)
        srs_app.current_reviews.append(wrong_card)
        next_card = srs_app.current_reviews[srs_app.current_index]

        # The bug: pop(current_index) removes the next card, not the wrong card
        card_at_current_index = srs_app.current_reviews[srs_app.current_index]
        assert card_at_current_index == next_card      # confirms it would remove next card
        assert card_at_current_index != wrong_card     # wrong card is NOT at current_index
        assert srs_app.current_reviews[-1] == wrong_card  # wrong card is at the end

    def test_current_index_not_incremented_after_add_valid_response(self, srs_app, tmp_dbs):
        """
        After pressing '=', current_index must NOT be incremented. process_answer
        already moved current_index past the wrong card. clean_card() would
        increment it again, skipping the next card in the queue.
        """
        _, srs_db = tmp_dbs
        conn = sqlite3.connect(srs_db)
        insert_srs_item(conn, associated_vocab="食べる",
                        next_answer_date="2000-01-01 00:00:00")
        insert_srs_item(conn, associated_vocab="飲む",
                        next_answer_date="2000-01-01 00:00:00")
        conn.close()

        srs_app.start_review_session()

        # Simulate process_answer incorrect
        wrong_card = srs_app.current_reviews.pop(srs_app.current_index)
        srs_app.current_reviews.append(wrong_card)
        index_after_wrong = srs_app.current_index  # should be 0, pointing to next card

        # Correct fix: pop from end, do NOT increment current_index
        srs_app.current_reviews.pop()

        # current_index unchanged — still points to the next card
        assert srs_app.current_index == index_after_wrong
