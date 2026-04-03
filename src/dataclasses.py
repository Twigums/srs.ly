from dataclasses import dataclass
from typing import Optional, Dict, Literal, List, Tuple


# init config
@dataclass
class AppConfig:
    keybinds: Dict[str, str]

    # check if user is using mobile or not
    is_mobile: bool = False

    srs_app: Optional[object] = None
    ui_port: int = 8080
    ui_web_title: str = "srs.ly"
    ui_storage_secret: str = "test"
    debug_mode: bool = False

# definition for an interval in config.toml
@dataclass
class Interval:
    value: int
    unit: Literal["hours", "days", "none"]

# discord bot config
@dataclass
class BotConfig:
    srs_app: Optional[object] = None
    token: Optional[str] = None
    prefix: Optional[str] = None
    debug: bool = False

# srs_app conf
@dataclass
class SrsConfig:
    srs_interval: Dict[int, Interval]
    path_to_srs_db: str
    path_to_full_db: str
    max_reviews_at_once: int = 10
    entries_before_commit: int = 10
    match_score_threshold: int = 85

# colors used by the Discord bot embeds
@dataclass
class Colors:
    vocab: Tuple[int, int, int] = (170, 46, 255)   # purple
    kanji: Tuple[int, int, int] = (46, 103, 255)   # blue
    kana: Tuple[int, int, int] = (57, 57, 57)      # dark gray
    romaji: Tuple[int, int, int] = (228, 228, 228) # light gray

# card type used during Discord bot review sessions
class Card:
    review_type: Optional[str] = None
    card_type: Optional[str] = None
    item_id: Optional[int] = None
    readings: Optional[List[str]] = None
    meanings: Optional[List[str]] = None
    kanji: Optional[str] = None
    vocab: Optional[str] = None
