from __future__ import annotations

from dataclasses import replace

import pytest

from tunesynctool.drivers.common.spotify_public import SpotifyPublicDriver
from tunesynctool.exceptions import ServiceDriverException, UnsupportedFeatureException
from tunesynctool.models import Configuration

from .fakes import FakePlaylist, FakePlaylistTrack, FakeTrack


class RecordingClient:
    def __init__(self, playlist):
        self.playlist = playlist
        self.calls = []

    def get_playlist(self, playlist_id, *, max_tracks):
        self.calls.append((playlist_id, max_tracks))
        return self.playlist


def make_driver(playlist):
    client = RecordingClient(playlist)
    return SpotifyPublicDriver(Configuration(), _public_client=client), client


def test_driver_is_credential_free_and_spotify_compatible():
    driver, _ = make_driver(FakePlaylist())

    assert driver.service_name == "spotify"
    assert driver.supports_direct_isrc_querying is False
    assert driver.supports_musicbrainz_id_querying is False


def test_get_playlist_fetches_metadata_only_by_default():
    driver, client = make_driver(FakePlaylist())

    result = driver.get_playlist(
        "  https://open.spotify.com/playlist/playlist-id?pt=secret#fragment  "
    )

    assert client.calls == [
        ("https://open.spotify.com/playlist/playlist-id", 0)
    ]
    assert result.service_id == "playlist-id"
    assert result.service_name == "spotify"
    assert result.name == "Public playlist"
    assert result.description == "Description"
    assert result.author_name == "Playlist owner"
    assert result.is_public is True
    assert result.service_data == FakePlaylist().to_dict()


def test_share_parameters_do_not_reach_client_or_error_text():
    seen = []

    class MissingClient:
        def get_playlist(self, playlist_id, *, max_tracks):
            seen.append(playlist_id)
            raise RuntimeError(f"failed for {playlist_id}")

    driver = SpotifyPublicDriver(Configuration(), _public_client=MissingClient())

    with pytest.raises(ServiceDriverException) as caught:
        driver.get_playlist(
            "https://open.spotify.com/playlist/playlist-id?pt=secret#fragment"
        )

    assert seen == ["https://open.spotify.com/playlist/playlist-id"]
    assert "pt=secret" not in str(caught.value)
    assert "#fragment" not in str(caught.value)


def test_get_playlist_can_forward_an_explicit_track_limit():
    driver, client = make_driver(FakePlaylist())

    driver.get_playlist("playlist-id", max_tracks=12)

    assert client.calls == [("playlist-id", 12)]


def test_get_playlist_tracks_maps_wrapped_track():
    driver, client = make_driver(FakePlaylist())

    result = driver.get_playlist_tracks("playlist-id?si=secret", limit=5)

    assert client.calls == [("playlist-id", 5)]
    assert len(result) == 1
    track = result[0]
    assert track.service_id == "track-id"
    assert track.service_name == "spotify"
    assert track.title == "Track title"
    assert track.primary_artist == "Primary artist"
    assert track.additional_artists == ["Featured artist"]
    assert track.album_name == "Album title"
    assert track.duration_seconds == 234
    assert track.track_number == 4
    assert track.release_year == 2024
    assert track.isrc is None
    assert track.service_data == FakePlaylist().tracks[0].track.to_dict()


def test_get_playlist_tracks_preserves_order_and_duplicates():
    first = FakePlaylistTrack(FakeTrack(id="first", name="First"))
    duplicate = FakePlaylistTrack(FakeTrack(id="first", name="First"))
    last = FakePlaylistTrack(FakeTrack(id="last", name="Last"))
    playlist = replace(
        FakePlaylist(),
        total_tracks=3,
        tracks=(first, duplicate, last),
    )
    driver, _ = make_driver(playlist)

    result = driver.get_playlist_tracks("playlist-id", limit=0)

    assert [(track.service_id, track.title) for track in result] == [
        ("first", "First"),
        ("first", "First"),
        ("last", "Last"),
    ]


@pytest.mark.parametrize("limit", [0, -1])
def test_nonpositive_track_limit_requests_all_tracks(limit):
    driver, client = make_driver(FakePlaylist())

    driver.get_playlist_tracks("playlist-id", limit=limit)

    assert client.calls == [("playlist-id", None)]


def test_unlimited_tracks_fail_closed_when_total_is_unknown():
    playlist = replace(FakePlaylist(), total_tracks=None)
    driver, client = make_driver(playlist)

    with pytest.raises(ServiceDriverException) as caught:
        driver.get_playlist_tracks("playlist-id", limit=0)

    assert client.calls == [("playlist-id", None)]
    assert "potentially incomplete" in str(caught.value)


def test_finite_tracks_do_not_require_a_total_count():
    playlist = replace(FakePlaylist(), total_tracks=None)
    driver, client = make_driver(playlist)

    result = driver.get_playlist_tracks("playlist-id", limit=1)

    assert client.calls == [("playlist-id", 1)]
    assert len(result) == 1


def test_unexpected_client_errors_are_sanitized():
    class BrokenClient:
        def get_playlist(self, playlist_id, *, max_tracks):
            raise RuntimeError("access_token=secret")

    driver = SpotifyPublicDriver(Configuration(), _public_client=BrokenClient())

    with pytest.raises(ServiceDriverException) as caught:
        driver.get_playlist("playlist-id")

    assert "access_token=secret" not in str(caught.value)


@pytest.mark.parametrize(
    ("method_name", "args"),
    [
        ("get_user_playlists", ()),
        ("create_playlist", ("name",)),
        ("add_tracks_to_playlist", ("playlist-id", ["track-id"])),
        ("remove_tracks_from_playlist", ("playlist-id", ["track-id"])),
        ("get_random_track", ()),
        ("get_track", ("track-id",)),
        ("search_tracks", ("query",)),
        ("get_track_by_isrc", ("USRC17607839",)),
    ],
)
def test_non_public_playlist_operations_are_explicitly_unsupported(
    method_name,
    args,
):
    driver, client = make_driver(FakePlaylist())

    with pytest.raises(UnsupportedFeatureException):
        getattr(driver, method_name)(*args)

    assert client.calls == []
