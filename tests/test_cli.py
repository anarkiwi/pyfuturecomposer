"""The ``futurecomposer`` format on the shared ``pysidtracker`` CLI."""

import wave
from dataclasses import replace
from importlib.metadata import entry_points

import pytest
from pysidtracker import SidError, maincli
from pysidtracker.formats import recognize_format

from pyfuturecomposer import parse, read
from pyfuturecomposer.formats import FORMAT
from pyfuturecomposer.writer import to_prg, to_sid, write_prg


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


def _synthetic(tmp_path, name, pattern):
    from tests.test_synthetic import _NOTE_PATTERN, _build  # pylint: disable=C0415

    song = _build(0x00, pattern or _NOTE_PATTERN)
    path = tmp_path / name
    path.write_bytes(to_sid(song) if name.endswith(".sid") else to_prg(song))
    return path


def test_equiv_ignores_the_container(capsys, tmp_path):
    sid = _synthetic(tmp_path, "a.sid", None)
    prg = _synthetic(tmp_path, "a.prg", None)
    assert _cli(["equiv", "--format", "futurecomposer", str(sid), str(prg)]) == 0
    assert capsys.readouterr().out == ""


def test_equiv_reports_a_different_note(capsys, tmp_path):
    same = _synthetic(tmp_path, "a.sid", None)
    other = _synthetic(tmp_path, "b.sid", (0xC0, 0x0D, 0xFF))
    argv = ["equiv", "--format", "futurecomposer", str(same), str(other)]
    with pytest.raises(SystemExit) as exit_info:
        _cli(argv)
    assert exit_info.value.code == 1
    out = capsys.readouterr().out
    assert "-    note NOTE=$0c" in out and "+    note NOTE=$0d" in out


def test_snapshot_probes_follow_the_song(tmp_path):
    probes = FORMAT.snapshot_probes()
    a = parse(_synthetic(tmp_path, "a.sid", None).read_bytes())
    b = parse(_synthetic(tmp_path, "b.sid", (0xC0, 0x0D, 0xFF)).read_bytes())
    assert set(probes) == {"canonical", "prg", "sid", "variant"}
    assert probes["canonical"](a) != probes["canonical"](b)
    assert probes["prg"](a) != probes["prg"](b)
    assert probes["variant"](a) == probes["variant"](b)


def test_info_and_export_work_on_a_tune_whose_streams_do_not_parse(
    capsys, tmp_path, hvsc
):
    data = hvsc.read("MUSICIANS/T/TC/Amiga_Theme.sid")
    source = tmp_path / "amiga.sid"
    source.write_bytes(data)
    with pytest.raises(SidError):
        parse(data)
    assert _cli(["info", str(source)]) == 0
    assert "format:   futurecomposer" in capsys.readouterr().out
    out = tmp_path / "amiga.prg"
    assert _cli(["export", str(source), str(out)]) == 0
    assert out.read_bytes() == to_prg(parse(data, validate=False))
