"""Read-only Spotify driver for public playlists."""

from __future__ import annotations

from typing import Any, List, Optional, Protocol

from tunesynctool.drivers.service_driver import ServiceDriver
from tunesynctool.exceptions import (
    PlaylistNotFoundException,
    ServiceDriverException,
    UnsupportedFeatureException,
)
from tunesynctool.models import Configuration, Playlist, Track

from .client import SpotifyScraperClient, _strip_share_parameters
from .mapper import SpotifyPublicMapper

_REQUEST_FAILED_MESSAGE = (
    "Spotify public playlist access failed. Spotify may have changed its public "
    "endpoints; try upgrading SpotifyScraper."
)
_INCOMPLETE_UNLIMITED_MESSAGE = (
    "Spotify did not report the playlist's total track count, so tunesynctool "
    "refused to return a potentially incomplete unlimited result."
)


class _PublicPlaylistClient(Protocol):
    def get_playlist(self, playlist_id: str, *, max_tracks: int | None) -> Any:
        """Fetch a public Spotify playlist."""


class SpotifyPublicDriver(ServiceDriver):
    """Access public Spotify playlists without OAuth or API credentials.

    This driver deliberately supports only playlist metadata and playlist
    tracks. All authenticated, write, search, and individual-track operations
    fail explicitly instead of silently switching semantics.
    """

    def __init__(
        self,
        config: Configuration,
        *,
        _public_client: _PublicPlaylistClient | None = None,
    ) -> None:
        super().__init__(
            service_name="spotify",
            config=config,
            mapper=SpotifyPublicMapper(),
        )
        self._public_client = (
            _public_client if _public_client is not None else SpotifyScraperClient()
        )

    def _fetch_playlist(self, playlist_id: str, *, max_tracks: int | None) -> Any:
        try:
            return self._public_client.get_playlist(
                _strip_share_parameters(playlist_id),
                max_tracks=max_tracks,
            )
        except (
            PlaylistNotFoundException,
            ServiceDriverException,
        ):
            raise
        except Exception as error:
            raise ServiceDriverException(_REQUEST_FAILED_MESSAGE) from error

    def get_playlist(
        self,
        playlist_id: str,
        max_tracks: int | None = 0,
    ) -> Playlist:
        """Fetch public playlist metadata, without tracks by default."""

        response = self._fetch_playlist(playlist_id, max_tracks=max_tracks)
        try:
            return self._mapper.map_playlist(response)
        except Exception as error:
            raise ServiceDriverException(_REQUEST_FAILED_MESSAGE) from error

    def get_playlist_tracks(
        self,
        playlist_id: str,
        limit: int = 100,
    ) -> List[Track]:
        max_tracks = None if limit <= 0 else limit
        response = self._fetch_playlist(playlist_id, max_tracks=max_tracks)

        if limit <= 0 and response.total_tracks is None:
            raise ServiceDriverException(_INCOMPLETE_UNLIMITED_MESSAGE)

        entries = tuple(response.tracks or ())
        if limit > 0:
            entries = entries[:limit]

        try:
            return [self._mapper.map_track(entry.track) for entry in entries]
        except Exception as error:
            raise ServiceDriverException(_REQUEST_FAILED_MESSAGE) from error

    def get_user_playlists(self, limit: int = 25) -> List[Playlist]:
        raise UnsupportedFeatureException(
            "Public Spotify access cannot fetch an authenticated user's playlists."
        )

    def create_playlist(self, name: str) -> Playlist:
        raise UnsupportedFeatureException(
            "Public Spotify access cannot create playlists."
        )

    def add_tracks_to_playlist(
        self,
        playlist_id: str,
        track_ids: List[str],
    ) -> None:
        raise UnsupportedFeatureException(
            "Public Spotify access cannot add tracks to playlists."
        )

    def remove_tracks_from_playlist(
        self,
        playlist_id: str,
        track_ids: List[str],
    ) -> None:
        raise UnsupportedFeatureException(
            "Public Spotify access cannot remove tracks from playlists."
        )

    def get_random_track(self) -> Optional[Track]:
        raise UnsupportedFeatureException(
            "Public Spotify access cannot fetch random tracks."
        )

    def get_track(self, track_id: str) -> Track:
        raise UnsupportedFeatureException(
            "Public Spotify access cannot fetch individual tracks."
        )

    def search_tracks(self, query: str, limit: int = 10) -> List[Track]:
        raise UnsupportedFeatureException(
            "Public Spotify access cannot search tracks."
        )

    def get_track_by_isrc(self, isrc: str) -> Track:
        raise UnsupportedFeatureException(
            "Public Spotify access cannot query tracks by ISRC."
        )
