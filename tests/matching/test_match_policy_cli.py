from click.testing import CliRunner

from tunesynctool.cli.main import cli
from tunesynctool.models import MatchPolicy


def test_match_policy_exposes_only_current_names():
    assert [policy.value for policy in MatchPolicy] == ['strict', 'relaxed']


def test_transfer_exposes_strict_and_relaxed_match_policies():
    result = CliRunner().invoke(cli, ['transfer', '--help'])

    assert result.exit_code == 0
    assert '--match-policy [strict|relaxed]' in result.output


def test_sync_exposes_strict_and_relaxed_match_policies():
    result = CliRunner().invoke(cli, ['sync', '--help'])

    assert result.exit_code == 0
    assert '--match-policy [strict|relaxed]' in result.output
