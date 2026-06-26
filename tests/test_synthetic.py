"""Synthetic-image tests driving the modulation-engine branches.

The representative tune exercises the core note / instrument / pulse-width /
slide paths; these synthetic FC images craft instrument modulation-control bytes
($1f28 master-control flags) to drive the remaining per-frame engine branches --
the wave-program walk ($02ac & 0x10), the arp-delay table ($02ac & 4), the
filter-cutoff program ($02ac & 1), the $E0 portamento command and the
end-of-song / hard-freq paths -- exercising the real player code with crafted DATA
(no byte-exact oracle needed; the assertion is "the engine runs and emits writes").
"""

from pyfuturecomposer import Player, Song, iter_register_writes
from pyfuturecomposer import constants as c

LOAD = 0x1800


def _blank_image() -> bytearray:
    # Cover load..$1f29 (the inline-table region) so every table read is in-image.
    img = bytearray(0x729 + c.INSTR_RECORD_SIZE * 4)
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
    player = Player(song)
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
    player = Player(song)
    for _ in range(8):
        player.play_frame()
    assert player.finished


def test_reglog_on_synthetic():
    song = _build(0x01, _NOTE_PATTERN)
    writes = list(iter_register_writes(song, max_frames=16))
    assert writes
