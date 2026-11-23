from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_POSTS = [
    {
        "id": "seed-1",
        "username": "musikalskare92",
        "text": "Lyssnade precis pa detta mastarverk!",
        "tip_artist": "Bon Iver",
        "tip_song": "Holocene",
        "created_at": "2026-04-28T09:17:00Z",
    },
    {
        "id": "seed-2",
        "username": "vibes_only",
        "text": "Har nagon fler tips i samma stil?",
        "tip_artist": "James Blake",
        "tip_song": "Retrograde",
        "created_at": "2026-04-28T07:58:00Z",
    },
    {
        "id": "seed-3",
        "username": "slow.days",
        "text": "Den har var perfekt under kvallens promenad.",
        "tip_artist": "Daughter",
        "tip_song": "Youth",
        "created_at": "2026-04-27T20:24:00Z",
    },
]

DEFAULT_STATE = {
    "saved_artists": [],
    "custom_artists": [],
    "community_posts": DEFAULT_POSTS,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class JsonStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        if not self.path.exists():
            self._write_data(deepcopy(DEFAULT_STATE))

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return self._read_data()

    def upsert_saved_artist(self, item: Dict[str, Any]) -> Dict[str, Any]:
        payload = deepcopy(item)
        payload["saved_at"] = payload.get("saved_at") or utc_now_iso()

        with self._lock:
            state = self._read_data()
            state["saved_artists"] = self._upsert_item(state["saved_artists"], payload, "artist_key")
            self._write_data(state)

        return payload

    def remove_artist_everywhere(self, artist_key: str) -> None:
        with self._lock:
            state = self._read_data()
            state["saved_artists"] = [
                item for item in state["saved_artists"] if item.get("artist_key") != artist_key
            ]
            state["custom_artists"] = [
                item for item in state["custom_artists"] if item.get("artist_key") != artist_key
            ]
            state["community_posts"] = [
                item
                for item in state["community_posts"]
                if item.get("artist_key") != artist_key
            ]
            self._write_data(state)

    def remove_saved_artist(self, artist_key: str) -> None:
        with self._lock:
            state = self._read_data()
            state["saved_artists"] = [
                item for item in state["saved_artists"] if item.get("artist_key") != artist_key
            ]
            self._write_data(state)

    def saved_artist_keys(self) -> List[str]:
        state = self.snapshot()
        return [item.get("artist_key", "") for item in state.get("saved_artists", []) if item.get("artist_key")]

    def add_custom_artist(self, item: Dict[str, Any]) -> Dict[str, Any]:
        payload = deepcopy(item)
        payload["added_at"] = payload.get("added_at") or utc_now_iso()

        with self._lock:
            state = self._read_data()
            state["custom_artists"] = self._upsert_item(state["custom_artists"], payload, "artist_key")
            self._write_data(state)

        return payload

    def add_community_post(self, item: Dict[str, Any]) -> Dict[str, Any]:
        payload = deepcopy(item)
        payload["created_at"] = payload.get("created_at") or utc_now_iso()
        payload["id"] = payload.get("id") or f"post-{payload['created_at']}-{payload.get('username', 'anon')}"

        with self._lock:
            state = self._read_data()
            state["community_posts"] = [payload, *state["community_posts"]]
            self._write_data(state)

        return payload

    def _upsert_item(self, items: List[Dict[str, Any]], payload: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
        updated = [payload]
        for item in items:
            if item.get(key) != payload.get(key):
                updated.append(item)

        updated.sort(
            key=lambda item: item.get("saved_at") or item.get("added_at") or item.get("created_at") or "",
            reverse=True,
        )
        return updated

    def _read_data(self) -> Dict[str, Any]:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError):
            data = deepcopy(DEFAULT_STATE)

        for key, default in DEFAULT_STATE.items():
            data.setdefault(key, deepcopy(default))
        return data

    def _write_data(self, data: Dict[str, Any]) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
