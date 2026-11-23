from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import euclidean_distances
from sklearn.preprocessing import StandardScaler

from .config import Settings
from .dataset import DISCOVER_GENRES, FEATURE_COLUMNS, PROMPT_SUGGESTIONS, DatasetCatalog, normalize_key
from .external_services import MusicApis
from .storage import JsonStore, utc_now_iso


CONTROLLED_OPTIONS = {
    "moods": ["glad", "ledsen", "chill", "arg", "romantisk"],
    "genres": ["pop", "rock", "indie", "jazz", "electronic", "house", "techno", "r&b", "hip-hop", "classical"],
    "occasions": ["plugga", "träna", "fest", "sova", "bilresa", "fokus", "kväll", "dejt"],
}



CLUSTER_RULES = {
    "glad": 1,
    "romantisk": 1,
    "ledsen": 2,
    "chill": 2,
    "arg": 0,
    "plugga": 3,
    "fokus": 3,
    "sova": 3,
    "kväll": 2,
    "fest": 1,
    "träna": 0,
    "bilresa": 0,
    "dejt": 1,
}


TARGETS = {
    "glad": {"energy": 0.75, "danceability": 0.70, "valence": 0.80},
    "ledsen": {"energy": 0.35, "valence": 0.20, "acousticness": 0.55},
    "chill": {"energy": 0.30, "danceability": 0.45, "acousticness": 0.60, "valence": 0.45},
    "arg": {"energy": 0.90, "loudness": -4.5, "valence": 0.18, "danceability": 0.60, "tempo": 128,},
    "romantisk": {"energy": 0.45, "danceability": 0.50, "valence": 0.65, "acousticness": 0.45},
    "plugga": {"energy": 0.25, "instrumentalness": 0.45, "acousticness": 0.60},
    "fokus": {"energy": 0.25, "instrumentalness": 0.50, "acousticness": 0.55},
    "träna": {"energy": 0.85, "danceability": 0.75, "tempo": 130, "valence": 0.70},
    "fest": {"energy": 0.80, "danceability": 0.80, "tempo": 125, "valence": 0.75},
    "sova": {"energy": 0.15, "instrumentalness": 0.65, "acousticness": 0.75, "valence": 0.30},
    "bilresa": {"energy": 0.62, "danceability": 0.62, "tempo": 105, "valence": 0.55},
    "kväll": {"energy": 0.35, "acousticness": 0.55, "valence": 0.40},
    "dejt": {"energy": 0.45, "danceability": 0.60, "valence": 0.70, "acousticness": 0.35, "tempo": 105,
},

}


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

        self.feature_cols = [
            "danceability",
            "energy",
            "loudness",
            "tempo",
            "instrumentalness",
            "acousticness",
            "valence",
        ]

        self.cluster_names = {
            0: "energetic_workout_driving",
            1: "happy_party_pop",
            2: "chill_sad_acoustic",
            3: "ambient_focus_sleep",
            4: "electronic_techno_instrumental",
        }

        self.ml_df = self.dataset.df.copy()


        for col in self.feature_cols:
            self.ml_df[col] = pd.to_numeric(self.ml_df[col], errors="coerce")

        self.ml_df = self.ml_df.dropna(subset=self.feature_cols)

        self.scaler = StandardScaler()
        x_scaled = self.scaler.fit_transform(self.ml_df[self.feature_cols])

        self.kmeans = KMeans(n_clusters=5, random_state=42, n_init=10)
        self.ml_df["kmeans_cluster"] = self.kmeans.fit_predict(x_scaled)

        self.cluster_profiles = self.ml_df.groupby("kmeans_cluster")[self.feature_cols].mean()

        print("\n=== KMEANS CLUSTER MEAN VALUES ===")
        print(self.cluster_profiles.round(3))

    def bootstrap_payload(self) -> Dict[str, Any]:
        summary = self.dataset.summary()
        state = self.store.snapshot()

        return {
            "genres": self.dataset.discover_genres(),
            "prompt_suggestions": PROMPT_SUGGESTIONS,
            "controlled_options": CONTROLLED_OPTIONS,
            "small_artist_definition": self.small_artist_definition(),
            "cluster_profiles": self.cluster_profiles.round(3).to_dict(orient="index"),
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

    def controlled_kmeans_recommendations(
        self,
        mood: str | None = None,
        genre: str | None = None,
        occasion: str | None = None,
        limit: int = 6,
    ) -> Dict[str, Any]:
        selected = [mood, genre, occasion]
        selected = [normalize_key(value) for value in selected if value]

        cluster = self._select_cluster(selected)
        targets = self._build_target_vector(selected, cluster)

        base_df = self._filter_by_genre(self.ml_df.copy(), genre)

        cluster_df = base_df.copy()

        

        return self._rank_kmeans_results(
            dataframe=cluster_df,
            cluster=cluster,
            target_vector=targets,
            limit=limit,
            query_label=" • ".join(selected) if selected else "KMeans rekommendation",
            filters={
                "mood": mood,
                "genre": genre,
                "occasion": occasion,
                "selected_cluster": cluster,
                "cluster_name": self.cluster_names.get(cluster),
                "target_vector": targets,
            },
        )

    def kmeans_recommendations(self, prompt: str, limit: int = 6) -> Dict[str, Any]:
        selected = self._prompt_to_controlled_values(prompt)
        mood = selected.get("mood")
        genre = selected.get("genre")
        occasion = selected.get("occasion")

        return self.controlled_kmeans_recommendations(
            mood=mood,
            genre=genre,
            occasion=occasion,
            limit=limit,
        )

    def prompt_search(self, prompt: str, limit: int) -> Dict[str, Any]:
        return self.kmeans_recommendations(prompt, limit)

    def discover_artists(self, genres: Sequence[str], limit: int) -> Dict[str, Any]:
        genre = genres[0] if genres else None
        return self.controlled_kmeans_recommendations(
            mood=None,
            genre=genre,
            occasion=None,
            limit=limit,
        )

    def feed_payload(self, exclude_artist_keys: Sequence[str]) -> Dict[str, Any]:
        state = self.store.snapshot()
        exclude = set(exclude_artist_keys)

        library_items = self._combined_library_items(state)
        for item in library_items:
            if item.get("artist_key") not in exclude:
                return {
                    "card": self._card_from_library_item(item, "Från ditt bibliotek"),
                    "community_posts": state.get("community_posts", []),
                    "saved_artist_keys": self.store.saved_artist_keys(),
                }

        results = self.controlled_kmeans_recommendations(mood="chill", limit=12).get("results", [])
        for result in results:
            if result.get("artist_key") not in exclude:
                return {
                    "card": result,
                    "community_posts": state.get("community_posts", []),
                    "saved_artist_keys": self.store.saved_artist_keys(),
                }

        return {
            "card": results[0] if results else {},
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

    def add_community_post(
        self,
        text: str,
        username: str,
        tip_artist: str | None,
        tip_song: str | None,
    ) -> Dict[str, Any]:
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

    def _select_cluster(self, selected: List[str]) -> int:
        votes = []

        for value in selected:
            if value in CLUSTER_RULES:
                votes.append(CLUSTER_RULES[value])

        if not votes:
            return 2

        return max(set(votes), key=votes.count)

    def _build_target_vector(self, selected: List[str], cluster: int) -> Dict[str, float]:
        base_target = self.cluster_profiles.loc[cluster].to_dict()

        feature_values: Dict[str, List[float]] = {
        feature: [float(base_target[feature])]
        for feature in self.feature_cols
        }

        for value in selected:
            if value in TARGETS:
                for feature, target_value in TARGETS[value].items():
                    if feature in feature_values:
                        feature_values[feature].append(float(target_value))

        averaged_target = {
            feature: sum(values) / len(values)
            for feature, values in feature_values.items()
            }

        return averaged_target


    def _filter_by_genre(self, dataframe: pd.DataFrame, genre: str | None) -> pd.DataFrame:
        if dataframe.empty or not genre:
            return dataframe

        genre_key = normalize_key(genre)

        genre_filtered = dataframe[
            dataframe["track_genre"]
            .fillna("")
            .apply(
                lambda value: genre_key in normalize_key(str(value))
            )
        ]

        return genre_filtered


    def _rank_kmeans_results(
        self,
        dataframe: pd.DataFrame,
        cluster: int,
        target_vector: Dict[str, float],
        limit: int,
        query_label: str,
        filters: Dict[str, Any],
    ) -> Dict[str, Any]:
        if dataframe.empty:
            return {
                "view": "kmeans",
                "query_label": query_label,
                "cluster": cluster,
                "cluster_name": self.cluster_names.get(cluster),
                "filters": filters,
                "results": [],
                "saved_artist_keys": self.store.saved_artist_keys(),
            }

        user_df = pd.DataFrame([target_vector])[self.feature_cols]
        user_scaled = self.scaler.transform(user_df)

        song_vectors = self.scaler.transform(dataframe[self.feature_cols])
        distances = euclidean_distances(user_scaled, song_vectors)[0]

        ranked = dataframe.copy()
        ranked["distance"] = distances

        if "popularity" in ranked.columns:
            ranked = ranked.sort_values(["distance", "popularity"], ascending=[True, True])
        else:
            ranked = ranked.sort_values("distance", ascending=True)

        ranked = ranked.drop_duplicates(subset=["artist_key"], keep="first")

        results = []
        seen_artist_keys: set[str] = set()

        candidate_pool = ranked.head(80).sample(
           n=min(len(ranked.head(80)), 40))

        for _, row in candidate_pool.iterrows():
            artist_key = row.get("artist_key")
            
            if not artist_key or artist_key in seen_artist_keys:
                  continue

            local = self.dataset.artist_record(artist_key)
            profile = self._profile_artist(row.get("primary_artist", ""), local, allow_local_only=True)

            if not profile.get("is_small"):
                continue

            results.append(self._build_kmeans_card(row.to_dict(), profile))
            seen_artist_keys.add(artist_key)

            if len(results) >= limit:
                break

        if not results:
            for _, row in ranked.head(limit).iterrows():
                local = self.dataset.artist_record(row.get("artist_key", ""))
                profile = self._profile_artist(row.get("primary_artist", ""), local, allow_local_only=True)
                results.append(self._build_kmeans_card(row.to_dict(), profile))

        return {
            "view": "kmeans",
            "query_label": query_label,
            "cluster": cluster,
            "cluster_name": self.cluster_names.get(cluster),
            "filters": filters,
            "results": results[:limit],
            "saved_artist_keys": self.store.saved_artist_keys(),
        }

    def _build_kmeans_card(self, row: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        artist_key = row.get("artist_key")

        secondary_tracks = []
        if artist_key:
            secondary_tracks = (
                self.dataset.rows_for_artist_key(artist_key)
                .sort_values("popularity", ascending=False)["track_name"]
                .head(3)
                .tolist()
            )

        secondary_tracks = [
            track for track in secondary_tracks
            if track and track != row.get("track_name")
        ]

        cluster = int(row.get("kmeans_cluster", -1))

        return {
            "artist_key": artist_key,
            "artist": row.get("primary_artist"),
            "song": row.get("track_name"),
            "secondary_tracks": secondary_tracks[:2],
            "genre": row.get("track_genre"),
            "album": row.get("album_name"),
            "reason": (
                f"KMeans matchade låten till cluster {cluster} "
                f"({self.cluster_names.get(cluster, 'okänt cluster')}). "
                f"Avstånd till vald musikprofil: {row.get('distance', 0):.2f}. "
                f"{profile.get('smallness_reason', '')}"
            ),
            "bio": profile.get("bio", ""),
            "image": profile.get("image"),
            "preview": profile.get("preview"),
            "deezer_link": profile.get("deezer_link"),
            "lastfm_link": profile.get("lastfm_link"),
            "metrics": profile.get("metrics", {}),
            "top_genres": profile.get("top_genres", []),
            "similar_artists": profile.get("similar_artists", []),
            "audio_signature": profile.get("audio_signature", {}),
            "cluster": cluster,
            "cluster_name": self.cluster_names.get(cluster),
            "distance": float(row.get("distance", 0)),
            "source": "kmeans",
            "is_custom": False,
        }

    def _prompt_to_controlled_values(self, prompt: str) -> Dict[str, str | None]:
        normalized = normalize_key(prompt)

        mood = None
        genre = None
        occasion = None

        for option in CONTROLLED_OPTIONS["moods"]:
            if normalize_key(option) in normalized:
                mood = option
                break

        for option in CONTROLLED_OPTIONS["genres"]:
            if normalize_key(option) in normalized:
                genre = option
                break

        for option in CONTROLLED_OPTIONS["occasions"]:
            if normalize_key(option) in normalized:
                occasion = option
                break

        return {
            "mood": mood,
            "genre": genre,
            "occasion": occasion,
        }

    def _profile_artist(
        self,
        artist_name: str,
        local: Dict[str, Any] | None = None,
        allow_local_only: bool = False,
    ) -> Dict[str, Any]:
        local = local or self.dataset.artist_record(normalize_key(artist_name))
        lastfm = self.apis.get_lastfm_artist(artist_name)
        deezer = self.apis.get_deezer_artist(artist_name)

        assessment = self._assess_small_artist(
            local,
            lastfm,
            deezer,
            allow_local_only=allow_local_only,
        )

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
        local: Dict[str, Any] | None,
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
            checks.append(
                (
                    "Spotify-popularitet",
                    metrics["spotify_popularity"] <= self.settings.max_local_popularity,
                )
            )

        if metrics["lastfm_listeners"] is not None:
            checks.append(
                (
                    "Last.fm-lyssnare",
                    metrics["lastfm_listeners"] <= self.settings.max_lastfm_listeners,
                )
            )

        if metrics["deezer_fans"] is not None:
            checks.append(
                (
                    "Deezer-fans",
                    metrics["deezer_fans"] <= self.settings.max_deezer_fans,
                )
            )

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
            reason = "Datasetet visar låg genomsnittlig popularitet på Spotify."
        else:
            reason = "Den här artisten är närmare mainstream än målet för appen."

        return {
            "metrics": metrics,
            "is_small": is_small,
            "reason": reason,
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

    def _extract_year(self, value: str | None) -> int | None:
        if not value:
            return None

        match = re.match(r"(\d{4})", value)
        return int(match.group(1)) if match else None
    
