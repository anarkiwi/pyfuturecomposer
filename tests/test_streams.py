"""Song-stream grammar tests: what parses, what the player does with it, and
that docs/format.md's byte tables describe the grammar."""

import re
from dataclasses import replace
from pathlib import Path

import pytest

from pyfuturecomposer import (
    FutureComposerSidParser,
    FutureComposerParseError,
    FutureComposerPlayer,
    SidParseError,
    parse,
    to_prg,
    to_sid,
)
from pyfuturecomposer import constants as c
from pyfuturecomposer.formats import FORMAT
from pyfuturecomposer.streams import GRAMMAR, Instrument, streams

from .test_synthetic import LOAD, _NOTE_PATTERN, _build

DOCS = Path(__file__).resolve().parent.parent / "docs" / "format.md"


def _sequence(*data):
    return GRAMMAR.parse_exact(bytes(data), "sequence")


def _pattern(*data):
    return GRAMMAR.parse_exact(bytes(data), "pattern")


def test_sequence_steps_and_loop():
    seq = _sequence(0x82, 0x43, 0x05, 0x06, c.SEQ_LOOP)
    assert seq.steps == (
        ("transpose", 2),
        ("repeat", 3),
        ("pattern", 5),
        ("pattern", 6),
    )
    assert seq.loops
    assert not _sequence(0x00, c.SEQ_END).loops


@pytest.mark.parametrize(
    "data",
    [
        (c.SEQ_LOOP,),
        (0x81, 0x41, c.SEQ_LOOP),
        (0x00,),
    ],
)
def test_sequence_the_player_cannot_walk_is_rejected(data):
    with pytest.raises(FutureComposerParseError):
        _sequence(*data)


def test_a_voice_may_end_the_song_without_naming_a_pattern():
    seq = _sequence(c.SEQ_END)
    assert seq.steps == () and not seq.loops
    song = _build(0x00, _NOTE_PATTERN, seq=(c.SEQ_END,))
    assert any(kind == "sequence" for _, _, kind in streams(song))
    player = FutureComposerPlayer(song)
    player.play_frame()
    assert player.finished


def test_grammar_and_player_agree_on_a_sequence_without_a_pattern():
    seq = (c.SEQ_TRANSPOSE | 1,) * 5 + (c.SEQ_LOOP,)
    song = _build(0x00, _NOTE_PATTERN, seq=seq)
    with pytest.raises(FutureComposerParseError):
        list(streams(song))
    with pytest.raises(FutureComposerParseError):
        FutureComposerPlayer(song).play_frame()


def test_pattern_commands():
    pat = _pattern(0xC1, 0x85, 0xE3, 0x12, 0x0C, 0xF0, 0x30, 0xFF)
    assert pat.commands == (
        ("instr", (1,)),
        ("duration", (5,)),
        ("slide", (3, 0x12)),
        ("note", (0x0C,)),
        ("row", (0, 0x30)),
    )
    assert pat.instruments == (1,)


def test_pattern_may_begin_with_a_row_marker_ff():
    assert _pattern(0xFF, 0x87, 0x0C, 0xFF).commands[0] == ("row", (15, 0x87))


@pytest.mark.parametrize("data", [(), (0xFF,), (0x0C,), (0xE1, 0x00)])
def test_unterminated_pattern_is_rejected(data):
    with pytest.raises(FutureComposerParseError):
        _pattern(*data)


def test_stream_tail_is_never_read():
    assert (
        GRAMMAR.parse_prefix(bytes((0x00, c.SEQ_END, 0xFF, 0xFF)), "sequence").size == 2
    )
    assert GRAMMAR.parse_prefix(bytes((0x0C, 0xFF, 0x00)), "pattern").size == 2


def test_instrument_record():
    record = GRAMMAR.parse_exact(bytes(range(1, 9)), "instrument")
    assert record == Instrument(1, 2, 3, 4, 5, 6, 7, 8)
    assert record.to_bytes() == bytes(range(1, 9))
    with pytest.raises(FutureComposerParseError):
        GRAMMAR.parse_exact(bytes(7), "instrument")


def test_streams_of_a_synthetic_song():
    song = _build(0x00, _NOTE_PATTERN)
    found = {name: model for name, model, _ in streams(song)}
    assert found["voice 0 sequence"].patterns == (0,)
    assert found["pattern 0"].commands == (
        ("instr", (0,)),
        ("note", (0x0C,)),
    )
    assert found["instrument 0"].master_ctrl == 0x00


def test_streams_round_trip_through_the_grammar():
    song = _build(0x00, _NOTE_PATTERN)
    GRAMMAR.check(streams(song), FutureComposerParseError)


def test_read_rejects_a_malformed_stream_unless_validation_is_off():
    song = _build(0x00, _NOTE_PATTERN, seq=(c.SEQ_LOOP,))
    data = to_sid(song)
    with pytest.raises(SidParseError):
        parse(data)
    assert parse(data, validate=False).image == song.image
    assert FutureComposerSidParser().parse(data).image == song.image


def test_bare_prg_streams_are_read_from_the_loaded_image():
    song = _build(0x00, _NOTE_PATTERN)
    bare = parse(to_prg(song))
    assert [m for _, m, _ in streams(bare)] == [m for _, m, _ in streams(song)]


def test_format_lists_the_grammar():
    song = _build(0x00, _NOTE_PATTERN)
    lines = list(FORMAT.listing(song))
    assert "pattern 0:" in lines
    assert any("instr INSTR=$c0" in line for line in lines)


def test_reference_tune_streams(tune_path):
    song = parse(tune_path.read_bytes())
    GRAMMAR.check(streams(song), FutureComposerParseError)


