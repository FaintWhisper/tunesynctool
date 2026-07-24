from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class FakeArtist:
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name}


@dataclass(frozen=True)
class FakeAlbum:
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name}


@dataclass(frozen=True)
class FakeOwner:
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name}


@dataclass(frozen=True)
class FakeTrack:
    id: str = "track-id"
    name: str = "Track title"
    duration_ms: int = 234567
    artists: tuple[FakeArtist, ...] = (
        FakeArtist("Primary artist"),
        FakeArtist("Featured artist"),
    )
    album: FakeAlbum | None = FakeAlbum("Album title")
    release_date: datetime | None = datetime(2024, 7, 3, tzinfo=timezone.utc)
    track_number: int | None = 4

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "duration_ms": self.duration_ms,
            "artists": [artist.to_dict() for artist in self.artists],
            "album": self.album.to_dict() if self.album else None,
            "release_date": (
                self.release_date.isoformat() if self.release_date else None
            ),
            "track_number": self.track_number,
        }


@dataclass(frozen=True)
class FakePlaylistTrack:
    track: FakeTrack

    def to_dict(self) -> dict[str, Any]:
        return {"track": self.track.to_dict()}


@dataclass(frozen=True)
class FakePlaylist:
    id: str = "playlist-id"
    name: str = "Public playlist"
    description: str = "Description"
    owner: FakeOwner | None = FakeOwner("Playlist owner")
    total_tracks: int | None = 1
    tracks: tuple[FakePlaylistTrack, ...] = (
        FakePlaylistTrack(FakeTrack()),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner": self.owner.to_dict() if self.owner else None,
            "total_tracks": self.total_tracks,
            "tracks": [entry.to_dict() for entry in self.tracks],
        }
