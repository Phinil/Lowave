from __future__ import annotations

import random
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import euclidean_distances

import pandas as pd

from .config import Settings
from .dataset import (
    DISCOVER_GENRES,
    FEATURE_COLUMNS,
    PROMPT_SUGGESTIONS,
    DatasetCatalog,
    normalize_key,
)
from .external_services import MusicApis
from .storage import JsonStore, utc_now_iso


STOPWORDS = {
    "som",
    "for",
    "med",
    "och",
    "till",
    "vill",
    "sanger",
    "låtar",
    "latar",
    "musik",
    "artist",
    "artister",
    "the",
    "att",
    "pa",
    "på",
    "min",
    "mitt",
    "mina",
}

PROMPT_GENRE_HINTS = {
    "indie": "Indie",
    "indiepop": "Indie",
    "pop": "Pop",
    "rock": "Rock",
    "jazz": "Jazz",
    "electronic": "Electronic",
    "electronisk": "Electronic",
    "house": "Electronic",
    "techno": "Electronic",
    "ambient": "Electronic",
    "r&b": "R&B",
    "rnb": "R&B",
    "soul": "R&B",
    "hiphop": "Hip-Hop",
    "hip-hop": "Hip-Hop",
    "rap": "Hip-Hop",
    "klassisk": "Classical",
    "classical": "Classical",
}

PROMPT_MOODS = {
    "regn": {"valence": 0.23, "energy": 0.30, "acousticness": 0.55},
    "rain": {"valence": 0.23, "energy": 0.30, "acousticness": 0.55},
    "morgon": {"valence": 0.38, "energy": 0.35, "acousticness": 0.45},
    "morning": {"valence": 0.38, "energy": 0.35, "acousticness": 0.45},
    "natt": {"valence": 0.40, "energy": 0.56, "danceability": 0.60},
    "night": {"valence": 0.40, "energy": 0.56, "danceability": 0.60},
    "bilen": {"energy": 0.62, "danceability": 0.62, "valence": 0.50},
    "car": {"energy": 0.62, "danceability": 0.62, "valence": 0.50},
    "plugg": {"energy": 0.30, "acousticness": 0.50, "instrumentalness": 0.25},
    "study": {"energy": 0.30, "acousticness": 0.50, "instrumentalness": 0.25},
    "träna": {"energy": 0.84, "danceability": 0.74, "valence": 0.70},
    "train": {"energy": 0.84, "danceability": 0.74, "valence": 0.70},
    "upbeat": {"energy": 0.78, "danceability": 0.72, "valence": 0.72},
    "chill": {"energy": 0.28, "valence": 0.45, "acousticness": 0.42},
    "fokus": {"energy": 0.32, "acousticness": 0.50, "instrumentalness": 0.30},
    "focus": {"energy": 0.32, "acousticness": 0.50, "instrumentalness": 0.30},
}


@dataclass(slots=True)
class LibraryContext:
    seed_names: List[str]
    preferred_genres: List[str]
    similar_artist_keys: set[str]
    avg_vector: Dict[str, float]


