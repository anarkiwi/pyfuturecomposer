"""Writer tests: Song -> editor-loadable .prg / PSID round-trip."""

import struct

from pyfuturecomposer import (
    Song,
    is_editor_native,
    parse,
    read,
    to_prg,
    to_sid,
    write_prg,
    write_sid,
)


def _song(image=b"\x01\x02\x03\x04", load=0x1800, init=0x1800, play=0x1806, **kw):
    return Song(image=image, load=load, init=init, play=play, **kw)


def test_to_prg_is_load_word_plus_image():
    song = _song(load=0x1800)
    assert to_prg(song) == b"\x00\x18" + song.image


def test_to_prg_relocated_load_word():
    assert to_prg(_song(load=0x10F0)) == b"\xf0\x10" + b"\x01\x02\x03\x04"


def test_prg_round_trips_load_and_image():
    song = _song(image=bytes(range(64)), load=0x1800)
    back = parse(to_prg(song))
    assert back.load == song.load
    assert back.image == song.image
    assert back.init == song.init  # init = load
    assert back.play == song.play  # play = load + 6


def test_sid_round_trips_model():
    song = _song(
        image=bytes(range(32)),
        load=0x1800,
        init=0x1800,
        play=0x1806,
        name="Tune",
        author="Composer",
        released="1989 Group",
    )
    back = parse(to_sid(song))
    assert back == song


def test_sid_header_is_valid_psid():
    data = to_sid(_song())
    assert data[:4] == b"PSID"
    assert struct.unpack(">H", data[4:6])[0] == 2  # version
    assert struct.unpack(">H", data[6:8])[0] == 0x7C  # data offset


def test_sid_truncates_overlong_metadata():
    song = _song(name="x" * 100)
    back = parse(to_sid(song))
    assert back.name == "x" * 31


def test_is_editor_native():
    assert is_editor_native(_song(load=0x1800, play=0x1806))
    assert not is_editor_native(_song(load=0x1000, play=0x1006))
    assert not is_editor_native(_song(load=0x1800, play=0x1803))


def test_write_prg_and_sid_files(tmp_path):
    song = _song(name="File", author="Me")
    prg = tmp_path / "out.prg"
    sid = tmp_path / "out.sid"
    write_prg(song, prg)
    write_sid(song, sid)
    assert prg.read_bytes() == to_prg(song)
    assert read(sid) == song


def test_tune_prg_round_trip(tune_path):
    song = read(tune_path)
    back = parse(to_prg(song))
    assert back.load == song.load
    assert back.image == song.image


def test_tune_sid_round_trip(tune_path):
    song = read(tune_path)
    assert parse(to_sid(song)) == song
