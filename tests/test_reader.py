"""Reader tests: PSID/PRG container parsing into a Song."""

import struct

import pytest

from pyfuturecomposer import SidParseError, parse, read


def _psid(image: bytes, load=0x1800, init=0x1800, play=0x1806) -> bytes:
    header = struct.pack(">4sHHHHHHHI", b"PSID", 2, 0x7C, load, init, play, 1, 0, 0)
    header += b"\0" * (0x7C - len(header))
    return header + image


def test_parse_psid_metadata():
    song = parse(_psid(b"\x00" * 64))
    assert song.load == 0x1800
    assert song.init == 0x1800
    assert song.play == 0x1806
    assert song.byte(0x1800) == 0


def test_parse_prg_load_address():
    song = parse(b"\x00\x10" + b"\xAB\xCD")
    assert song.load == 0x1000
    assert song.init == 0x1000  # init = load
    assert song.play == 0x1006  # play = load + 6
    assert song.byte(0x1000) == 0xAB
    assert song.byte(0x1001) == 0xCD


def test_parse_embedded_load_address():
    # data_off load field 0 -> load is the first 2 body bytes.
    header = struct.pack(">4sHHHHHHHI", b"PSID", 2, 0x7C, 0, 0, 0, 1, 0, 0)
    header += b"\0" * (0x7C - len(header))
    song = parse(header + b"\x00\x18" + b"\x42")
    assert song.load == 0x1800
    assert song.byte(0x1800) == 0x42


def test_byte_out_of_range_is_zero():
    song = parse(b"\x00\x18" + b"\x11")
    assert song.byte(0x1800) == 0x11
    assert song.byte(0x9999) == 0


def test_truncated_header_raises():
    with pytest.raises(SidParseError):
        parse(b"PSID\x00")


def test_truncated_prg_raises():
    with pytest.raises(SidParseError):
        parse(b"\x00")


def test_read_tune_file(tune_path):
    song = read(tune_path)
    assert song.load == 0x1800
    assert song.play == song.load + 6
    assert len(song.image) > 0
    assert song.name  # the PSID header carries a title
