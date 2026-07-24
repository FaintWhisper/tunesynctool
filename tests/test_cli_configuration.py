import click
from click.testing import CliRunner

from tunesynctool.cli.main import cli


@click.command(name="_inspect-config")
@click.pass_obj
def inspect_config(obj):
    config = obj["config"]
    click.echo(
        "|".join(
            (
                config.spotify_redirect_uri,
                config.subsonic_base_url,
                str(config.subsonic_port),
                str(config.subsonic_legacy_auth),
            )
        )
    )


def invoke_inspector(arguments):
    cli.add_command(inspect_config)
    try:
        return CliRunner().invoke(cli, [*arguments, "_inspect-config"])
    finally:
        cli.commands.pop("_inspect-config")


def test_cli_uses_configuration_defaults(monkeypatch):
    for name in (
        "SPOTIFY_REDIRECT_URI",
        "SUBSONIC_BASE_URL",
        "SUBSONIC_PORT",
        "SUBSONIC_LEGACY_AUTH",
    ):
        monkeypatch.delenv(name, raising=False)

    result = invoke_inspector([])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == (
        "http://localhost:8888/callback|http://127.0.0.1|4533|False"
    )


def test_cli_uses_environment_and_allows_explicit_overrides(monkeypatch):
    monkeypatch.setenv("SPOTIFY_REDIRECT_URI", "https://env.example/callback")
    monkeypatch.setenv("SUBSONIC_BASE_URL", "https://env.example")
    monkeypatch.setenv("SUBSONIC_PORT", "4040")
    monkeypatch.setenv("SUBSONIC_LEGACY_AUTH", "true")

    from_environment = invoke_inspector([])
    overridden = invoke_inspector(
        [
            "--spotify-redirect-uri",
            "https://cli.example/callback",
            "--subsonic-base-url",
            "https://cli.example",
            "--subsonic-port",
            "5050",
            "--no-subsonic-legacy-auth",
        ]
    )

    assert from_environment.exit_code == 0, from_environment.output
    assert from_environment.output.strip() == (
        "https://env.example/callback|https://env.example|4040|True"
    )
    assert overridden.exit_code == 0, overridden.output
    assert overridden.output.strip() == (
        "https://cli.example/callback|https://cli.example|5050|False"
    )
