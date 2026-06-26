"""CLI tests."""

import pytest

from pyfuturecomposer import cli


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


def test_no_command_exits():
    with pytest.raises(SystemExit):
        cli.main([])
