"""The ``futurecomposer`` format on the shared ``pysidtracker`` CLI."""

import wave
from dataclasses import replace
from importlib.metadata import entry_points

import pytest
from pysidtracker import SidError, maincli
from pysidtracker.formats import recognize_format

from pyfuturecomposer import parse, read
from pyfuturecomposer.formats import FORMAT
from pyfuturecomposer.writer import write_prg


def _cli(argv):
    return maincli.run_cli(lambda: maincli.build_parser([FORMAT]), SidError, argv)


def test_registered_on_the_entry_point_group():
    group = entry_points(group="pysidtracker.formats")
    assert [e.load() for e in group if e.name == "futurecomposer"] == [FORMAT]


def test_recognizes_the_tune(tune_path):
    assert recognize_format([FORMAT], tune_path.read_bytes()) is FORMAT


def test_info(capsys, tune_path):
    assert _cli(["info", str(tune_path)]) == 0
    out = capsys.readouterr().out
    song = read(tune_path)
    assert f"load:     ${song.load:04X}" in out
    assert f"init:     ${song.init:04X}" in out
    assert f"play:     ${song.play:04X}" in out
    assert "format:   futurecomposer" in out
    assert f"image bytes: {len(song.image)}" in out


def test_reglog(tmp_path, tune_path):
    out = tmp_path / "log.txt"
    assert _cli(["reglog", str(tune_path), str(out), "--seconds", "0.2"]) == 0
    assert out.read_text(encoding="utf-8").strip()


def test_wav(tmp_path, tune_path):
    out = tmp_path / "out.wav"
    assert _cli(["wav", str(tune_path), str(out), "--seconds", "0.1"]) == 0
    with wave.open(str(out)) as wav:
        assert wav.getnframes() > 0


def test_reglog_error(tmp_path):
    missing = tmp_path / "nope.sid"
    assert _cli(["reglog", str(missing), str(tmp_path / "o.txt")]) == 1


def test_export_prg(capsys, tmp_path, tune_path):
    out = tmp_path / "editor.prg"
    assert _cli(["export", str(tune_path), str(out)]) == 0
    assert parse(out.read_bytes()).image == read(tune_path).image
    assert f"wrote {out} (prg)" in capsys.readouterr().out


def test_export_sid_round_trip(tmp_path, tune_path):
    out = tmp_path / "wrapped.sid"
    assert _cli(["export", str(tune_path), str(out)]) == 0
    assert read(out) == read(tune_path)


def test_export_format_override(tmp_path, tune_path):
    out = tmp_path / "module.bin"
    assert _cli(["export", str(tune_path), str(out), "--format", "sid"]) == 0
    assert read(out) == read(tune_path)


@pytest.mark.parametrize("load, noted", [(0x1800, False), (0x2000, True)])
def test_export_notes_a_relocated_rip(capsys, tmp_path, tune_path, load, noted):
    song = replace(read(tune_path), load=load, init=load, play=load + 6)
    src = tmp_path / "in.prg"
    write_prg(song, src)
    assert _cli(["export", str(src), str(tmp_path / "out.prg")]) == 0
    assert ("relocated rip" in capsys.readouterr().err) is noted


def test_no_command_exits():
    with pytest.raises(SystemExit):
        _cli([])
