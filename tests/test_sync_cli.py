import importlib
from unittest.mock import MagicMock

from click.testing import CliRunner

from tunesynctool.cli.main import cli
from tunesynctool.drivers import ServiceDriver
from tunesynctool.exceptions import UnsupportedFeatureException
from tunesynctool.models import Playlist, Track


def make_track(
    title: str,
    service_id: str,
    *,
    service_name: str,
) -> Track:
    return Track(
        title=title,
        primary_artist='Artist',
        duration_seconds=200,
        service_id=service_id,
        service_name=service_name,
    )


def test_sync_does_not_add_before_an_unsupported_removal(monkeypatch) -> None:
    sync_module = importlib.import_module('tunesynctool.cli.commands.sync')
    source_driver = MagicMock(spec=ServiceDriver)
    target_driver = MagicMock(spec=ServiceDriver)
    source_driver.get_playlist.return_value = Playlist(
        name='Source',
        service_id='source-playlist',
        service_name='spotify',
    )
    target_driver.get_playlist.return_value = Playlist(
        name='Target',
        service_id='target-playlist',
        service_name='subsonic',
    )

    first_source = make_track(
        'First Song',
        'first-source',
        service_name='spotify',
    )
    second_source = make_track(
        'Second Song',
        'second-source',
        service_name='spotify',
    )
    first_target = make_track(
        'First Song',
        'first-target',
        service_name='subsonic',
    )
    second_target = make_track(
        'Second Song',
        'second-target',
        service_name='subsonic',
    )
    source_driver.get_playlist_tracks.return_value = [
        first_source,
        second_source,
    ]
    target_driver.get_playlist_tracks.return_value = [
        second_target,
        first_target,
    ]
    target_driver.remove_tracks_from_playlist.side_effect = (
        UnsupportedFeatureException()
    )

    def fake_get_driver(provider: str):
        driver = source_driver if provider == 'spotify' else target_driver
        return lambda _config: driver

    monkeypatch.setattr(sync_module, 'get_driver_by_name', fake_get_driver)

    result = CliRunner().invoke(
        cli,
        [
            'sync',
            '--from',
            'spotify',
            '--from-playlist',
            'source-playlist',
            '--to',
            'subsonic',
            '--to-playlist',
            'target-playlist',
        ],
    )

    assert result.exit_code == 1, result.output
    assert 'sync could not be completed' in result.output
    target_driver.add_tracks_to_playlist.assert_not_called()
