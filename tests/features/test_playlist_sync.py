from unittest.mock import MagicMock

from tunesynctool.drivers import ServiceDriver
from tunesynctool.features import PlaylistSynchronizer
from tunesynctool.models import Track


def build_synchronizer() -> PlaylistSynchronizer:
    dummy_driver = MagicMock(spec=ServiceDriver)
    return PlaylistSynchronizer(
        source_driver=dummy_driver,
        target_driver=dummy_driver,
    )


def make_track(title: str, artist: str, service_id: str, service_name: str = 'spotify') -> Track:
    return Track(
        title=title,
        primary_artist=artist,
        service_id=service_id,
        service_name=service_name,
    )


def test_find_missing_tracks_handles_equivalent_versions() -> None:
    synchronizer = build_synchronizer()

    spotify_track = make_track(
        title='Back To Me',
        artist='KSHMR',
        service_id='spotify-1',
    )
    navidrome_variant = make_track(
        title='Back To Me (feat. Micky Blue)',
        artist='KSHMR • Crossnaders • Micky Blue',
        service_id='navidrome-1',
        service_name='subsonic',
    )

    missing = synchronizer.find_missing_tracks(
        source_playlist_tracks=[spotify_track],
        target_playlist_tracks=[navidrome_variant],
    )

    assert missing == []


def test_find_tracks_to_remove_detects_target_only_entries() -> None:
    synchronizer = build_synchronizer()

    shared_track = make_track(
        title='Strobe (Radio Edit)',
        artist='deadmau5',
        service_id='shared',
    )
    extra_track = make_track(
        title='Random Song',
        artist='Artist',
        service_id='extra',
    )

    tracks_to_remove = synchronizer.find_tracks_to_remove(
        source_playlist_tracks=[shared_track],
        target_playlist_tracks=[shared_track, extra_track],
    )

    assert tracks_to_remove == [extra_track]
