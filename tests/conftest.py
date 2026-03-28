import sqlite3
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.dataclasses import BotConfig, Colors, SrsConfig
from src.discord_bot import Bot
from src.srs_app import SrsApp


SRS_SCHEMA = """
CREATE TABLE SrsEntrySet (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Meanings TEXT,
    Readings TEXT,
    CurrentGrade INTEGER DEFAULT 0,
    FailureCount INTEGER DEFAULT 0,
    SuccessCount INTEGER DEFAULT 0,
    AssociatedVocab TEXT,
    AssociatedKanji TEXT,
    MeaningNote TEXT,
    ReadingNote TEXT,
    Tags TEXT,
    IsDeleted INTEGER DEFAULT 0,
    LastUpdateDateISO TEXT,
    CreationDateISO TEXT,
    NextAnswerDateISO TEXT
);
"""

# srs_interval mirrors config.toml; keys are strings (as tomllib produces)
TEST_SRS_INTERVAL = {
    "0": {"value": 4,   "unit": "hours"},
    "1": {"value": 8,   "unit": "hours"},
    "2": {"value": 1,   "unit": "days"},
    "3": {"value": 3,   "unit": "days"},
    "4": {"value": 7,   "unit": "days"},
    "5": {"value": 14,  "unit": "days"},
    "6": {"value": 30,  "unit": "days"},
    "7": {"value": 120, "unit": "days"},
    "8": {"value": -1,  "unit": "none"},
}


@pytest.fixture
def tmp_dbs(tmp_path):
    """Create two temporary SQLite files: a bare full DB and an SRS DB with schema."""
    full_db = tmp_path / "full.db"
    srs_db  = tmp_path / "srs.db"

    # full DB is empty (tests that need vocab/kanji tables add them separately)
    sqlite3.connect(str(full_db)).close()

    conn = sqlite3.connect(str(srs_db))
    conn.execute(SRS_SCHEMA)
    conn.commit()
    conn.close()

    return str(full_db), str(srs_db)


@pytest.fixture
def srs_app(tmp_dbs):
    """SrsApp connected to temporary databases, torn down after the test."""
    full_db, srs_db = tmp_dbs
    config = SrsConfig(
        srs_interval=TEST_SRS_INTERVAL,
        path_to_full_db=full_db,
        path_to_srs_db=srs_db,
        entries_before_commit = 1,  # commit immediately so separate readers see writes
    )
    app = SrsApp(config)
    app.init_db()
    yield app
    app.close_db()


def insert_srs_item(conn,
                    *,
                    meanings = "test meaning",
                    readings = "テスト",
                    current_grade = 0,
                    failure_count = 0,
                    success_count = 0,
                    associated_vocab = None,
                    associated_kanji = None,
                    next_answer_date = "1970-01-01 00:00:00"
                   ):

    """Insert a single row into SrsEntrySet and return its ID."""

    conn.execute(
        """
        INSERT INTO SrsEntrySet
            (Meanings, Readings, CurrentGrade, FailureCount, SuccessCount,
             AssociatedVocab, AssociatedKanji, NextAnswerDateISO,
             LastUpdateDateISO, CreationDateISO, IsDeleted)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, '2020-01-01 00:00:00', '2020-01-01 00:00:00', 0)
        """,
        (meanings,
         readings,
         current_grade,
         failure_count,
         success_count,
         associated_vocab,
         associated_kanji,
         next_answer_date
        ),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def make_nicegui_item(type_,
                      kanji,
                      meanings,
                      readings,
                      meaning_notes = "",
                      reading_notes = ""
                     ):

    """
    Simulate the dict that NiceGUI tabs pass to add_review_item / edit_review_item.
    Each field is wrapped in a SimpleNamespace with a .value attribute.
    """

    return {
        "type":          type_,
        "kanji":         SimpleNamespace(value=kanji),
        "meanings":      SimpleNamespace(value=meanings),
        "readings":      SimpleNamespace(value=readings),
        "meaning_notes": SimpleNamespace(value=meaning_notes),
        "reading_notes": SimpleNamespace(value=reading_notes),
    }


@pytest.fixture
def mock_srs_app():
    """A MagicMock standing in for SrsApp in Discord bot tests."""
    m = MagicMock()
    m.match_score_threshold = 85
    m.current_index = 0
    m.current_completed = 0
    m.len_review_ids = 5
    m.stop_updating_review = False
    m.current_reviews = []
    return m


@pytest.fixture
def bot(mock_srs_app):
    """Discord Bot instance wired to the mock SrsApp."""
    config = BotConfig(
        srs_app=mock_srs_app,
        token="test-token",
        prefix="!",
        debug=False,
    )
    return Bot(config, Colors())