def _doc_rows(heading):
    """``(first, last, meaning)`` rows of the table after ``heading``'s intro."""
    text = DOCS.read_text(encoding="utf-8")
    block = text.split(heading, 1)[1].split("\n\n")
    rows = []
    for table in block:
        for line in table.splitlines():
            m = re.match(
                r"\| `\$([0-9A-F]{2})`(?:-`\$([0-9A-F]{2})`)? \| (.*) \|", line
            )
            if m:
                lo = int(m.group(1), 16)
                rows.append((lo, int(m.group(2) or m.group(1), 16), m.group(3)))
        if rows:
            break
    return rows


def _kind(rule, byte):
    if rule == "sequence":
        data = bytes((0x00, byte, c.SEQ_LOOP)) if byte < 0xFE else bytes((0x00, byte))
        steps = GRAMMAR.parse_prefix(data, "sequence").model
        return steps
    return GRAMMAR.parse_prefix(bytes((byte, 0, 0, 0xFF)), "pattern").model


def test_documented_sequence_bytes_match_the_grammar():
    rows = _doc_rows("| Sequence byte |")
    covered = sorted(b for lo, hi, _ in rows for b in range(lo, hi + 1))
    assert covered == list(range(256))
    for lo, hi, meaning in rows:
        for byte in range(lo, hi + 1):
            if byte >= 0xFE:
                model = _kind("sequence", byte)
                assert model.loops == (byte == 0xFF)
                continue
            kind = _kind("sequence", byte).steps[-1]
            expect = (
                "pattern"
                if "play pattern" in meaning
                else "repeat" if "repeat" in meaning else "transpose"
            )
            assert kind[0] == expect, hex(byte)


def test_documented_pattern_bytes_match_the_grammar():
    rows = _doc_rows("| Pattern byte |")
    covered = sorted(b for lo, hi, _ in rows for b in range(lo, hi + 1))
    assert covered == list(range(256))
    names = {
        "note index": "note",
        "note duration": "duration",
        "select instrument": "instr",
        "slide command": "slide",
        "row marker": "row",
    }
    for lo, hi, meaning in rows:
        if meaning == "end of pattern":
            with pytest.raises(FutureComposerParseError):
                _pattern(0xFF)
            continue
        want = next(v for k, v in names.items() if meaning.startswith(k))
        for byte in range(lo, hi + 1):
            assert _kind("pattern", byte).commands[0][0] == want, hex(byte)


def _frames_until_finished(song, limit=400):
    player = FutureComposerPlayer(song)
    for frame in range(limit):
        player.play_frame()
        if player.finished:
            return frame
    raise AssertionError("song never ended")


def test_repeat_step_plays_the_next_pattern_that_many_extra_times():
    end = c.SEQ_END
    once = _frames_until_finished(_build(0x00, _NOTE_PATTERN, seq=(0x00, end)))
    twice = _frames_until_finished(_build(0x00, _NOTE_PATTERN, seq=(0x00, 0x00, end)))
    repeated = _frames_until_finished(
        _build(0x00, _NOTE_PATTERN, seq=(c.SEQ_REPEAT | 2, 0x00, end))
    )
    assert twice > once
    assert repeated - once == 2 * (twice - once)


def test_transpose_step_adds_its_low_five_bits_to_the_note_index():
    def first_pitch(seq):
        song = _build(0x00, _NOTE_PATTERN, seq=seq)
        img = bytearray(song.image)
        for note in range(0x40):
            img[c.OFF_FREQ_LO + note] = note
            img[c.OFF_FREQ_HI + note] = 0x80 | note
        player = FutureComposerPlayer(replace(song, image=bytes(img)))
        player.play_frame()
        return player.regs[0]

    assert first_pitch((0x00, c.SEQ_LOOP)) == 0x0C
    assert first_pitch((c.SEQ_TRANSPOSE | 3, 0x00, c.SEQ_LOOP)) == 0x0F
    assert first_pitch((c.SEQ_TRANSPOSE | 0x23, 0x00, c.SEQ_LOOP)) == 0x0F


def test_tables_in_the_io_area_are_not_readable_as_ram():
    base = _build(0x00, _NOTE_PATTERN)
    song = replace(base, load=0xD000, init=0xD000, play=0xD006)
    with pytest.raises(FutureComposerParseError, match="I/O area"):
        list(streams(song))


def test_spec_player_checks_every_stream_kind_it_opens(tune_path):
    player = FutureComposerPlayer(parse(tune_path.read_bytes()), validate=True)
    for _ in range(300):
        player.play_frame()
    opened = {ref.rsplit(":", 1)[1] for ref, _base in player.validator.results}
    assert opened == {"sequence", "pattern", "instrument"}
    assert not player.validator.failures()


def test_unterminated_pattern_is_rejected_unless_validation_is_off():
    song = _build(0x00, (0x0C,) * 0x100)
    FutureComposerPlayer(song, validate=False).play_frame()
    with pytest.raises(FutureComposerParseError, match="pattern"):
        FutureComposerPlayer(song).play_frame()


def test_the_frame_ends_when_a_voice_ends_the_song():
    song = _build(0x00, _NOTE_PATTERN)
    img = bytearray(song.image)
    end = 0x6F2 + 0x10
    img[end] = c.SEQ_END
    img[c.OFF_SEQ_LO + 2] = (LOAD + end) & 0xFF
    img[c.OFF_SEQ_HI + 2] = (LOAD + end) >> 8
    player = FutureComposerPlayer(replace(song, image=bytes(img)))
    player.play_frame()
    assert player.finished
    assert not any(player.regs[:0x18])
