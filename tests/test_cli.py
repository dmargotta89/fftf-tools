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
        "edit-pass",
        "distro",
    ):
        assert cmd in result.output


def test_new_command_help():
    runner = CliRunner()
    for cmd in ("brief-pack", "claim-gate", "script-strip", "picture-sync", "thumb-pack"):
        result = runner.invoke(main, [cmd, "--help"])
        assert result.exit_code == 0
        assert cmd in result.output
        assert "--json" in result.output


def test_every_command_help_has_a_copy_paste_example():
    runner = CliRunner()
    commands = (
        ["vo-check"],
        ["duck-sheet"],
        ["drive-checklist"],
        ["thumb-safe"],
        ["distro-pack"],
        ["shorts-cutter"],
        ["brief-pack"],
        ["claim-gate"],
        ["script-strip"],
        ["picture-sync"],
        ["thumb-pack"],
        ["edit-pass"],
        ["edit-pass", "status"],
        ["distro"],
        ["distro", "status"],
        ["distro", "yt-long"],
        ["distro", "shorts"],
        ["distro", "podcast"],
        ["distro", "podcast-extended"],
    )
    for args in commands:
        result = runner.invoke(main, [*args, "--help"])
        assert result.exit_code == 0, result.output
        assert "Examples:" in result.output, args
        assert "fftf " in result.output
        assert "--publish" not in result.output
