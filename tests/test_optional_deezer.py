import importlib.util
from pathlib import Path
import subprocess
import sys
import textwrap
import tomllib

import pytest

from tunesynctool.cli.utils.driver import (
    SOURCE_ONLY_PROVIDERS,
    SUPPORTED_PROVIDERS,
    get_driver_by_name,
)
from tunesynctool.exceptions import UnsupportedFeatureException


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def run_in_fresh_python(source: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )


def test_streamrip_is_a_deezer_only_project_dependency():
    with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as project_file:
        project = tomllib.load(project_file)["project"]

    assert not any(dependency.startswith("streamrip") for dependency in project["dependencies"])
    assert any(
        dependency.startswith("streamrip")
        for dependency in project["optional-dependencies"]["deezer"]
    )


def test_base_import_does_not_load_deezer_dependencies():
    result = run_in_fresh_python(
        """
        import sys

        import tunesynctool
        from tunesynctool import SpotifyDriver, SubsonicDriver, YouTubeDriver
        from tunesynctool.drivers.common.deezer import DeezerMapper

        assert SpotifyDriver.__name__ == "SpotifyDriver"
        assert SubsonicDriver.__name__ == "SubsonicDriver"
        assert YouTubeDriver.__name__ == "YouTubeDriver"
        assert DeezerMapper.__name__ == "DeezerMapper"
        assert not any(name == "streamrip" or name.startswith("streamrip.") for name in sys.modules)
        assert not any(name == "deezer" or name.startswith("deezer.") for name in sys.modules)
        """
    )

    assert result.returncode == 0, result.stderr


def test_deezer_is_still_a_supported_lazy_driver():
    assert "deezer" in SUPPORTED_PROVIDERS
    assert "deezer" in SOURCE_ONLY_PROVIDERS
    assert get_driver_by_name("spotify").__name__ == "SpotifyDriver"


def test_deezer_is_rejected_as_a_transfer_target():
    from click.testing import CliRunner
    from tunesynctool.cli.main import cli

    result = CliRunner().invoke(
        cli,
        ["transfer", "--from", "spotify", "--to", "deezer", "playlist-id"],
    )

    assert result.exit_code == 2, result.output
    assert "read-only and can only be used as --from" in result.output


def test_missing_deezer_extra_has_an_actionable_import_error():
    result = run_in_fresh_python(
        """
        import builtins

        real_import = builtins.__import__

        def import_without_streamrip(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "streamrip" or name.startswith("streamrip."):
                raise ModuleNotFoundError("No module named 'streamrip'", name="streamrip")
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = import_without_streamrip

        from tunesynctool.exceptions import OptionalDependencyException

        try:
            from tunesynctool import DeezerDriver
        except OptionalDependencyException as error:
            assert "Deezer support is not installed" in str(error)
            assert "tunesynctool[deezer]" in str(error)
        else:
            raise AssertionError("Importing DeezerDriver should require the Deezer extra.")
        """
    )

    assert result.returncode == 0, result.stderr


def test_missing_deezer_extra_has_an_actionable_cli_error():
    result = run_in_fresh_python(
        """
        import builtins

        real_import = builtins.__import__

        def import_without_streamrip(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "streamrip" or name.startswith("streamrip."):
                raise ModuleNotFoundError("No module named 'streamrip'", name="streamrip")
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = import_without_streamrip

        from click.testing import CliRunner
        from tunesynctool.cli.main import cli

        result = CliRunner().invoke(
            cli,
            ["transfer", "--from", "deezer", "--to", "spotify", "playlist-id"],
        )

        assert result.exit_code == 2, result.output
        assert "Deezer support is not installed" in result.output
        assert "tunesynctool[deezer]" in result.output
        """
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(
    importlib.util.find_spec("streamrip") is None,
    reason="The optional Deezer dependencies are not installed.",
)
def test_deezer_driver_imports_when_extra_is_installed():
    from tunesynctool import DeezerDriver

    assert DeezerDriver.__name__ == "DeezerDriver"


@pytest.mark.skipif(
    importlib.util.find_spec("streamrip") is None,
    reason="The optional Deezer dependencies are not installed.",
)
def test_deezer_get_user_playlists_raises_unsupported():
    from tunesynctool import DeezerDriver

    driver = object.__new__(DeezerDriver)

    with pytest.raises(UnsupportedFeatureException):
        driver.get_user_playlists()