class RecommendationEngine:
    def __init__(
        self,
        settings: Settings,
        dataset: DatasetCatalog,
        apis: MusicApis,
        store: JsonStore,
        
    ) -> None:
        self.settings = settings
        self.dataset = dataset
        self.apis = apis
        self.store = store

        self.feature_cols = [ "danceability", "energy", "loudness",
            "tempo", "instrumentalness",
            "acousticness", "valence"]

        self.cluster_names = {
            0: "danceable_mainstream", 
            1: "upbeat_positive",
            2: "chill_acoustic_melancholy",
            3: "ambient_instrumental_chill",
            4: "electronic_edm_instrumental"
}

        self.ml_df = self.dataset.df.copy()

        for col in self.feature_cols:
            self.ml_df[col] = pd.to_numeric(self.ml_df[col], errors="coerce")

        self.ml_df = self.ml_df.dropna(subset=self.feature_cols)

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(self.ml_df[self.feature_cols])

        self.kmeans = KMeans(n_clusters=5, random_state=42, n_init=10)
        self.ml_df["kmeans_cluster"] = self.kmeans.fit_predict(X_scaled)
        
        self.cluster_profiles = self.ml_df.groupby("kmeans_cluster")[self.feature_cols].mean()

    def bootstrap_payload(self) -> Dict[str, Any]:
        summary = self.dataset.summary()
        state = self.store.snapshot()
        return {
            "genres": self.dataset.discover_genres(),
            "prompt_suggestions": PROMPT_SUGGESTIONS,
            "small_artist_definition": self.small_artist_definition(),
            "stats": {
                "spotify_rows": summary.spotify_rows,
                "artist_count": summary.artist_count,
                "genre_count": summary.genre_count,
                "saved_count": len(state.get("saved_artists", [])),
                "custom_count": len(state.get("custom_artists", [])),
            },
            "saved_artist_keys": self.store.saved_artist_keys(),
        }

    def small_artist_definition(self) -> Dict[str, Any]:
        return {
            "title": "Hur vi definierar mindre artister",
            "text": (
                "Appen prioriterar artister som ligger lagom lågt i synlighet. "
                "Vi väger ihop Spotify-datasetets popularitet med Last.fm-lyssnare "
                "och Deezer-fans när de finns tillgängliga."
            ),
            "thresholds": {
                "spotify_avg_popularity_max": self.settings.max_local_popularity,
                "lastfm_listeners_max": self.settings.max_lastfm_listeners,
                "deezer_fans_max": self.settings.max_deezer_fans,
            },
        }

    def discover_artists(self, genres: Sequence[str], limit: int) -> Dict[str, Any]:
        genre_labels = [label for label in genres if label in DISCOVER_GENRES]
        base_df = self.dataset.rows_for_genres(genre_labels)
        context = self._build_library_context()
        request = {
            "genres": genre_labels,
            "tokens": [],
            "mood_targets": {},
            "year_filter": None,
            "source_label": "Utvalda efter dina genreval",
        }
        scored = self._score_rows(base_df, request, context)
        results = self._assemble_results(scored, request, context, limit)
        return {
            "view": "discover",
            "query_label": ", ".join(genre_labels) if genre_labels else "Alla genrer",
            "results": results,
            "saved_artist_keys": self.store.saved_artist_keys(),
            "small_artist_definition": self.small_artist_definition(),
        }

    def prompt_search(self, prompt: str, limit: int) -> Dict[str, Any]:
        request = self._interpret_prompt(prompt)
        base_df = self.dataset.rows_for_genres(request["genres"])
        context = self._build_library_context()
        scored = self._score_rows(base_df, request, context)
        results = self._assemble_results(scored, request, context, limit)
        return {
            "view": "search",
            "query_label": prompt,
            "interpretation": {
                "genres": request["genres"],
                "tokens": request["tokens"][:6],
                "year_filter": request["year_filter"],
            },
            "results": results,
            "saved_artist_keys": self.store.saved_artist_keys(),
        }
    
    def _prompt_to_cluster(self, prompt: str) -> int:
        prompt = prompt.lower()

        if any(word in prompt for word in [
        "ledsen", "deppig", "sorglig", "gråta", "ensam",
        "indie", "akustisk", "regn", "kväll", "soft" ]):
         return 2
        
        if any(word in prompt for word in [
        "ambient", "instrumental", "bakgrund", "piano", "sova",
        "lugn", "chill", "fokus", "plugga", "studera", "meditera" ]):
         return 3
    
        if any(word in prompt for word in [
        "glad", "happy", "fest", "dans", "sommar", "sol", "solen",
        "njuta", "vår", "party", "kul" ]):
         return 1

        if any(word in prompt for word in [
        "techno", "house", "edm", "klubb", "rave"]):
         return 4

        if any(word in prompt for word in [
        "träning", "gym", "springa", "pepp", "tagga"]):
         return 0
    
         return 2

    
    def _apply_kmeans_subfilters(self, dataframe: pd.DataFrame, prompt: str) -> pd.DataFrame:
        prompt = prompt.lower()
        filtered = dataframe.copy()
    
        if any(word in prompt for word in ["glad", "happy", "sol", "sommar", "fest", "dans", "njuta"]):
            filtered = filtered[
                (filtered["danceability"] >= 0.50) &
                (filtered["energy"] >= 0.55) &
                (filtered["valence"] >= 0.60)
            ]

        if any(word in prompt for word in ["klubb", "rave", "techno", "house"]):
            filtered = filtered[
                (filtered["danceability"] >= 0.65) &
                (filtered["energy"] >= 0.70) &
                (filtered["tempo"] >= 115)
            ]

        if any(word in prompt for word in ["träning", "gym", "springa", "pepp", "tagga"]):
            filtered = filtered[
                (filtered["energy"] >= 0.70) &
                (filtered["tempo"] >= 110)
            ]

        if any(word in prompt for word in ["bil", "bilresa", "köra"]):
            filtered = filtered[
                (filtered["energy"] >= 0.35) &
                (filtered["tempo"] >= 90)
            ]

        if any(phrase in prompt for phrase in ["chill", "lugn", "kväll", "mys", "fokus"]):
            filtered = filtered[
            (filtered["valence"] >= 0.30) &
            (filtered["energy"] <= 0.50) &
            (filtered["acousticness"] >= 0.40)]

        if any(word in prompt for word in ["ledsen", "deppig", "sorglig", "indie", "regn"]):
            filtered = filtered[
                (filtered["valence"] <= 0.25) &
                (filtered["energy"] <= 0.45)
            ]

        if any(word in prompt for word in ["ambient", "instrumental", "piano", "bakgrund"]):
            filtered = filtered[
                (filtered["instrumentalness"] >= 0.60) &
                (filtered["energy"] <= 0.40)
    ]

        return filtered
    
    def kmeans_recommendations(self, prompt: str, limit: int = 6) -> Dict[str, Any]:
        cluster = self._prompt_to_cluster(prompt)

        profile = self.cluster_profiles.loc[cluster].to_dict()
        user_df = pd.DataFrame([profile])[self.feature_cols]
        user_scaled = self.scaler.transform(user_df)

        cluster_df = self.ml_df[self.ml_df["kmeans_cluster"] == cluster].copy()

        subfiltered = self._apply_kmeans_subfilters(cluster_df, prompt)
        if not subfiltered.empty:
            cluster_df = subfiltered

        if cluster_df.empty:
            return {
            "view": "kmeans",
            "query_label": prompt,
            "cluster": cluster,
            "cluster_name": self.cluster_names[cluster],
            "results": [],
        }

        song_vectors = self.scaler.transform(cluster_df[self.feature_cols])
        distances = euclidean_distances(user_scaled, song_vectors)[0]

        cluster_df["distance"] = distances

        cluster_df = cluster_df.drop_duplicates(
            subset=["artist_key"],
            keep="first"
        )

        cluster_df = cluster_df.sort_values("distance", ascending=True)

        candidate_pool = cluster_df.head(100).copy()

        if len(candidate_pool) > limit:
            candidate_pool = candidate_pool.sample(n=limit, random_state=None)
         
         
        results = []

        for _, row in candidate_pool.iterrows():
            results.append({
            "artist_key": row.get("artist_key"),
            "artist": row.get("primary_artist"),
            "song": row.get("track_name"),
            "genre": row.get("track_genre"),
            "cluster": int(row["kmeans_cluster"]),
            "cluster_name": self.cluster_names[int(row["kmeans_cluster"])],
            "reason": (
                f"KMeans cluster {int(row['kmeans_cluster'])} "
                f"({self.cluster_names[int(row['kmeans_cluster'])]}) • "
                f"distance {row['distance']:.2f}"
            ),
            "source": "kmeans",
            "is_custom": False,
        })

        return {
        "view": "kmeans",
        "query_label": prompt,
        "cluster": cluster,
        "cluster_name": self.cluster_names[cluster],
        "results": results,
        "saved_artist_keys": self.store.saved_artist_keys(),
    }


    def feed_payload(self, exclude_artist_keys: Sequence[str]) -> Dict[str, Any]:
        state = self.store.snapshot()
        exclude = set(exclude_artist_keys)
        library_items = self._combined_library_items(state)

        if library_items and len(exclude) % 2 == 1:
            for item in library_items:
                if item.get("artist_key") not in exclude:
                    card = self._card_from_library_item(item, "Från ditt bibliotek")
                    return {
                        "card": card,
                        "community_posts": state.get("community_posts", []),
                        "saved_artist_keys": self.store.saved_artist_keys(),
                    }

        context = self._build_library_context(state)
        preferred_labels = self._preferred_labels_from_genres(context.preferred_genres)
        base_df = self.dataset.rows_for_genres(preferred_labels)
        if base_df.empty:
            base_df = self.dataset.df.copy()
        if len(base_df) > 12000:
            base_df = base_df.sample(12000, random_state=len(exclude) + 17)

        request = {
            "genres": preferred_labels,
            "tokens": [],
            "mood_targets": context.avg_vector,
            "year_filter": None,
            "source_label": "Vald för ditt flöde",
        }
        scored = self._score_rows(base_df, request, context)
        results = self._assemble_results(scored, request, context, limit=12)
        for result in results:
            if result.get("artist_key") not in exclude:
                return {
                    "card": result,
                    "community_posts": state.get("community_posts", []),
                    "saved_artist_keys": self.store.saved_artist_keys(),
                }

        fallback = library_items[0] if library_items else None
        return {
            "card": self._card_from_library_item(fallback, "Från ditt bibliotek") if fallback else {},
            "community_posts": state.get("community_posts", []),
            "saved_artist_keys": self.store.saved_artist_keys(),
        }

    def profile_payload(self) -> Dict[str, Any]:
        state = self.store.snapshot()
        saved_items = state.get("saved_artists", [])
        custom_items = state.get("custom_artists", [])
        return {
            "saved_artists": saved_items,
            "custom_artists": custom_items,
            "saved_count": len(saved_items),
            "custom_count": len(custom_items),
            "small_artist_definition": self.small_artist_definition(),
        }

    def add_custom_artist(self, isrc: str, note: str = "") -> Dict[str, Any]:
        track = self.apis.lookup_track_by_isrc(isrc)
        if not track:
            raise ValueError("Vi kunde inte hitta någon låt via Deezer för den ISRC-koden.")

        artist_name = track.get("artist") or "Okänd artist"
        artist_key = normalize_key(artist_name)
        local = self.dataset.artist_record(artist_key)
        profile = self._profile_artist(artist_name, local)

        item = {
            "artist_key": artist_key,
            "artist": artist_name,
            "song": track.get("song"),
            "genre": ", ".join(profile.get("top_genres", [])[:2]),
            "image": track.get("image") or profile.get("image"),
            "preview": track.get("preview") or profile.get("preview"),
            "deezer_link": track.get("deezer_link") or profile.get("deezer_link"),
            "lastfm_link": profile.get("lastfm_link"),
            "reason": "Egen inlagd mindre artist via ISRC-kod.",
            "top_genres": profile.get("top_genres", []),
            "similar_artists": profile.get("similar_artists", []),
            "metrics": profile.get("metrics", {}),
            "audio_signature": profile.get("audio_signature", {}),
            "source": "suggest",
            "is_custom": True,
            "note": note,
            "isrc": track.get("isrc"),
            "added_at": utc_now_iso(),
        }

        self.store.add_custom_artist(item)
        self.store.upsert_saved_artist(item)
        self.store.add_community_post(
            {
                "username": "du",
                "text": "Delade en ny mindre artist till community-flödet.",
                "tip_artist": artist_name,
                "tip_song": track.get("song"),
                "artist_key": artist_key,
            }
        )
        return item

    def toggle_saved_artist(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        artist_key = normalize_key(payload.get("artist_key") or payload.get("artist"))
        current_keys = set(self.store.saved_artist_keys())

        if artist_key in current_keys:
            self.store.remove_saved_artist(artist_key)
            return {"saved": False, "artist_key": artist_key}

        item = dict(payload)
        item["artist_key"] = artist_key
        item["saved_at"] = utc_now_iso()
        stored = self.store.upsert_saved_artist(item)
        return {"saved": True, "artist_key": artist_key, "item": stored}

    def remove_artist(self, artist_key: str) -> None:
        self.store.remove_artist_everywhere(normalize_key(artist_key))

    def add_community_post(self, text: str, username: str, tip_artist: str | None, tip_song: str | None) -> Dict[str, Any]:
        artist_key = normalize_key(tip_artist) if tip_artist else ""
        return self.store.add_community_post(
            {
                "username": username or "du",
                "text": text,
                "tip_artist": tip_artist,
                "tip_song": tip_song,
                "artist_key": artist_key or None,
            }
        )

    def _interpret_prompt(self, prompt: str) -> Dict[str, Any]:
        normalized_prompt = normalize_key(prompt)
        joined_prompt = normalized_prompt.replace(" ", "")

        genres = []
        for keyword, label in PROMPT_GENRE_HINTS.items():
            if keyword in joined_prompt or keyword in normalized_prompt:
                genres.append(label)

        mood_targets: Dict[str, float] = {}
        for keyword, values in PROMPT_MOODS.items():
            if keyword in normalized_prompt:
                mood_targets.update(values)

        tokens = [
            token
            for token in re.findall(r"[a-zA-Z0-9åäöÅÄÖ-]{3,}", prompt.lower())
            if normalize_key(token) not in STOPWORDS
        ]

        return {
            "genres": list(dict.fromkeys(genres)),
            "tokens": tokens,
            "mood_targets": mood_targets,
            "year_filter": self._parse_year_filter(prompt),
            "source_label": "Matchad mot din prompt",
        }

    def _parse_year_filter(self, prompt: str) -> Dict[str, int] | None:
        exact_match = re.search(r"\b(19|20)\d{2}\b", prompt)
        if exact_match:
            year = int(exact_match.group(0))
            return {"from": year, "to": year}

        decade_match = re.search(r"\b(80|90|00|10|20)-?(?:talet|s)\b", normalize_key(prompt))
        if not decade_match:
            return None

        value = decade_match.group(1)
        if value == "00":
            return {"from": 2000, "to": 2009}
        if value == "10":
            return {"from": 2010, "to": 2019}
        if value == "20":
            return {"from": 2020, "to": 2029}
        return {"from": int(f"19{value}"), "to": int(f"19{value}") + 9}

    def _build_library_context(self, state: Dict[str, Any] | None = None) -> LibraryContext:
        state = state or self.store.snapshot()
        items = self._combined_library_items(state)

        preferred_genres = Counter()
        similar_artist_keys: set[str] = set()
        vectors: List[Dict[str, float]] = []
        seed_names: List[str] = []

        for item in items:
            seed_names.append(item.get("artist", ""))
            preferred_genres.update(item.get("top_genres", []))
            similar_artist_keys.update(normalize_key(name) for name in item.get("similar_artists", []))
            audio_signature = item.get("audio_signature", {})
            if audio_signature:
                vectors.append(audio_signature)

        avg_vector = self._average_vectors(vectors)
        return LibraryContext(
            seed_names=[name for name in seed_names if name][:6],
            preferred_genres=[genre for genre, _ in preferred_genres.most_common(5)],
            similar_artist_keys=similar_artist_keys,
            avg_vector=avg_vector,
        )

    def _score_rows(self, df: pd.DataFrame, request: Dict[str, Any], context: LibraryContext) -> pd.DataFrame:
        if df.empty:
            return df.copy()

        working = df.copy()
        score = pd.Series(0.0, index=working.index)

        selected_genres = self.dataset.map_genre_labels(request.get("genres", []))
        if selected_genres:
            score += working["track_genre"].isin(selected_genres).astype(float) * 2.4

        if context.preferred_genres:
            score += working["track_genre"].isin(context.preferred_genres).astype(float) * 0.7

        if context.similar_artist_keys:
            score += working["artist_key"].isin(context.similar_artist_keys).astype(float) * 1.1

        blob = working["search_blob"].fillna("")
        for token in request.get("tokens", [])[:8]:
            score += blob.str.contains(token, regex=False).astype(float) * 0.55

        mood_targets = request.get("mood_targets", {})
        for feature, target in mood_targets.items():
            if feature in working.columns:
                distance = (working[feature].fillna(target) - target).abs().clip(0, 1)
                score += (1 - distance) * 0.95

        for feature, target in context.avg_vector.items():
            if feature in working.columns:
                distance = (working[feature].fillna(target) - target).abs().clip(0, 1)
                score += (1 - distance) * 0.30

        score += (1 - working["popularity"].fillna(50).clip(0, 100) / 100.0) * 1.35
        working["match_score"] = score
        return working.sort_values(["match_score", "popularity"], ascending=[False, True]).reset_index(drop=True)

    def _assemble_results(
        self,
        scored_df: pd.DataFrame,
        request: Dict[str, Any],
        context: LibraryContext,
        limit: int,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        seen_artist_keys: set[str] = set()

        for _, row in scored_df.head(140).iterrows():
            artist_key = row.get("artist_key", "")
            if not artist_key or artist_key in seen_artist_keys:
                continue

            local = self.dataset.artist_record(artist_key)
            profile = self._profile_artist(row.get("primary_artist", ""), local)

            if not profile.get("is_small"):
                continue
            if not self._release_year_matches(profile.get("release_year"), request.get("year_filter")):
                continue

            results.append(self._build_card(row.to_dict(), profile, request, context))
            seen_artist_keys.add(artist_key)

            if len(results) >= limit:
                return results

        if results:
            return results

        # Fallback: do not fail completely if APIs are unavailable.
        for _, row in scored_df.head(50).iterrows():
            artist_key = row.get("artist_key", "")
            if not artist_key or artist_key in seen_artist_keys:
                continue
            local = self.dataset.artist_record(artist_key)
            if not local or local.get("avg_popularity", 100) > self.settings.max_local_popularity + 5:
                continue
            profile = self._profile_artist(row.get("primary_artist", ""), local, allow_local_only=True)
            results.append(self._build_card(row.to_dict(), profile, request, context))
            seen_artist_keys.add(artist_key)
            if len(results) >= limit:
                break

        return results

    def _profile_artist(
        self,
        artist_name: str,
        local: Dict[str, Any] | None = None,
        allow_local_only: bool = False,
    ) -> Dict[str, Any]:
        local = local or self.dataset.artist_record(normalize_key(artist_name))
        lastfm = self.apis.get_lastfm_artist(artist_name)
        deezer = self.apis.get_deezer_artist(artist_name)

        assessment = self._assess_small_artist(local, lastfm, deezer, allow_local_only=allow_local_only)
        audio_signature = {
            feature: float(local.get(f"avg_{feature}", 0))
            for feature in FEATURE_COLUMNS
            if local and local.get(f"avg_{feature}") is not None
        }

        return {
            "artist": local.get("primary_artist") if local else artist_name,
            "top_genres": list(local.get("top_genres", [])) if local else [],
            "image": deezer.get("image"),
            "preview": deezer.get("preview"),
            "deezer_link": deezer.get("link"),
            "lastfm_link": lastfm.get("url"),
            "release_year": self._extract_year(deezer.get("release_date")),
            "bio": lastfm.get("bio", ""),
            "similar_artists": lastfm.get("similar_artists", []),
            "metrics": assessment["metrics"],
            "is_small": assessment["is_small"],
            "smallness_reason": assessment["reason"],
            "audio_signature": audio_signature,
        }

    def _assess_small_artist(
        self,
        local: Dict[str, Any],
        lastfm: Dict[str, Any],
        deezer: Dict[str, Any],
        allow_local_only: bool = False,
    ) -> Dict[str, Any]:
        metrics = {
            "spotify_popularity": local.get("avg_popularity") if local else None,
            "spotify_tracks": local.get("track_count") if local else None,
            "lastfm_listeners": lastfm.get("listeners"),
            "deezer_fans": deezer.get("fans"),
        }

        checks = []
        if metrics["spotify_popularity"] is not None:
            checks.append(("Spotify-popularitet", metrics["spotify_popularity"] <= self.settings.max_local_popularity))
        if metrics["lastfm_listeners"] is not None:
            checks.append(("Last.fm-lyssnare", metrics["lastfm_listeners"] <= self.settings.max_lastfm_listeners))
        if metrics["deezer_fans"] is not None:
            checks.append(("Deezer-fans", metrics["deezer_fans"] <= self.settings.max_deezer_fans))

        passed = [label for label, is_ok in checks if is_ok]
        local_only_pass = (
            metrics["spotify_popularity"] is not None
            and metrics["spotify_popularity"] <= self.settings.max_local_popularity - 8
        )

        is_small = len(passed) >= 2 or (len(checks) == 1 and len(passed) == 1)
        if allow_local_only and not is_small:
            is_small = local_only_pass
        if not checks and local_only_pass:
            is_small = True

        if passed:
            reason = "Liten synlighet enligt " + ", ".join(passed[:3]).lower() + "."
        elif local_only_pass:
            reason = "Datasetet visar låg genomsnittlig popularitet pa Spotify."
        else:
            reason = "Den här artisten är närmare mainstream än målet för appen."

        return {"metrics": metrics, "is_small": is_small, "reason": reason}

    def _build_card(
        self,
        row: Dict[str, Any],
        profile: Dict[str, Any],
        request: Dict[str, Any],
        context: LibraryContext,
    ) -> Dict[str, Any]:
        similar_hint = ""
        if context.seed_names and normalize_key(row.get("primary_artist")) in context.similar_artist_keys:
            similar_hint = f" Påminner också om ditt bibliotek via Last.fm-liknande artister."

        secondary_tracks = self.dataset.rows_for_artist_key(row["artist_key"]).sort_values(
            "popularity", ascending=False
        )["track_name"].head(3).tolist()
        secondary_tracks = [track for track in secondary_tracks if track and track != row.get("track_name")]

        return {
            "artist_key": row.get("artist_key"),
            "artist": row.get("primary_artist"),
            "song": row.get("track_name"),
            "secondary_tracks": secondary_tracks[:2],
            "genre": row.get("track_genre"),
            "album": row.get("album_name"),
            "reason": f"{request.get('source_label', 'Matchad rekommendation')}. {profile.get('smallness_reason', '')}{similar_hint}",
            "bio": profile.get("bio", ""),
            "image": profile.get("image"),
            "preview": profile.get("preview"),
            "deezer_link": profile.get("deezer_link"),
            "lastfm_link": profile.get("lastfm_link"),
            "metrics": profile.get("metrics", {}),
            "top_genres": profile.get("top_genres", []),
            "similar_artists": profile.get("similar_artists", []),
            "audio_signature": profile.get("audio_signature", {}),
            "source": "recommendation",
            "is_custom": False,
        }

    def _card_from_library_item(self, item: Dict[str, Any] | None, fallback_reason: str) -> Dict[str, Any]:
        if not item:
            return {}
        payload = dict(item)
        payload.setdefault("reason", fallback_reason)
        payload.setdefault("source", "library")
        return payload

    def _combined_library_items(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        seen = set()
        merged: List[Dict[str, Any]] = []
        for bucket in ("custom_artists", "saved_artists"):
            for item in state.get(bucket, []):
                key = item.get("artist_key")
                if key and key not in seen:
                    merged.append(item)
                    seen.add(key)
        return merged

    def _average_vectors(self, vectors: Iterable[Dict[str, float]]) -> Dict[str, float]:
        totals: Dict[str, float] = {}
        counts: Dict[str, int] = {}
        for vector in vectors:
            for key, value in vector.items():
                totals[key] = totals.get(key, 0.0) + float(value)
                counts[key] = counts.get(key, 0) + 1
        return {key: totals[key] / counts[key] for key in totals if counts[key]}

    def _preferred_labels_from_genres(self, genres: Sequence[str]) -> List[str]:
        labels = []
        for label, values in DISCOVER_GENRES.items():
            if any(value in values for value in genres):
                labels.append(label)
        return labels

    def _extract_year(self, value: str | None) -> int | None:
        if not value:
            return None
        match = re.match(r"(\d{4})", value)
        return int(match.group(1)) if match else None

    def _release_year_matches(self, release_year: int | None, year_filter: Dict[str, int] | None) -> bool:
        if not year_filter or not release_year:
            return True
        return year_filter["from"] <= release_year <= year_filter["to"]