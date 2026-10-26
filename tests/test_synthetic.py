"""Synthetic-image tests driving the modulation-engine branches.

The representative tune exercises the core note / instrument / pulse-width /
slide paths; these synthetic FC images craft instrument modulation-control bytes
($1f28 master-control flags) to drive the remaining per-frame engine branches --
the wave-program walk ($02ac & 0x10), the arp-delay table ($02ac & 4), the
filter-cutoff program ($02ac & 1), the $E0 portamento command and the
end-of-song / hard-freq paths -- exercising the real player code with crafted DATA
(no byte-exact oracle needed; the assertion is "the engine runs and emits writes").
"""

import pytest

from pyfuturecomposer import (
    FutureComposerParseError,
    FutureComposerPlayer,
    Song,
    iter_register_writes,
)
from pyfuturecomposer import constants as c

LOAD = 0x1800


def _blank_image() -> bytearray:
    # Cover load..$1f29 (the inline-table region) so every table read is in-image.
    img = bytearray(0x800)
    return img


def _put(img, off, value):
    img[off] = value & 0xFF


def _put16(img, off, addr):
    img[off] = addr & 0xFF
    img[off + 1] = (addr >> 8) & 0xFF


def _build(master_ctrl, pattern, *, seq=(0x00, 0xFF), vib_ctrl=0x00, pw_ctrl=0x00):
    """A minimal FC image: 3 voices playing pattern 0, instrument 0's mod flags."""
    img = _blank_image()
    _put(img, c.OFF_SPEED, 0x01)  # speed = 1
    for v in range(3):
        _put(img, c.OFF_VOICE_BASE + v, v * 7)
        _put(img, c.OFF_SEQ_LO + v, (LOAD + 0x6F2) & 0xFF)  # seq data at $1ef2
        _put(img, c.OFF_SEQ_HI + v, (LOAD + 0x6F2) >> 8)
    for i, b in enumerate(seq):
        _put(img, 0x6F2 + i, b)
    # pattern pointer table: pattern 0 -> $1f00 (after the tables, in-image)
    pat_addr = LOAD + 0x700
    _put16(img, c.OFF_PAT_PTR, pat_addr)
    for i, b in enumerate(pattern):
        _put(img, 0x700 + i, b)
    # instrument 0 record at $1f21: AD/SR + mod-control bytes.
    rec = c.OFF_INSTR
    _put(img, rec + c.INSTR_AD, 0x00)
    _put(img, rec + c.INSTR_SR, 0xF0)
    _put(img, rec + c.INSTR_WAVEFORM, 0x41)
    _put(img, rec + c.INSTR_VIB_CTRL, vib_ctrl)
    _put(img, rec + c.INSTR_PW_CTRL, pw_ctrl)
    _put(img, rec + c.INSTR_MASTER_CTRL, master_ctrl)
    return Song(image=bytes(img), load=LOAD, init=LOAD, play=LOAD + 6)


def _run(song, frames=24):
    player = FutureComposerPlayer(song)
    writes = []
    for _ in range(frames):
        writes.extend(player.play_frame())
    return writes


# A pattern playing instrument 0, then a held note (index 12), terminated by $ff.
_NOTE_PATTERN = (c.INSTR_MIN | 0, 0x0C, c.PATTERN_END)


def test_filter_program_branch():
    song = _build(0x01, _NOTE_PATTERN)  # 02ac & 1 -> filter program
    assert _run(song)


def test_wave_program_branch():
    song = _build(0x10, _NOTE_PATTERN)  # 02ac & 0x10 -> wave-program walk
    assert _run(song)


def test_arp_delay_branch():
    song = _build(0x04, _NOTE_PATTERN)  # 02ac & 4 -> arp-delay table
    assert _run(song)


def test_hard_freq_branch():
    song = _build(0x80, _NOTE_PATTERN)  # 02ac & 0x80 -> hard freq set
    assert _run(song)


def test_wave_arp_routing_branch():
    # vib_ctrl nonzero with 02ac & 0x40 -> the $1e79 routing table.
    song = _build(0x40, _NOTE_PATTERN, vib_ctrl=0x08)
    assert _run(song)


def test_portamento_e0_command():
    # An $E0 portamento command (with its arg byte) then a note.
    pattern = (c.PORTA_MIN | 0x01, 0x34, c.INSTR_MIN | 0, 0x0C, c.PATTERN_END)
    song = _build(0x00, pattern)
    assert _run(song)


