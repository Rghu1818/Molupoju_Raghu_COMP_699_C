from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class AppConfig:
    default_subreddits: List[str] = (
        "news",
        "worldnews",
        "technology",
    )
    default_time_window: str = "7d"
    cache_ttl_minutes: int = 30
