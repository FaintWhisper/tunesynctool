import pytest

from tunesynctool.models import Configuration


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", True),
        ("true", True),
        ("YES", True),
        (" on ", True),
        ("0", False),
        ("false", False),
        ("NO", False),
        (" off ", False),
    ],
)
def test_from_env_parses_subsonic_legacy_auth(monkeypatch, value, expected):
    monkeypatch.setenv("SUBSONIC_LEGACY_AUTH", value)

    assert Configuration.from_env().subsonic_legacy_auth is expected


def test_from_env_rejects_invalid_subsonic_legacy_auth(monkeypatch):
    monkeypatch.setenv("SUBSONIC_LEGACY_AUTH", "sometimes")

    with pytest.raises(
        ValueError,
        match="Invalid configuration value: SUBSONIC_LEGACY_AUTH",
    ):
        Configuration.from_env()


def test_from_env_preserves_defaults_when_variables_are_absent(monkeypatch):
    for name in (
        "SPOTIFY_REDIRECT_URI",
        "SPOTIFY_SCOPES",
        "SUBSONIC_BASE_URL",
        "SUBSONIC_PORT",
        "SUBSONIC_LEGACY_AUTH",
    ):
        monkeypatch.delenv(name, raising=False)

    assert Configuration.from_env() == Configuration()
