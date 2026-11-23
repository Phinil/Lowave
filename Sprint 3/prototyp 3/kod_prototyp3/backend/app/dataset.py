from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import pandas as pd


FEATURE_COLUMNS = [
    "danceability",
    "energy",
    "valence",
    "acousticness",
    "instrumentalness",
]

DISCOVER_GENRES: Dict[str, List[str]] = {
    "Indie": ["indie", "indie-pop", "alternative", "alt-rock"],
    "Pop": ["pop", "power-pop"],
    "Rock": ["rock", "alt-rock", "punk-rock", "psych-rock", "rock-n-roll"],
    "Jazz": ["jazz", "blues", "soul"],
    "Electronic": ["electronic", "house", "deep-house", "techno", "ambient", "club"],
    "R&B": ["r-n-b", "soul", "funk"],
    "Hip-Hop": ["hip-hop", "rap", "trip-hop"],
    "Classical": ["classical", "opera", "piano"],
}

PROMPT_SUGGESTIONS = [
    "Låtar som låter som en regnig söndagsmorgon",
    "Musik för sena nattliga bilresor",
    "Upbeat låtar att träna till",
    "Chill vibes för pluggande",
]


def normalize_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s+", " ", text)
    return text


def split_artists(value: Any) -> List[str]:
    raw = str(value or "")
    parts = [part.strip() for part in re.split(r"[;,]", raw) if part.strip()]
    return parts


def clean_text(value: Any) -> str:
    return str(value or "").strip()


@dataclass(slots=True)
class DatasetSummary:
    spotify_rows: int
    artist_count: int
    genre_count: int


class DatasetCatalog:
    def __init__(self, csv_path: Path) -> None:
        self.df = self._load(csv_path)
        self.artist_frame = self._build_artist_frame(self.df)
        self.artist_map = {
            row["artist_key"]: row.to_dict()
            for _, row in self.artist_frame.iterrows()
        }

    def summary(self) -> DatasetSummary:
        return DatasetSummary(
            spotify_rows=int(len(self.df)),
            artist_count=int(len(self.artist_frame)),
            genre_count=int(self.df["track_genre"].nunique()),
        )

    def discover_genres(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for label, genres in DISCOVER_GENRES.items():
            count = int(self.df["track_genre"].isin(genres).sum())
            items.append({"label": label, "dataset_genres": genres, "count": count})
        return items

    def rows_for_genres(self, labels: Sequence[str]) -> pd.DataFrame:
        genre_values = self.map_genre_labels(labels)
        if not genre_values:
            return self.df.copy()
        return self.df[self.df["track_genre"].isin(genre_values)].copy()

    def map_genre_labels(self, labels: Sequence[str]) -> List[str]:
        values: List[str] = []
        for label in labels:
            values.extend(DISCOVER_GENRES.get(label, []))
        return sorted(set(values))

    def artist_record(self, artist_key: str) -> Dict[str, Any]:
        return dict(self.artist_map.get(artist_key, {}))

    def rows_for_artist_key(self, artist_key: str) -> pd.DataFrame:
        return self.df[self.df["artist_key"] == artist_key].copy()

    def _load(self, csv_path: Path) -> pd.DataFrame:
        df = pd.read_csv(csv_path)
        df = df.loc[:, ~df.columns.str.contains(r"^Unnamed")]
        df = df.drop_duplicates(subset=["track_id"]).copy()

        for column in ["popularity", "duration_ms", *FEATURE_COLUMNS]:
            df[column] = pd.to_numeric(df[column], errors="coerce")

        df["track_genre"] = df["track_genre"].fillna("unknown").astype(str)
        df["primary_artist"] = df["artists"].map(self._first_artist)
        df["artist_key"] = df["primary_artist"].map(normalize_key)
        df["search_blob"] = (
            df["track_name"].fillna("")
            + " "
            + df["album_name"].fillna("")
            + " "
            + df["artists"].fillna("")
            + " "
            + df["track_genre"].fillna("")
        ).str.lower()

        return df[df["artist_key"] != ""].reset_index(drop=True)

    def _build_artist_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        grouped = df.groupby(["artist_key", "primary_artist"], as_index=False).agg(
            track_count=("track_id", "count"),
            avg_popularity=("popularity", "mean"),
            max_popularity=("popularity", "max"),
            avg_danceability=("danceability", "mean"),
            avg_energy=("energy", "mean"),
            avg_valence=("valence", "mean"),
            avg_acousticness=("acousticness", "mean"),
            avg_instrumentalness=("instrumentalness", "mean"),
        )

        top_genres: List[List[str]] = []
        sample_tracks: List[List[str]] = []
        for artist_key in grouped["artist_key"]:
            artist_rows = df[df["artist_key"] == artist_key]
            genres = artist_rows["track_genre"].value_counts().head(3).index.tolist()
            tracks = artist_rows.sort_values("popularity", ascending=False)["track_name"].head(3).tolist()
            top_genres.append(genres)
            sample_tracks.append(tracks)

        grouped["top_genres"] = top_genres
        grouped["sample_tracks"] = sample_tracks
        grouped["avg_popularity"] = grouped["avg_popularity"].round(2)
        grouped["max_popularity"] = grouped["max_popularity"].round(2)

        return grouped.sort_values(["avg_popularity", "track_count"], ascending=[True, False]).reset_index(drop=True)

    def _first_artist(self, value: Any) -> str:
        artists = split_artists(value)
        return artists[0] if artists else clean_text(value)
