from click.testing import CliRunner

from fftf_tools.cli import main


def test_help_lists_commands():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    for cmd in (
        "vo-check",
        "duck-sheet",
        "drive-checklist",
        "thumb-safe",
        "distro-pack",
        "shorts-cutter",
        "brief-pack",
        "claim-gate",
        "script-strip",
        "picture-sync",
        "thumb-pack",
    ):
        assert cmd in result.output


def test_new_command_help():
    runner = CliRunner()
    for cmd in ("brief-pack", "claim-gate", "script-strip", "picture-sync", "thumb-pack"):
        result = runner.invoke(main, [cmd, "--help"])
        assert result.exit_code == 0
        assert cmd in result.output
        assert "--json" in result.output
