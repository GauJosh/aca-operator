import re

from typer.testing import CliRunner

from synoscd.cli import app

runner = CliRunner()


ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _plain(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text)


def test_cli_help_contains_reconcile_and_get_commands():
    result = runner.invoke(app, ["--help"])
    stdout = _plain(result.stdout)
    assert result.exit_code == 0
    assert "reconcile" in stdout
    assert "get" in stdout
    assert "diff" in stdout


def test_diff_help_is_available():
    result = runner.invoke(app, ["diff", "--help"])
    stdout = _plain(result.stdout)
    assert result.exit_code == 0
    assert "Show desired vs live state differences" in stdout


def test_reconcile_help_contains_app_and_source():
    result = runner.invoke(app, ["reconcile", "--help"])
    stdout = _plain(result.stdout)
    assert result.exit_code == 0
    assert "app" in stdout
    assert "source" in stdout


def test_get_help_contains_apps_source_status():
    result = runner.invoke(app, ["get", "--help"])
    stdout = _plain(result.stdout)
    assert result.exit_code == 0
    assert "apps" in stdout
    assert "source" in stdout
    assert "status" in stdout


def test_cli_help_contains_status_logs_and_config_commands():
    result = runner.invoke(app, ["--help"])
    stdout = _plain(result.stdout)
    assert result.exit_code == 0
    assert "status" in stdout
    assert "logs" in stdout
    assert "config" in stdout
    assert "describe" in stdout
    assert "set" in stdout
    assert "suspend" in stdout
    assert "resume" in stdout


def test_status_help_contains_app_and_all_commands():
    result = runner.invoke(app, ["status", "--help"])
    stdout = _plain(result.stdout)
    assert result.exit_code == 0
    assert "app" in stdout
    assert "all" in stdout


def test_logs_help_contains_app_and_operator_commands():
    result = runner.invoke(app, ["logs", "--help"])
    stdout = _plain(result.stdout)
    assert result.exit_code == 0
    assert "app" in stdout
    assert "operator" in stdout


def test_describe_help_is_available():
    result = runner.invoke(app, ["describe", "--help"])
    stdout = _plain(result.stdout)
    assert result.exit_code == 0
    assert "alias for 'status app'" in stdout
    assert "yaml" in stdout


def test_set_help_contains_supported_flags():
    result = runner.invoke(app, ["set", "--help"])
    stdout = _plain(result.stdout)
    assert result.exit_code == 0
    assert "--interval" in stdout
    assert "--prune" in stdout
    assert "--protected-apps" in stdout
    assert "--max-concurrent" in stdout


def test_cli_help_contains_global_logging_flags():
    result = runner.invoke(app, ["--help"])
    stdout = _plain(result.stdout)
    assert result.exit_code == 0
    assert "--verbose" in stdout
    assert "--debug" in stdout
