from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DiscoverRequest(BaseModel):
    genres: List[str] = Field(default_factory=list)
    limit: int = 6


class PromptRequest(BaseModel):
    prompt: str
    limit: int = 6


class FeedRequest(BaseModel):
    exclude_artist_keys: List[str] = Field(default_factory=list)


class SaveArtistRequest(BaseModel):
    artist_key: str
    artist: str
    song: Optional[str] = None
    genre: Optional[str] = None
    image: Optional[str] = None
    preview: Optional[str] = None
    deezer_link: Optional[str] = None
    lastfm_link: Optional[str] = None
    reason: Optional[str] = None
    top_genres: List[str] = Field(default_factory=list)
    similar_artists: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    audio_signature: Dict[str, float] = Field(default_factory=dict)
    source: str = "discover"
    is_custom: bool = False


class SuggestArtistRequest(BaseModel):
    isrc: str
    confirm_smaller_artist: bool = False
    note: str = ""


class CommunityPostRequest(BaseModel):
    text: str
    username: str = "du"
    tip_artist: Optional[str] = None
    tip_song: Optional[str] = None
