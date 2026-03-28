import pytest
from src.dataclasses import AppConfig, BotConfig, Colors, SrsConfig


class TestColors:
    def test_default_vocab_color(self):
        assert Colors().vocab == (170, 46, 255)

    def test_default_kanji_color(self):
        assert Colors().kanji == (46, 103, 255)

    def test_progress_has_five_entries(self):
        assert len(Colors().progress) == 5

    def test_progress_entries_are_rgb_tuples(self):
        for entry in Colors().progress:
            assert len(entry) == 3
            assert all(0 <= v <= 255 for v in entry)

    def test_independent_instances_do_not_share_progress(self):
        c1 = Colors()
        c2 = Colors()
        c1.progress.append((0, 0, 0))
        assert len(c2.progress) == 5


class TestBotConfig:
    def test_all_fields_default_to_none_or_false(self):
        cfg = BotConfig()
        assert cfg.srs_app is None
        assert cfg.token is None
        assert cfg.prefix is None
        assert cfg.debug is False

    def test_fields_can_be_set(self):
        cfg = BotConfig(token="abc", prefix="!", debug=True)
        assert cfg.token == "abc"
        assert cfg.prefix == "!"
        assert cfg.debug is True


class TestSrsConfig:
    def test_required_fields_raise_without_args(self):
        with pytest.raises(TypeError):
            SrsConfig()

    def test_defaults(self):
        cfg = SrsConfig(
            srs_interval={},
            path_to_srs_db="a.db",
            path_to_full_db="b.db",
        )
        assert cfg.max_reviews_at_once == 10
        assert cfg.entries_before_commit == 10
        assert cfg.match_score_threshold == 85


class TestAppConfig:
    def test_required_keybinds(self):
        with pytest.raises(TypeError):
            AppConfig()

    def test_defaults(self):
        cfg = AppConfig(keybinds={})
        assert cfg.is_mobile is False
        assert cfg.ui_port == 8080
        assert cfg.debug_mode is False
