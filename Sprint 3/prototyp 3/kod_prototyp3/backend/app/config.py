from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional before dependencies are installed
    def load_dotenv() -> bool:
        return False


load_dotenv()


@dataclass(slots=True)
class Settings:
    base_dir: Path
    frontend_dir: Path
    data_dir: Path
    spotify_csv_path: Path
    user_state_path: Path
    api_cache_path: Path
    lastfm_api_key: str
    request_timeout_seconds: float
    result_limit: int
    max_local_popularity: float
    max_lastfm_listeners: int
    max_deezer_fans: int


def get_settings() -> Settings:
    base_dir = Path(__file__).resolve().parents[2]
    data_dir = base_dir / "data"

    return Settings(
        base_dir=base_dir,
        frontend_dir=base_dir / "frontend",
        data_dir=data_dir,
        spotify_csv_path=data_dir / "spotify_tracks.csv",
        user_state_path=data_dir / "user_state.json",
        api_cache_path=data_dir / "api_cache.json",
        lastfm_api_key=os.getenv("LASTFM_API_KEY", "").strip(),
        request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "12")),
        result_limit=int(os.getenv("RESULT_LIMIT", "6")),
        max_local_popularity=float(os.getenv("MAX_LOCAL_POPULARITY", "45")),
        max_lastfm_listeners=int(os.getenv("MAX_LASTFM_LISTENERS", "350000")),
        max_deezer_fans=int(os.getenv("MAX_DEEZER_FANS", "120000")),
    )
