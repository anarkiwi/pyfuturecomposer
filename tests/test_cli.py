"""CLI tests."""

import pytest

from pyfuturecomposer import cli, parse, read


def test_info(capsys, tune_path):
    assert cli.main(["info", str(tune_path)]) == 0
    out = capsys.readouterr().out
    assert "load:" in out
    assert "init/play:" in out


def test_reglog(tmp_path, tune_path):
    out = tmp_path / "log.txt"
    assert cli.main(["reglog", str(tune_path), str(out), "--seconds", "0.2"]) == 0
    assert out.exists()
    assert out.read_text(encoding="utf-8").strip()


def test_reglog_error(tmp_path):
    missing = tmp_path / "nope.sid"
    assert cli.main(["reglog", str(missing), str(tmp_path / "o.txt")]) == 1


def test_export_prg(tmp_path, tune_path):
    out = tmp_path / "editor.prg"
    assert cli.main(["export", str(tune_path), str(out)]) == 0
    song = read(tune_path)
    assert parse(out.read_bytes()).image == song.image


def test_export_sid_round_trip(tmp_path, tune_path):
    out = tmp_path / "wrapped.sid"
    assert cli.main(["export", str(tune_path), str(out)]) == 0
    assert read(out) == read(tune_path)


def test_export_format_override(tmp_path, tune_path):
    out = tmp_path / "module.bin"
    assert cli.main(["export", str(tune_path), str(out), "--format", "sid"]) == 0
    assert read(out) == read(tune_path)


def test_no_command_exits():
    with pytest.raises(SystemExit):
        cli.main([])
