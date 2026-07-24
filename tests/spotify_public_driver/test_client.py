from __future__ import annotations

import pytest

from tunesynctool.drivers.common.spotify_public.client import (
    SpotifyScraperClient,
    _SpotifyScraperRuntime,
)
from tunesynctool.exceptions import (
    OptionalDependencyException,
    PlaylistNotFoundException,
    ServiceDriverException,
)

from .fakes import FakePlaylist


class FakeSpotifyScraperError(Exception):
    pass


class FakeURLError(FakeSpotifyScraperError):
    pass


class FakeNotFoundError(FakeSpotifyScraperError):
    pass


def runtime_for(factory):
    return _SpotifyScraperRuntime(
        client_factory=factory,
        url_error=FakeURLError,
        not_found_error=FakeNotFoundError,
        scraper_error=FakeSpotifyScraperError,
    )


def test_wrapper_uses_context_manager_and_forwards_limit():
    events = []
    playlist = FakePlaylist()

    class Client:
        def __enter__(self):
            events.append("enter")
            return self

        def __exit__(self, *args):
            events.append("exit")

        def get_playlist(self, playlist_id, *, max_tracks):
            events.append((playlist_id, max_tracks))
            return playlist

    wrapper = SpotifyScraperClient(_runtime_loader=lambda: runtime_for(Client))

    assert (
        wrapper.get_playlist(
            " https://open.spotify.com/playlist/playlist-id?pt=secret#fragment ",
            max_tracks=0,
        )
        is playlist
    )
    assert events == [
        "enter",
        ("https://open.spotify.com/playlist/playlist-id", 0),
        "exit",
    ]


@pytest.mark.parametrize("error_type", [FakeURLError, FakeNotFoundError])
def test_wrapper_translates_invalid_or_missing_playlist(error_type):
    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get_playlist(self, playlist_id, *, max_tracks):
            raise error_type("secret raw URL details")

    wrapper = SpotifyScraperClient(_runtime_loader=lambda: runtime_for(Client))

    with pytest.raises(PlaylistNotFoundException) as caught:
        wrapper.get_playlist("playlist-id", max_tracks=0)

    assert "secret raw URL details" not in str(caught.value)


def test_wrapper_sanitizes_other_spotify_scraper_errors():
    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get_playlist(self, playlist_id, *, max_tracks):
            raise FakeSpotifyScraperError("access_token=secret")

    wrapper = SpotifyScraperClient(_runtime_loader=lambda: runtime_for(Client))

    with pytest.raises(ServiceDriverException) as caught:
        wrapper.get_playlist("playlist-id", max_tracks=None)

    assert "access_token=secret" not in str(caught.value)
    assert "upgrading SpotifyScraper" in str(caught.value)


def test_missing_dependency_error_is_actionable(monkeypatch):
    def missing_module(name):
        raise ModuleNotFoundError(
            "No module named 'spotify_scraper'",
            name="spotify_scraper",
        )

    monkeypatch.setattr(
        "tunesynctool.drivers.common.spotify_public.client.import_module",
        missing_module,
    )

    with pytest.raises(OptionalDependencyException) as caught:
        SpotifyScraperClient()

    assert str(caught.value).startswith(
        "Public Spotify playlist support is not installed"
    )
    assert "tunesynctool[spotify-public]" in str(caught.value)


def test_missing_transitive_dependency_is_not_misreported(monkeypatch):
    def broken_install(name):
        raise ModuleNotFoundError("No module named 'httpx'", name="httpx")

    monkeypatch.setattr(
        "tunesynctool.drivers.common.spotify_public.client.import_module",
        broken_install,
    )

    with pytest.raises(ModuleNotFoundError, match="httpx"):
        SpotifyScraperClient()
