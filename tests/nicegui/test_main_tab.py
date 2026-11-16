from unittest.mock import patch

import pandas as pd

from src.dataclasses import AppConfig
from src.nicegui.main_tab import MainTab


# ---------------------------------------------------------------------------
# MainTab stats messages
# load_stats() runs while the page is being built and then every 60 s, so its
# messages are labels in the stats grid instead of ui.notify toasts
# ---------------------------------------------------------------------------

def _build_main_tab(mock_srs_app):
    config = AppConfig(keybinds = {}, srs_app = mock_srs_app)

    with patch("src.nicegui.main_tab.ui") as mock_ui, patch("src.nicegui.main_tab.app"):
        MainTab(config)

    labels = [c.args[0] for c in mock_ui.label.call_args_list if c.args]
    return mock_ui, labels


def _stats(grade_counts, due_now = 0):
    df_grade_counts = pd.DataFrame({"val": range(len(grade_counts)), "count": grade_counts})
    return df_grade_counts, pd.DataFrame([[3]]), pd.DataFrame({"ratio": [0.5]}), due_now


class TestMainTabMessages:
    def test_disconnected_db_is_shown_in_the_page(self, mock_srs_app):
        mock_srs_app.get_review_stats.return_value = None

        mock_ui, labels = _build_main_tab(mock_srs_app)

        mock_ui.notify.assert_not_called()
        assert "DB not connected." in labels

    def test_no_grades_is_shown_in_the_page(self, mock_srs_app):
        mock_srs_app.get_review_stats.return_value = _stats([])

        mock_ui, labels = _build_main_tab(mock_srs_app)

        mock_ui.notify.assert_not_called()
        assert "Start adding items and reviewing to see stats!" in labels

    def test_stats_are_shown(self, mock_srs_app):
        mock_srs_app.get_review_stats.return_value = _stats([1, 2, 3, 4, 5, 6, 7, 8, 9], due_now = 2)

        mock_ui, labels = _build_main_tab(mock_srs_app)

        mock_ui.notify.assert_not_called()
        assert "2 / 3" in labels
        assert "Set in Stone" in labels

        # the due count comes from the stats query instead of loading every due review
        mock_srs_app.get_due_reviews.assert_not_called()
