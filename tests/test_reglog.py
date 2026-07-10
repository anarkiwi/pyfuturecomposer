"""Register-log tests: the shared py* register-surface convention."""

import io

import pytest
from pysidtracker import SidParseError

from pyfuturecomposer import (
    FutureComposerError,
    RegWrite,
    iter_register_writes,
    read,
    read_reglog,
    write_reglog,
)


def test_iter_register_writes_surface(tune_path):
    song = read(tune_path)
    writes = list(iter_register_writes(song, max_frames=16))
    assert writes
    assert all(isinstance(w, RegWrite) for w in writes)
    assert all(0 <= w.reg < 25 and 0 <= w.val <= 0xFF for w in writes)
    # clocks are non-decreasing
    assert all(b.clock >= a.clock for a, b in zip(writes, writes[1:]))


def test_reglog_round_trip(tune_path):
    song = read(tune_path)
    writes = list(iter_register_writes(song, max_frames=8))
    buf = io.StringIO()
    write_reglog(writes, buf)
    buf.seek(0)
    back = read_reglog(buf)
    assert back == writes


def test_reglog_path_round_trip(tmp_path, tune_path):
    song = read(tune_path)
    writes = list(iter_register_writes(song, max_frames=8))
    path = tmp_path / "log.txt"
    write_reglog(writes, path)
    assert read_reglog(path) == writes


def test_reglog_rejects_bad_line():
    with pytest.raises(SidParseError):
        read_reglog(io.StringIO("1 2\n"))


def test_reglog_rejects_non_int():
    with pytest.raises(SidParseError):
        read_reglog(io.StringIO("a b c\n"))


def test_reglog_skips_comments_and_blanks():
    text = "# header\n\n100 4 200  # inline\n"
    assert read_reglog(io.StringIO(text)) == [RegWrite(100, 4, 200)]


def test_reglog_write_spacing_guard(tune_path):
    song = read(tune_path)
    with pytest.raises(FutureComposerError):
        list(iter_register_writes(song, max_frames=1, write_spacing=10000))


def test_read_reglog_bad_type():
    with pytest.raises(TypeError):
        read_reglog(12345)
