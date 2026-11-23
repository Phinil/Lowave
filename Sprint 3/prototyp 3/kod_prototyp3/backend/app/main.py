from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .dataset import DatasetCatalog
from .external_services import MusicApis
from .models import (
    CommunityPostRequest,
    DiscoverRequest,
    FeedRequest,
    PromptRequest,
    SaveArtistRequest,
    SuggestArtistRequest,
)
from .recommendations import RecommendationEngine
from .storage import JsonStore


settings = get_settings()


class AppContainer:
    def __init__(self) -> None:
        self.dataset = DatasetCatalog(settings.spotify_csv_path)
        self.store = JsonStore(settings.user_state_path)
        self.apis = MusicApis(settings)
        self.engine = RecommendationEngine(settings, self.dataset, self.apis, self.store)

    def close(self) -> None:
        self.apis.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = AppContainer()
    app.state.container = container
    yield
    container.close()


app = FastAPI(title="Small Web Smaller Artists App", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(settings.frontend_dir)), name="static")


def get_engine() -> RecommendationEngine:
    return app.state.container.engine


@app.get("/")
def index() -> FileResponse:
    return FileResponse(settings.frontend_dir / "index.html")


@app.get("/api/health")
def health() -> Dict[str, Any]:
    engine = get_engine()
    return {
        "status": "ok",
        "dataset": engine.bootstrap_payload()["stats"],
        "lastfm_configured": bool(settings.lastfm_api_key),
    }


@app.get("/api/bootstrap")
def bootstrap() -> Dict[str, Any]:
    return get_engine().bootstrap_payload()


@app.post("/api/discover")
def discover(payload: DiscoverRequest) -> Dict[str, Any]:
    limit = max(1, min(payload.limit, 12))
    return get_engine().discover_artists(payload.genres, limit=limit)


@app.post("/api/search")
def search(payload: PromptRequest) -> Dict[str, Any]:
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Skriv en prompt först.")
    limit = max(1, min(payload.limit, 12))
    return get_engine().prompt_search(prompt, limit=limit)


@app.post("/api/feed")
def feed(payload: FeedRequest) -> Dict[str, Any]:
    return get_engine().feed_payload(payload.exclude_artist_keys)


@app.get("/api/profile")
def profile() -> Dict[str, Any]:
    return get_engine().profile_payload()


@app.post("/api/save")
def save(payload: SaveArtistRequest) -> Dict[str, Any]:
    return get_engine().toggle_saved_artist(payload.model_dump())


@app.delete("/api/library/{artist_key}")
def delete_library_artist(artist_key: str) -> Dict[str, Any]:
    get_engine().remove_artist(artist_key)
    return {"removed": True, "artist_key": artist_key}


@app.post("/api/suggestions")
def add_suggestion(payload: SuggestArtistRequest) -> Dict[str, Any]:
    if not payload.confirm_smaller_artist:
        raise HTTPException(
            status_code=400,
            detail="Bekräfta att du vill lägga till artisten innan du skickar in.",
        )

    try:
        item = get_engine().add_custom_artist(payload.isrc, note=payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"saved": True, "item": item}


@app.post("/api/community")
def create_community_post(payload: CommunityPostRequest) -> Dict[str, Any]:
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Skriv något innan du postar.")

    item = get_engine().add_community_post(
        text=payload.text.strip(),
        username=payload.username.strip() or "du",
        tip_artist=payload.tip_artist.strip() if payload.tip_artist else None,
        tip_song=payload.tip_song.strip() if payload.tip_song else None,
    )
    return {"item": item}


@app.get("/{full_path:path}")
def spa_fallback(full_path: str) -> FileResponse:
    candidate = settings.frontend_dir / full_path
    if candidate.exists() and candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(settings.frontend_dir / "index.html")
