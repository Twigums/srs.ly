from dataclasses import dataclass
from typing import Optional, Dict, Literal


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

# srs_app conf
@dataclass
class SrsConfig:
    srs_interval: Dict[int, Interval]
    path_to_srs_db: str
    path_to_full_db: str
    max_reviews_at_once: int = 10
    entries_before_commit: int = 10
    match_score_threshold: int = 85
