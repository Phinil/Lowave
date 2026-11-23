from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from .config import Settings
from .dataset import normalize_key


def parse_int(value: Any) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", text or "")
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


class JsonTTLCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        if not self.path.exists():
            self._write({})

    def get(self, section: str, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            data = self._read()
            payload = data.get(section, {}).get(key)
            if not payload:
                return None
            if payload.get("expires_at", 0) < time.time():
                return None
            return payload.get("value")

    def set(self, section: str, key: str, value: Dict[str, Any], ttl_seconds: int) -> None:
        with self._lock:
            data = self._read()
            bucket = data.setdefault(section, {})
            bucket[key] = {
                "expires_at": int(time.time() + ttl_seconds),
                "value": value,
            }
            self._write(data)

    def _read(self) -> Dict[str, Any]:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write(self, data: Dict[str, Any]) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)


class MusicApis:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.Client(
            timeout=httpx.Timeout(settings.request_timeout_seconds),
            follow_redirects=True,
        )
        self.cache = JsonTTLCache(settings.api_cache_path)

    def close(self) -> None:
        self.client.close()

    def get_lastfm_artist(self, artist_name: str) -> Dict[str, Any]:
        if not self.settings.lastfm_api_key:
            return {}

        cache_key = normalize_key(artist_name)
        cached = self.cache.get("lastfm_artist", cache_key)
        if cached is not None:
            return cached

        payload = self._get_json(
            "https://ws.audioscrobbler.com/2.0/",
            params={
                "method": "artist.getinfo",
                "artist": artist_name,
                "api_key": self.settings.lastfm_api_key,
                "format": "json",
                "autocorrect": 1,
            },
        )

        if not payload or payload.get("error"):
            return {}

        artist = payload.get("artist", {})
        similar = artist.get("similar", {}).get("artist", [])
        result = {
            "name": artist.get("name") or artist_name,
            "listeners": parse_int(artist.get("stats", {}).get("listeners")),
            "playcount": parse_int(artist.get("stats", {}).get("playcount")),
            "bio": strip_html(artist.get("bio", {}).get("summary", "")),
            "url": artist.get("url"),
            "similar_artists": [item.get("name") for item in similar[:6] if item.get("name")],
        }
        self.cache.set("lastfm_artist", cache_key, result, ttl_seconds=60 * 60 * 24 * 7)
        return result

    def get_deezer_artist(self, artist_name: str) -> Dict[str, Any]:
        cache_key = normalize_key(artist_name)
        cached = self.cache.get("deezer_artist", cache_key)
        if cached is not None:
            return cached

        search = self._get_json(
            "https://api.deezer.com/search/artist",
            params={"q": artist_name, "limit": 5},
        )
        candidates = search.get("data", []) if search else []
        if not candidates:
            return {}

        best = self._pick_best_artist(artist_name, candidates)
        artist_id = best.get("id")
        if not artist_id:
            return {}

        details = self._get_json(f"https://api.deezer.com/artist/{artist_id}") or {}
        top_tracks_payload = self._get_json(
            f"https://api.deezer.com/artist/{artist_id}/top",
            params={"limit": 3},
        ) or {}
        top_tracks = top_tracks_payload.get("data", [])
        first_track = top_tracks[0] if top_tracks else {}

        result = {
            "artist_id": artist_id,
            "name": details.get("name") or best.get("name") or artist_name,
            "fans": parse_int(details.get("nb_fan") or best.get("nb_fan")),
            "image": details.get("picture_xl")
            or details.get("picture_big")
            or best.get("picture_xl")
            or best.get("picture_big")
            or best.get("picture_medium"),
            "link": details.get("link") or best.get("link"),
            "preview": first_track.get("preview"),
            "top_tracks": [
                {
                    "title": item.get("title"),
                    "preview": item.get("preview"),
                    "release_date": item.get("release_date"),
                }
                for item in top_tracks
            ],
            "release_date": first_track.get("release_date"),
        }
        self.cache.set("deezer_artist", cache_key, result, ttl_seconds=60 * 60 * 24 * 3)
        return result

    def lookup_track_by_isrc(self, isrc: str) -> Dict[str, Any]:
        normalized = isrc.strip().upper()
        cached = self.cache.get("deezer_isrc", normalized)
        if cached is not None:
            return cached

        track_payload = self._get_json(f"https://api.deezer.com/track/isrc:{normalized}") or {}
        if not track_payload.get("id"):
            track_payload = self._search_track_by_isrc(normalized)

        if not track_payload.get("id"):
            return {}

        track_id = track_payload.get("id")
        details = self._get_json(f"https://api.deezer.com/track/{track_id}") or track_payload

        result = {
            "track_id": details.get("id"),
            "artist": details.get("artist", {}).get("name"),
            "song": details.get("title"),
            "album": details.get("album", {}).get("title"),
            "image": details.get("album", {}).get("cover_xl")
            or details.get("album", {}).get("cover_big")
            or details.get("album", {}).get("cover_medium"),
            "preview": details.get("preview"),
            "deezer_link": details.get("link"),
            "release_date": details.get("release_date"),
            "isrc": details.get("isrc") or normalized,
        }
        self.cache.set("deezer_isrc", normalized, result, ttl_seconds=60 * 60 * 24 * 30)
        return result

    def _search_track_by_isrc(self, isrc: str) -> Dict[str, Any]:
        for query in (f'isrc:"{isrc}"', isrc):
            payload = self._get_json(
                "https://api.deezer.com/search/track",
                params={"q": query, "limit": 10},
            ) or {}
            for item in payload.get("data", []):
                if str(item.get("isrc", "")).upper() == isrc:
                    return item
        return {}

    def _pick_best_artist(self, artist_name: str, candidates: list[dict[str, Any]]) -> Dict[str, Any]:
        needle = normalize_key(artist_name)
        exact = [item for item in candidates if normalize_key(item.get("name")) == needle]
        if exact:
            return exact[0]

        startswith = [
            item for item in candidates
            if normalize_key(item.get("name", "")).startswith(needle[:8])
        ]
        if startswith:
            return startswith[0]

        return candidates[0]

    def _get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception:
            return {}
