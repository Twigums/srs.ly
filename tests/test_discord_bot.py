import pytest
from unittest.mock import MagicMock, patch

from src.discord_bot import Bot, AppState, romaji_to_kana
from src.dataclasses import BotConfig, Colors


# ---------------------------------------------------------------------------
# romaji_to_kana
# ---------------------------------------------------------------------------

class TestRomajiToKana:
    def test_basic_conversion(self):
        assert romaji_to_kana("ka") == "か"

    def test_lowercases_input(self):
        assert romaji_to_kana("KA") == romaji_to_kana("ka")

    def test_nn_produces_n(self):
        # "nn" should become "n'" which pyokaka converts to ん
        result = romaji_to_kana("tabemasu nn")
        assert "ん" in result

    def test_full_word(self):
        assert romaji_to_kana("taberu") == "たべる"

    def test_empty_string(self):
        assert romaji_to_kana("") == ""


# ---------------------------------------------------------------------------
# _start_review
# ---------------------------------------------------------------------------

class TestStartReview:
    def test_returns_true_when_reviews_exist(self, bot, mock_srs_app):
        mock_srs_app.start_review_session.return_value = [{"id": 1}]
        assert bot._start_review() is True
        assert bot.item_dict == {}

    def test_returns_false_when_no_reviews(self, bot, mock_srs_app):
        mock_srs_app.start_review_session.return_value = []
        assert bot._start_review() is False


# ---------------------------------------------------------------------------
# _clean_buffer
# ---------------------------------------------------------------------------

class TestCleanBuffer:
    def test_resets_state(self, bot):
        bot.showing_wrong_message = True
        bot.previous_answer = "wrong"
        bot._clean_buffer()
        assert bot.showing_wrong_message is False
        assert bot.previous_answer is None


# ---------------------------------------------------------------------------
# process_answer — reading cards
# ---------------------------------------------------------------------------

class TestProcessAnswerReading:
    def _set_reading_card(self, bot, item_id=1, readings="たべる"):
        bot.current_card.card_type = "reading"
        bot.current_card.review_type = "vocab"
        bot.current_card.item_id = item_id
        bot.current_card.readings = readings
        bot.current_card.meanings = "to eat"

    def _setup_reviews(self, bot, mock_srs_app, item_id=1):
        review = {"ID": item_id, "card_type": "reading"}
        mock_srs_app.current_reviews = [review]
        mock_srs_app.current_index = 0
        bot.item_dict = {}

    def test_correct_reading_returns_true(self, bot, mock_srs_app):
        self._set_reading_card(bot)
        self._setup_reviews(bot, mock_srs_app)
        is_correct, _ = bot.process_answer("taberu", False)
        assert is_correct is True

    def test_incorrect_reading_returns_false(self, bot, mock_srs_app):
        self._set_reading_card(bot)
        self._setup_reviews(bot, mock_srs_app)
        is_correct, _ = bot.process_answer("nomimasu", False)
        assert is_correct is False

    def test_incorrect_reading_reappends_to_reviews(self, bot, mock_srs_app):
        self._set_reading_card(bot)
        review = {"ID": 1, "card_type": "reading"}
        mock_srs_app.current_reviews = [review]
        mock_srs_app.current_index = 0
        bot.item_dict = {}

        bot.process_answer("nomimasu", False)
        # item was popped then re-appended because the answer was wrong
        assert len(mock_srs_app.current_reviews) == 1

    def test_will_submit_true_records_item_in_dict_even_if_wrong(self, bot, mock_srs_app):
        """will_submit=True: even a wrong answer is recorded in item_dict (as 0)."""
        self._set_reading_card(bot)
        review = {"ID": 1, "card_type": "reading"}
        mock_srs_app.current_reviews = [review]
        mock_srs_app.current_index = 0
        bot.item_dict = {}

        bot.process_answer("nomimasu", True)
        assert 1 in bot.item_dict
        assert 0 in bot.item_dict[1]  # wrong answer recorded as 0


# ---------------------------------------------------------------------------
# process_answer — meaning cards
# ---------------------------------------------------------------------------

