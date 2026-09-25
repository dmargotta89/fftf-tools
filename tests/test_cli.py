from click.testing import CliRunner

from fftf_tools.cli import main


def test_help_lists_commands():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    for cmd in ("vo-check", "duck-sheet", "drive-checklist", "thumb-safe"):
        assert cmd in result.output
