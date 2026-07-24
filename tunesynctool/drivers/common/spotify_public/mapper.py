"""Map SpotifyScraper's typed public models into tunesynctool models."""

from __future__ import annotations

from typing import Any

from tunesynctool.drivers.service_mapper import ServiceMapper
from tunesynctool.models import Playlist, Track


def _service_data(data: Any) -> dict:
    """Keep SpotifyScraper's documented JSON-safe representation."""

    result = data.to_dict()
    if not isinstance(result, dict):
        raise ValueError("SpotifyScraper to_dict() must return a dictionary.")
    return result


class SpotifyPublicMapper(ServiceMapper):
    """Map SpotifyScraper playlist and track models."""

    def map_playlist(self, data: Any) -> Playlist:
        if data is None:
            raise ValueError("Input data cannot be None.")

        owner = data.owner
        return Playlist(
            service_id=data.id,
            service_name="spotify",
            name=data.name,
            description=data.description,
            is_public=True,
            author_name=owner.name if owner is not None else None,
            service_data=_service_data(data),
        )

    def map_track(self, data: Any) -> Track:
        if data is None:
            raise ValueError("Input data cannot be None.")

        artist_names = [artist.name for artist in data.artists]
        release_year = (
            data.release_date.year
            if data.release_date is not None
            else None
        )

        return Track(
            title=data.name,
            album_name=data.album.name if data.album is not None else None,
            primary_artist=artist_names[0] if artist_names else None,
            additional_artists=artist_names[1:],
            duration_seconds=int(data.duration_ms / 1000),
            track_number=data.track_number,
            release_year=release_year,
            isrc=None,
            service_id=data.id,
            service_name="spotify",
            service_data=_service_data(data),
        )
