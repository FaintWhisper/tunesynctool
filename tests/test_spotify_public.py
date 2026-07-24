import importlib
from pathlib import Path
import subprocess
import sys
import textwrap
import tomllib

import pytest
from click.testing import CliRunner

from tunesynctool.cli.main import cli
from tunesynctool.cli.utils.driver import (
    SOURCE_ONLY_PROVIDERS,
    SUPPORTED_PROVIDERS,
    UNSAFE_SYNC_SOURCE_PROVIDERS,
    get_driver_by_name,
)
from tunesynctool.exceptions import ServiceDriverException
from tunesynctool.models import Playlist


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def run_in_fresh_python(source: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )


def test_spotifyscraper_is_a_required_project_dependency():
    with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as project_file:
        project = tomllib.load(project_file)["project"]

    assert any(
        dependency.startswith("spotifyscraper>=3.9.2,<4")
        for dependency in project["dependencies"]
    )
    assert "spotify-public" not in project["optional-dependencies"]


def test_base_import_does_not_load_spotifyscraper():
    result = run_in_fresh_python(
        """
        import sys

        import tunesynctool
        from tunesynctool import SpotifyDriver, SubsonicDriver, YouTubeDriver

        assert SpotifyDriver.__name__ == "SpotifyDriver"
        assert SubsonicDriver.__name__ == "SubsonicDriver"
        assert YouTubeDriver.__name__ == "YouTubeDriver"
        assert not any(
            name == "spotify_scraper" or name.startswith("spotify_scraper.")
            for name in sys.modules
        )
        """
    )

    assert result.returncode == 0, result.stderr


def test_spotify_public_is_a_registered_source_only_provider():
    assert "spotify-public" in SUPPORTED_PROVIDERS
    assert "spotify-public" in SOURCE_ONLY_PROVIDERS
    assert "spotify-public" in UNSAFE_SYNC_SOURCE_PROVIDERS
    assert get_driver_by_name("spotify").__name__ == "SpotifyDriver"


@pytest.mark.parametrize("command", ["transfer", "sync"])
def test_cli_rejects_spotify_public_as_a_destination(command: str):
    if command == "transfer":
        arguments = [
            command,
            "--from",
            "spotify",
            "--to",
            "spotify-public",
            "playlist-id",
        ]
    else:
        arguments = [
            command,
            "--from",
            "spotify",
            "--from-playlist",
            "source-id",
            "--to",
            "spotify-public",
            "--to-playlist",
            "target-id",
        ]

    result = CliRunner().invoke(cli, arguments)

    assert result.exit_code == 2, result.output
    assert "'spotify-public' is read-only" in result.output
    assert "can only be used as --from" in result.output


def test_cli_rejects_spotify_public_as_a_sync_source():
    result = CliRunner().invoke(
        cli,
        [
            "sync",
            "--from",
            "spotify-public",
            "--from-playlist",
            "source-id",
            "--to",
            "subsonic",
            "--to-playlist",
            "target-id",
        ],
    )

    assert result.exit_code == 2, result.output
    assert "cannot be used with sync" in result.output
    assert "Use transfer instead" in result.output


def test_transfer_sanitizes_public_track_fetch_errors(monkeypatch):
    transfer_module = importlib.import_module(
        "tunesynctool.cli.commands.transfer"
    )

    class FailingSource:
        def get_playlist(self, _playlist_id):
            return Playlist(
                service_id="playlist-id",
                service_name="spotify",
                name="Public playlist",
            )

        def get_playlist_tracks(self, **_kwargs):
            try:
                raise RuntimeError("pt=private-token")
            except RuntimeError as error:
                raise ServiceDriverException(
                    "Spotify public playlist access failed."
                ) from error

    class UnusedTarget:
        pass

    def fake_get_driver(name):
        driver = FailingSource if name == "spotify-public" else UnusedTarget
        return lambda _config: driver()

    monkeypatch.setattr(
        transfer_module,
        "get_driver_by_name",
        fake_get_driver,
    )

    result = CliRunner().invoke(
        cli,
        [
            "transfer",
            "--from",
            "spotify-public",
            "--to",
            "subsonic",
            "playlist-id",
        ],
    )

    assert result.exit_code == 2, result.output
    assert "Spotify public playlist access failed" in result.output
    assert "pt=private-token" not in result.output
    assert "Traceback" not in result.output


def test_spotify_public_driver_constructs_with_standard_install():
    from tunesynctool import Configuration, SpotifyPublicDriver

    driver = SpotifyPublicDriver(Configuration())

    assert driver.__class__.__name__ == "SpotifyPublicDriver"
