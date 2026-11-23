from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

data_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "spotify_tracks.csv"
)

df = pd.read_csv(data_path)

# Städning
df["track_genre"] = df["track_genre"].astype(str).str.strip().str.lower()
df["artists"] = df["artists"].astype(str).str.strip()
df["track_name"] = df["track_name"].astype(str).str.strip()
df["popularity"] = pd.to_numeric(df["popularity"], errors="coerce")
df["valence"] = pd.to_numeric(df["valence"], errors="coerce")
df["energy"] = pd.to_numeric(df["energy"], errors="coerce")

df = df.dropna(subset=["artists", "track_name", "track_genre", "popularity", "valence", "energy"])

# Ta första artisten om flera finns i samma fält
df["primary_artist"] = df["artists"].apply(lambda x: x.split(";")[0].strip().lower())

# Artistnivå-statistik
artist_stats = (
    df.groupby("primary_artist")
    .agg(
        avg_popularity=("popularity", "mean"),
        max_popularity=("popularity", "max"),
        track_count=("track_name", "count")
    )
    .reset_index()
)

# Smallweb-filter
small_artist_pool = artist_stats[
    (artist_stats["avg_popularity"] < 15) &
    (artist_stats["max_popularity"] < 25) &
    (artist_stats["track_count"] <= 8)
]


def apply_smallweb_filter(dataframe):
    return dataframe[dataframe["primary_artist"].isin(small_artist_pool["primary_artist"])]


def apply_mood_filter(dataframe, mood):
    mood = mood.lower().strip()

    if mood == "melankolisk":
        return dataframe[dataframe["valence"] < 0.40]
    elif mood == "glad":
        return dataframe[dataframe["valence"] > 0.60]
    elif mood == "lugn":
        return dataframe[dataframe["energy"] < 0.45]

    return dataframe


def attach_artist_stats(dataframe):
    return dataframe.merge(
        small_artist_pool,
        on="primary_artist",
        how="left"
    )


def build_results(dataframe, extra_reason=""):
    dataframe = dataframe.drop_duplicates(subset=["primary_artist"])

    dataframe = dataframe.sort_values(
        by=["max_popularity", "avg_popularity", "track_count", "popularity"],
        ascending=[True, True, True, True]
    )

    candidate_pool = dataframe.head(20).copy()

    if len(candidate_pool) > 6:
        candidate_pool = candidate_pool.sample(n=6)

    results = []

    for _, row in candidate_pool.iterrows():
        reason_text = (
            f"{row['track_genre']} • "
            f"avg popularity {row['avg_popularity']:.1f} • "
            f"max popularity {int(row['max_popularity'])}"
        )

        if extra_reason:
            reason_text = f"{extra_reason} • " + reason_text

        results.append({
            "artist": row["artists"],
            "song": row["track_name"],
            "reason": reason_text
        })

    return results


@app.get("/artists")
def get_artists(
    genre: str = Query(default="indie"),
    mood: str = Query(default="melankolisk"),
    artist_input: str = Query(default="")
):
    filtered = df.copy()

    genre = genre.lower().strip()
    mood = mood.lower().strip()
    artist_input = artist_input.lower().strip()

    # Genre
    filtered = filtered[filtered["track_genre"] == genre]

    # Smallweb
    filtered = apply_smallweb_filter(filtered)

    # Mood
    filtered = apply_mood_filter(filtered, mood)

    # Artist-input påverkar sorteringen lite
    if artist_input:
        same_artist_rows = df[df["artists"].str.lower().str.contains(artist_input, na=False)]

        if not same_artist_rows.empty:
            target_valence = same_artist_rows["valence"].mean()
            target_energy = same_artist_rows["energy"].mean()

            filtered["distance"] = (
                (filtered["valence"] - target_valence).abs() +
                (filtered["energy"] - target_energy).abs()
            )

            filtered = filtered.sort_values(by="distance", ascending=True)

    filtered = attach_artist_stats(filtered)

    return build_results(filtered)


def interpret_prompt(prompt: str):
    prompt = prompt.lower()

    genre = None
    mood = None
    min_energy = None
    max_energy = None
    min_valence = None
    max_valence = None

    # Genre
    if "house" in prompt:
        genre = "house"
    elif "indie" in prompt:
        genre = "indie"
    elif "rock" in prompt:
        genre = "rock"
    elif "pop" in prompt:
        genre = "pop"
    elif "techno" in prompt:
        genre = "techno"
    elif "ambient" in prompt:
        genre = "ambient"
    elif "chill" in prompt:
        genre = "chill"

    # Mood / situation
    if "bilresa" in prompt or "roadtrip" in prompt or "car" in prompt:
        min_energy = 0.55
        min_valence = 0.45

    if "fest" in prompt or "party" in prompt or "dans" in prompt:
        min_energy = 0.70
        min_valence = 0.60

    if "lugn" in prompt or "chill" in prompt or "kväll" in prompt:
        mood = "lugn"
        max_energy = 0.45

    if "melankolisk" in prompt or "sad" in prompt or "ledsen" in prompt:
        mood = "melankolisk"
        max_valence = 0.40

    if "glad" in prompt or "happy" in prompt:
        mood = "glad"
        min_valence = 0.65

    return {
        "genre": genre,
        "mood": mood,
        "min_energy": min_energy,
        "max_energy": max_energy,
        "min_valence": min_valence,
        "max_valence": max_valence
    }


@app.get("/prompt-artists")
def get_prompt_artists(prompt: str = Query(default="")):
    filtered = df.copy()
    rules = interpret_prompt(prompt)

    # Smallweb först
    filtered = apply_smallweb_filter(filtered)

    # Genre
    if rules["genre"]:
        filtered = filtered[filtered["track_genre"] == rules["genre"]]

    # Mood
    if rules["mood"]:
        filtered = apply_mood_filter(filtered, rules["mood"])

    # Extra promptregler
    if rules["min_energy"] is not None:
        filtered = filtered[filtered["energy"] >= rules["min_energy"]]

    if rules["max_energy"] is not None:
        filtered = filtered[filtered["energy"] <= rules["max_energy"]]

    if rules["min_valence"] is not None:
        filtered = filtered[filtered["valence"] >= rules["min_valence"]]

    if rules["max_valence"] is not None:
        filtered = filtered[filtered["valence"] <= rules["max_valence"]]

    filtered = attach_artist_stats(filtered)

    return build_results(filtered, extra_reason=f"matchade prompten '{prompt}'")
    