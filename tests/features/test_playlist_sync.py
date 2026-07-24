from unittest.mock import MagicMock, call

import pytest

from tunesynctool.drivers import ServiceDriver
from tunesynctool.exceptions import (
    ServiceDriverException,
    TrackNotFoundException,
    UnsupportedFeatureException,
)
from tunesynctool.features import PlaylistSynchronizer
from tunesynctool.models import MatchPolicy, Track


def build_synchronizer(
    policy: MatchPolicy | str = MatchPolicy.STRICT,
) -> PlaylistSynchronizer:
    dummy_driver = MagicMock(spec=ServiceDriver)
    return PlaylistSynchronizer(
        source_driver=dummy_driver,
        target_driver=dummy_driver,
        match_policy=policy,
    )


def make_track(
    title: str,
    artist: str,
    service_id: str,
    service_name: str = 'spotify',
    duration_seconds: int | None = None,
) -> Track:
    return Track(
        title=title,
        primary_artist=artist,
        duration_seconds=duration_seconds,
        service_id=service_id,
        service_name=service_name,
    )


def test_find_missing_tracks_handles_equivalent_versions() -> None:
    synchronizer = build_synchronizer()

    spotify_track = make_track(
        title='Example Track',
        artist='Primary Artist',
        service_id='spotify-1',
    )
    navidrome_variant = make_track(
        title='Example Track (feat. Guest Artist)',
        artist='Primary Artist • Guest Artist',
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
        title='Example Track (Radio Edit)',
        artist='Primary Artist',
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


def test_reorder_sync_requests_complete_source_and_target_playlists() -> None:
    source_driver = MagicMock(spec=ServiceDriver)
    target_driver = MagicMock(spec=ServiceDriver)
    source_driver.get_playlist_tracks.return_value = []
    target_driver.get_playlist_tracks.return_value = []
    synchronizer = PlaylistSynchronizer(
        source_driver=source_driver,
        target_driver=target_driver,
    )

    synchronizer.sync(
        source_playlist_id="source-playlist",
        target_playlist_id="target-playlist",
    )

    source_driver.get_playlist_tracks.assert_called_once_with(
        playlist_id="source-playlist",
        limit=0,
    )
    target_driver.get_playlist_tracks.assert_called_once_with(
        playlist_id="target-playlist",
        limit=0,
    )


def test_strict_sync_treats_wrong_remix_as_missing() -> None:
    synchronizer = build_synchronizer()
    source = make_track(
        'Example Track',
        'Primary Artist',
        'source',
        duration_seconds=187,
    )
    remix = make_track(
        'Example Track (Guest Producer Remix)',
        'Primary Artist & Guest Producer',
        'remix',
        service_name='subsonic',
        duration_seconds=196,
    )

    assert synchronizer.find_missing_tracks([source], [remix]) == [source]


def test_relaxed_sync_can_accept_close_soft_edit_difference() -> None:
    synchronizer = build_synchronizer(MatchPolicy.RELAXED)
    source = make_track(
        'Example Track - Radio Edit',
        'Artist',
        'source',
        duration_seconds=180,
    )
    unlabeled = make_track(
        'Example Track',
        'Artist',
        'target',
        service_name='subsonic',
        duration_seconds=185,
    )

    assert synchronizer.find_missing_tracks([source], [unlabeled]) == []


def test_existing_playlist_candidate_is_ranked_by_duration() -> None:
    synchronizer = build_synchronizer()
    source = make_track(
        'Example Track',
        'Primary Artist',
        'source',
        duration_seconds=271,
    )
    worse = make_track(
        'Example Track',
        'Primary Artist • Guest Artist',
        'worse',
        service_name='subsonic',
        duration_seconds=279,
    )
    exact = make_track(
        'Example Track (feat. Guest Artist)',
        'Primary Artist & Guest Artist',
        'exact',
        service_name='subsonic',
        duration_seconds=271,
    )

    assert synchronizer.find_matching_track(source, [worse, exact]) is exact


def test_sync_does_not_append_when_existing_playlist_cannot_be_cleared() -> None:
    source_driver = MagicMock(spec=ServiceDriver)
    target_driver = MagicMock(spec=ServiceDriver)
    first_source_track = make_track(
        'First Song',
        'Artist',
        'first-source-id',
        duration_seconds=200,
    )
    second_source_track = make_track(
        'Second Song',
        'Artist',
        'second-source-id',
        duration_seconds=220,
    )
    first_target_track = make_track(
        'First Song',
        'Artist',
        'first-target-id',
        service_name='subsonic',
        duration_seconds=200,
    )
    second_target_track = make_track(
        'Second Song',
        'Artist',
        'second-target-id',
        service_name='subsonic',
        duration_seconds=220,
    )
    source_driver.get_playlist_tracks.return_value = [
        first_source_track,
        second_source_track,
    ]
    target_driver.get_playlist_tracks.return_value = [
        second_target_track,
        first_target_track,
    ]
    target_driver.remove_tracks_from_playlist.side_effect = (
        UnsupportedFeatureException()
    )
    synchronizer = PlaylistSynchronizer(source_driver, target_driver)

    with pytest.raises(UnsupportedFeatureException):
        synchronizer.sync('source-playlist', 'target-playlist')

    target_driver.add_tracks_to_playlist.assert_not_called()


def test_sync_does_not_mutate_when_any_source_track_is_unresolved() -> None:
    source_driver = MagicMock(spec=ServiceDriver)
    target_driver = MagicMock(spec=ServiceDriver)
    available_target_track = make_track(
        'Available Song',
        'Artist',
        'available-target-id',
        service_name='subsonic',
        duration_seconds=180,
    )
    source_driver.get_playlist_tracks.return_value = [
        make_track(
            'Available Song',
            'Artist',
            'available-source-id',
            duration_seconds=180,
        ),
        make_track(
            'Unavailable Song',
            'Artist',
            'source-id',
            duration_seconds=200,
        )
    ]
    target_driver.get_playlist_tracks.return_value = [
        make_track(
            'Old Target Song',
            'Different Artist',
            'old-target-id',
            service_name='subsonic',
            duration_seconds=240,
        )
    ]
    target_driver.service_name = 'subsonic'
    target_driver.supports_direct_isrc_querying = False
    target_driver.supports_musicbrainz_id_querying = False
    target_driver.search_tracks.return_value = [available_target_track]
    synchronizer = PlaylistSynchronizer(source_driver, target_driver)

    with pytest.raises(
        TrackNotFoundException,
        match='target playlist was not modified',
    ):
        synchronizer.sync('source-playlist', 'target-playlist')

    target_driver.remove_tracks_from_playlist.assert_not_called()
    target_driver.add_tracks_to_playlist.assert_not_called()


def test_apply_target_order_restores_original_tracks_after_add_failure() -> None:
    source_driver = MagicMock(spec=ServiceDriver)
    target_driver = MagicMock(spec=ServiceDriver)
    original = make_track(
        'Original Song',
        'Artist',
        'original-id',
        service_name='subsonic',
    )
    replacement = make_track(
        'Replacement Song',
        'Artist',
        'replacement-id',
        service_name='subsonic',
    )
    update_error = ServiceDriverException('addition failed')
    target_driver.add_tracks_to_playlist.side_effect = [update_error, None]
    synchronizer = PlaylistSynchronizer(source_driver, target_driver)

    with pytest.raises(ServiceDriverException, match='addition failed'):
        synchronizer.apply_target_order(
            'target-playlist',
            [original],
            [replacement],
        )

    assert target_driver.remove_tracks_from_playlist.call_args_list == [
        call(
            playlist_id='target-playlist',
            track_ids=['original-id'],
        ),
        call(
            playlist_id='target-playlist',
            track_ids=['replacement-id'],
        ),
    ]
    assert target_driver.add_tracks_to_playlist.call_args_list == [
        call(
            playlist_id='target-playlist',
            track_ids=['replacement-id'],
        ),
        call(
            playlist_id='target-playlist',
            track_ids=['original-id'],
        ),
    ]


def test_apply_target_order_reports_failed_rollback() -> None:
    source_driver = MagicMock(spec=ServiceDriver)
    target_driver = MagicMock(spec=ServiceDriver)
    original = make_track(
        'Original Song',
        'Artist',
        'original-id',
        service_name='subsonic',
    )
    replacement = make_track(
        'Replacement Song',
        'Artist',
        'replacement-id',
        service_name='subsonic',
    )
    target_driver.add_tracks_to_playlist.side_effect = [
        ServiceDriverException('addition failed'),
        ServiceDriverException('restoration failed'),
    ]
    synchronizer = PlaylistSynchronizer(source_driver, target_driver)

    with pytest.raises(
        ServiceDriverException,
        match='could not be fully restored',
    ):
        synchronizer.apply_target_order(
            'target-playlist',
            [original],
            [replacement],
        )
