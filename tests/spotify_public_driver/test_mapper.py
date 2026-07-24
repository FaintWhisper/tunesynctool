from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest

from tunesynctool.drivers.common.spotify_public import SpotifyPublicMapper

from .fakes import FakePlaylist, FakeTrack


def test_playlist_service_data_remains_json_safe():
    mapped = SpotifyPublicMapper().map_playlist(FakePlaylist())

    assert json.loads(json.dumps(mapped.service_data)) == FakePlaylist().to_dict()


def test_track_without_tier_one_fields_maps_partial_metadata():
    raw = replace(
        FakeTrack(),
        album=None,
        release_date=None,
        track_number=None,
        artists=(),
    )

    mapped = SpotifyPublicMapper().map_track(raw)

    assert mapped.album_name is None
    assert mapped.release_year is None
    assert mapped.track_number is None
    assert mapped.primary_artist is None
    assert mapped.additional_artists == []
    assert mapped.isrc is None


@pytest.mark.parametrize("method_name", ["map_playlist", "map_track"])
def test_mapper_rejects_none(method_name):
    with pytest.raises(ValueError):
        getattr(SpotifyPublicMapper(), method_name)(None)


def test_mapper_rejects_incomplete_dtos_instead_of_silently_defaulting():
    class IncompleteTrack:
        def to_dict(self):
            return {}

    with pytest.raises(AttributeError):
        SpotifyPublicMapper().map_track(IncompleteTrack())


def test_mapper_contract_with_spotifyscraper_3_models():
    from spotify_scraper.models import AlbumRef, ArtistRef, Playlist, Track, UserRef

    raw_track = Track(
        id="track-id",
        uri="spotify:track:track-id",
        name="Track title",
        duration_ms=234567,
        explicit=False,
        playable=True,
        preview_url=None,
        artists=(ArtistRef(name="Artist"),),
        images=(),
        release_date=datetime(2024, 7, 3, tzinfo=timezone.utc),
        album=AlbumRef(
            id="album-id",
            uri="spotify:album:album-id",
            name="Album title",
        ),
        track_number=4,
    )
    raw_playlist = Playlist(
        id="playlist-id",
        uri="spotify:playlist:playlist-id",
        name="Playlist title",
        owner=UserRef(name="Owner"),
        total_tracks=0,
    )

    mapper = SpotifyPublicMapper()
    mapped_track = mapper.map_track(raw_track)
    mapped_playlist = mapper.map_playlist(raw_playlist)

    assert mapped_track.service_id == "track-id"
    assert mapped_track.primary_artist == "Artist"
    assert mapped_track.album_name == "Album title"
    assert mapped_track.release_year == 2024
    assert mapped_track.isrc is None
    assert mapped_playlist.service_id == "playlist-id"
    assert mapped_playlist.description == ""
    assert mapped_playlist.author_name == "Owner"
