from typer.testing import CliRunner

from synoscd.cli import app


runner = CliRunner()


def test_cli_help_contains_reconcile_and_get_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "reconcile" in result.stdout
    assert "get" in result.stdout
    assert "diff" in result.stdout


def test_diff_help_is_available():
    result = runner.invoke(app, ["diff", "--help"])
    assert result.exit_code == 0
    assert "Show desired vs live state differences" in result.stdout


def test_reconcile_help_contains_app_and_source():
    result = runner.invoke(app, ["reconcile", "--help"])
    assert result.exit_code == 0
    assert "app" in result.stdout
    assert "source" in result.stdout


def test_get_help_contains_apps_source_status():
    result = runner.invoke(app, ["get", "--help"])
    assert result.exit_code == 0
    assert "apps" in result.stdout
    assert "source" in result.stdout
    assert "status" in result.stdout


def test_cli_help_contains_status_logs_and_config_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "status" in result.stdout
    assert "logs" in result.stdout
    assert "config" in result.stdout


def test_status_help_contains_app_and_all_commands():
    result = runner.invoke(app, ["status", "--help"])
    assert result.exit_code == 0
    assert "app" in result.stdout
    assert "all" in result.stdout


def test_logs_help_contains_app_and_operator_commands():
    result = runner.invoke(app, ["logs", "--help"])
    assert result.exit_code == 0
    assert "app" in result.stdout
    assert "operator" in result.stdout