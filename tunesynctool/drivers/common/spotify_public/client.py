"""Small, optional-dependency boundary around SpotifyScraper."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable

from tunesynctool.exceptions import (
    OptionalDependencyException,
    PlaylistNotFoundException,
    ServiceDriverException,
)

_INSTALL_MESSAGE = (
    "Public Spotify playlist support is not installed. Install this fork with "
    "the 'spotify-public' extra, for example: "
    'pip install "tunesynctool[spotify-public] @ '
    'git+https://github.com/FaintWhisper/tunesynctool.git"'
)
_INCOMPATIBLE_MESSAGE = (
    "Public Spotify playlist support needs a compatible SpotifyScraper 3.x "
    "installation. Reinstall the 'spotify-public' extra."
)
_NOT_FOUND_MESSAGE = (
    "The Spotify playlist is missing, private, or otherwise unavailable."
)
_REQUEST_FAILED_MESSAGE = (
    "Spotify public playlist access failed. Spotify may have changed its public "
    "endpoints; try upgrading SpotifyScraper."
)


def _strip_share_parameters(playlist_id: str) -> str:
    """Remove share-only query parameters and fragments before any request."""

    return playlist_id.strip().split("#", 1)[0].split("?", 1)[0]


@dataclass(frozen=True)
class _SpotifyScraperRuntime:
    client_factory: Callable[[], Any]
    url_error: type[BaseException]
    not_found_error: type[BaseException]
    scraper_error: type[BaseException]


def _load_runtime() -> _SpotifyScraperRuntime:
    """Import SpotifyScraper only when this optional feature is selected."""

    try:
        module = import_module("spotify_scraper")
    except ModuleNotFoundError as error:
        if error.name == "spotify_scraper":
            raise OptionalDependencyException(_INSTALL_MESSAGE) from error
        raise

    try:
        return _SpotifyScraperRuntime(
            client_factory=module.SpotifyClient,
            url_error=module.URLError,
            not_found_error=module.NotFoundError,
            scraper_error=module.SpotifyScraperError,
        )
    except AttributeError as error:
        raise OptionalDependencyException(_INCOMPATIBLE_MESSAGE) from error


class SpotifyScraperClient:
    """Fetch public playlist DTOs while hiding the optional implementation."""

    def __init__(
        self,
        *,
        _runtime_loader: Callable[[], _SpotifyScraperRuntime] = _load_runtime,
    ) -> None:
        # Loading here keeps ordinary tunesynctool imports dependency-free while
        # still surfacing a missing extra as soon as this driver is selected.
        self._runtime = _runtime_loader()

    def get_playlist(self, playlist_id: str, *, max_tracks: int | None) -> Any:
        safe_playlist_id = _strip_share_parameters(playlist_id)
        try:
            with self._runtime.client_factory() as client:
                return client.get_playlist(safe_playlist_id, max_tracks=max_tracks)
        except (self._runtime.url_error, self._runtime.not_found_error) as error:
            raise PlaylistNotFoundException(_NOT_FOUND_MESSAGE) from error
        except self._runtime.scraper_error as error:
            raise ServiceDriverException(_REQUEST_FAILED_MESSAGE) from error