def test_duration_token_then_note():
    pattern = (c.DUR_MIN | 0x04, c.INSTR_MIN | 0, 0x0C, c.PATTERN_END)
    song = _build(0x00, pattern)
    assert _run(song)


def test_rowmark_no_new_instrument():
    # A $f0.. row marker: the next byte is the note (no instrument reload).
    pattern = (c.INSTR_MIN | 0, 0x0C, c.ROWMARK_MIN | 0, 0x0E, c.PATTERN_END)
    song = _build(0x00, pattern)
    assert _run(song)


def test_transpose_and_repeat_sequence_ops():
    # Sequence: transpose ($80|3), repeat ($40|1), play 0, loop.
    song = _build(
        0x00,
        _NOTE_PATTERN,
        seq=(c.SEQ_TRANSPOSE | 0x03, c.SEQ_REPEAT | 0x01, 0x00, 0xFF),
    )
    assert _run(song)


def test_end_of_song_stops():
    # Sequence end-of-song ($fe) -> the player silences and stops.
    song = _build(0x00, _NOTE_PATTERN, seq=(0xFE,))
    player = FutureComposerPlayer(song)
    for _ in range(8):
        player.play_frame()
    assert player.finished


def test_reglog_on_synthetic():
    song = _build(0x01, _NOTE_PATTERN)
    writes = list(iter_register_writes(song, max_frames=16))
    assert writes


@pytest.mark.parametrize(
    "seq", [(c.SEQ_LOOP,), (c.SEQ_TRANSPOSE | 1,) * 5 + (c.SEQ_LOOP,)]
)
def test_sequence_without_pattern_raises_parse_error(seq):
    with pytest.raises(FutureComposerParseError, match="sequence"):
        _run(_build(0x00, _NOTE_PATTERN, seq=seq), frames=2)


def test_pattern_without_note_raises_parse_error():
    song = _build(0x00, _NOTE_PATTERN)
    img = bytearray(song.image) + bytes([c.DUR_MIN | 1]) * 0x100
    _put16(img, c.OFF_PAT_PTR, LOAD + len(song.image))
    with pytest.raises(FutureComposerParseError, match="pattern"):
        _run(Song(image=bytes(img), load=LOAD, init=LOAD, play=LOAD + 6), frames=2)


def _glide_onset(threshold):
    pattern = (
        c.DUR_MIN | 0x3F,
        c.PORTA_MIN | 1,
        0x30 | threshold,
        c.INSTR_MIN | 0,
        0x0C,
        c.PATTERN_END,
    )
    player = FutureComposerPlayer(_build(0x00, pattern))
    grid = player.render_grid(40)
    assert player._rd(player.a_slide) == threshold  # pylint: disable=protected-access
    onset = next(i for i, row in enumerate(grid) if row[0])
    assert grid[onset][0] == 0x100 - 0x30
    return onset


def test_slide_threshold_gates_glide():
    onsets = [_glide_onset(t) for t in (0, 3, 6)]
    assert onsets == sorted(set(onsets))


@pytest.mark.parametrize("ctrl", [0x21, 0x81])
def test_wave_program_reads_through_operand_words(ctrl):
    img = bytearray(_build(0x10, _NOTE_PATTERN).image)
    for i, addr in enumerate((LOAD + 0x780, LOAD + 0x790)):
        _put(img, c.OFF_WAVE_PROG_PTR + 4 * i, addr)
        _put(img, c.OFF_WAVE_PROG_PTR + 4 * i + 2, addr >> 8)
    img[0x780:0x790] = bytes([ctrl]) * 16
    img[0x790:0x7A0] = bytes([0x05]) * 16
    song = Song(image=bytes(img), load=LOAD, init=LOAD, play=LOAD + 6)
    grid = FutureComposerPlayer(song).render_grid(8)
    assert (0x05 + 0x0D, ctrl) in {(row[1], row[4]) for row in grid}


def test_cold_init_clears_work_area():
    load = 0x0200
    song = Song(image=b"\xaa" * 0x800, load=load, init=load, play=load + 6)
    player = FutureComposerPlayer(song)
    assert player.variant.source("play").kind == "default"
    mem = bytes(
        player._rd(a) for a in range(0x0277, 0x02DC)
    )  # pylint: disable=protected-access
    work = bytearray(c.WORK_SIZE)
    work[0x02C9 - c.WORK_BASE] = c.FILTER_ROUTE_SEED
    assert mem == b"\xaa" + bytes(work) + b"\xaa"