class TestProcessAnswerMeaning:
    def _set_meaning_card(self, bot, item_id=1, meanings="to eat"):
        bot.current_card.card_type = "meaning"
        bot.current_card.review_type = "vocab"
        bot.current_card.item_id = item_id
        bot.current_card.readings = "たべる"
        bot.current_card.meanings = meanings

    def _setup_reviews(self, bot, mock_srs_app, item_id=1):
        review = {"ID": item_id, "card_type": "meaning"}
        mock_srs_app.current_reviews = [review]
        mock_srs_app.current_index = 0
        bot.item_dict = {}

    def test_close_meaning_passes_fuzzy_threshold(self, bot, mock_srs_app):
        self._set_meaning_card(bot)
        self._setup_reviews(bot, mock_srs_app)
        # exact match against "to eat" scores 100, well above the 85 threshold
        is_correct, _ = bot.process_answer("to eat", False)
        assert is_correct is True

    def test_wrong_meaning_fails(self, bot, mock_srs_app):
        self._set_meaning_card(bot)
        self._setup_reviews(bot, mock_srs_app)
        is_correct, _ = bot.process_answer("xyzzy", False)
        assert is_correct is False


# ---------------------------------------------------------------------------
# process_answer — item completion logic
# ---------------------------------------------------------------------------

class TestProcessAnswerCompletion:
    def test_both_correct_first_try_calls_update_with_true(self, bot, mock_srs_app):
        """Both reading and meaning correct on first attempt → passed=True."""
        bot.current_card.card_type = "meaning"
        bot.current_card.review_type = "vocab"
        bot.current_card.item_id = 42
        bot.current_card.readings = "たべる"
        bot.current_card.meanings = "to eat"

        mock_srs_app.current_reviews = [{"ID": 42}]
        mock_srs_app.current_index = 0
        # Simulate reading card already marked correct
        bot.item_dict = {42: [1]}

        bot.process_answer("to eat", False)

        mock_srs_app.update_review_item.assert_called_once_with(42, True)
        mock_srs_app.update_review_session.assert_called_once()

    def test_one_wrong_then_correct_calls_update_with_false(self, bot, mock_srs_app):
        """Reading had a failure before passing → passed=False."""
        bot.current_card.card_type = "meaning"
        bot.current_card.review_type = "vocab"
        bot.current_card.item_id = 42
        bot.current_card.readings = "たべる"
        bot.current_card.meanings = "to eat"

        mock_srs_app.current_reviews = [{"ID": 42}]
        mock_srs_app.current_index = 0
        # [0, 1] means reading had a failure, then passed; now meaning passes
        bot.item_dict = {42: [0, 1]}

        bot.process_answer("to eat", False)

        mock_srs_app.update_review_item.assert_called_once_with(42, False)


# ---------------------------------------------------------------------------
# update_embed
# ---------------------------------------------------------------------------

class TestUpdateEmbed:
    def test_no_reviews_returns_done_embed(self, bot, mock_srs_app):
        mock_srs_app.get_current_item.return_value = None
        embed = bot.update_embed()
        assert embed.title == "No more reviews!"

    def test_reading_card_uses_black_squares(self, bot, mock_srs_app):
        mock_srs_app.get_current_item.return_value = {
            "review_type": "vocab",
            "card_type": "reading",
            "ID": 1,
            "Readings": "たべる",
            "Meanings": "to eat",
            "AssociatedKanji": None,
            "AssociatedVocab": "食べる",
        }
        embed = bot.update_embed()
        assert ":black_large_square:" in embed.description

    def test_meaning_card_uses_white_squares(self, bot, mock_srs_app):
        mock_srs_app.get_current_item.return_value = {
            "review_type": "vocab",
            "card_type": "meaning",
            "ID": 1,
            "Readings": "たべる",
            "Meanings": "to eat",
            "AssociatedKanji": None,
            "AssociatedVocab": "食べる",
        }
        embed = bot.update_embed()
        assert ":white_large_square:" in embed.description


# ---------------------------------------------------------------------------
# wrong_embed
# ---------------------------------------------------------------------------

class TestWrongEmbed:
    def test_reading_card_converts_answer_to_kana(self, bot):
        bot.current_card.card_type = "reading"
        bot.current_card.review_type = "vocab"
        bot.current_card.vocab = "食べる"
        bot.current_card.kanji = None
        bot.srs_app.current_completed = 0
        bot.srs_app.len_review_ids = 5

        embed = bot.wrong_embed("taberu", "たべる")
        # The embed fields should include the kana form
        field_values = [f.value for f in embed.fields]
        assert any("たべる" in v for v in field_values)

    def test_meaning_card_shows_raw_answer(self, bot):
        bot.current_card.card_type = "meaning"
        bot.current_card.review_type = "vocab"
        bot.current_card.vocab = "食べる"
        bot.current_card.kanji = None
        bot.srs_app.current_completed = 0
        bot.srs_app.len_review_ids = 5

        embed = bot.wrong_embed("to drink", "to eat")
        field_values = [f.value for f in embed.fields]
        assert any("to drink" in v for v in field_values)
