"""The playspec's state: what the init leaves, and what a play call does with it."""

import pytest

from pyfuturecomposer import FutureComposerPlayer
from pyfuturecomposer import constants as c
from types import SimpleNamespace

from pyfuturecomposer import FutureComposerParseError
from pyfuturecomposer.player import _stray, binding, initial, play_variables, refusal

from .test_synthetic import _NOTE_PATTERN, _build

NOTE = 0x0C


def _play(song, frames=1):
    player = FutureComposerPlayer(song)
    for _ in range(frames):
        player.play_frame()
    return player


def test_initial_values_are_the_work_area_bytes_by_voice():
    view = bytearray(0x10000)
    work = 0x0300
    for x in range(3):
        view[work + c.VOICE_BYTES["dur"] + x] = 10 + x
        view[work + c.VOICE_WORDS["freq"][0] + x] = 0x34 + x
        view[work + c.VOICE_WORDS["freq"][1] + x] = 0x12
    view[work + c.SHARED_BYTES["route"]] = 0xB0
    view[work + c.SHARED_WORDS["slide_rate"][0]] = 0x30
    view[work + c.SHARED_WORDS["slide_rate"][1]] = 0x02
    view[0x1AF8] = 6
    view[0x41] = 3
    got = initial(bytes(view), work, 0x1AF8, 0x41)
    assert got["init_dur"] == [10, 11, 12]
    assert got["init_freq"] == [0x1234, 0x1235, 0x1236]
    assert got["init_route"] == 0xB0
    assert got["init_slide_rate"] == 0x0230
    assert got["init_slide_delay"] == 6
    assert got["init_arp_scratch"] == 3


def test_binding_places_the_tables_and_reads_the_init_values():
    song = _build(0x00, _NOTE_PATTERN)
    values = binding(song)
    assert values["has_state"]
    assert values["seq_lo"] == song.load + c.OFF_SEQ_LO
    assert values["init_route"] == 0xB0
    assert "work" not in values and "voices" not in values


def test_every_play_variable_is_spec_state():
    player = _play(_build(0x00, _NOTE_PATTERN))
    names = [name for name, _ in play_variables(0, lambda _addr: 0)]
    voice = len(c.VOICE_BYTES) + len(c.VOICE_WORDS)
    assert (
        len(names)
        == len(set(names))
        == 3 * voice + len(c.SHARED_BYTES) + len(c.SHARED_WORDS)
    )
    assert all(isinstance(player.state(name), int) for name in names)


def test_the_tempo_counts_down_to_a_row_and_reloads_the_speed():
    player = FutureComposerPlayer(_build(0x00, _NOTE_PATTERN))
    seen = []
    for _ in range(6):
        player.play_frame()
        seen.append(player.state("countdown"))
    assert seen == [1, 0, 1, 0, 1, 0]


def test_a_note_sets_the_key_the_duration_and_the_pitch():
    pattern = (c.DUR_MIN | 4, c.INSTR_MIN | 0, NOTE, c.PATTERN_END)
    player = _play(_build(0x00, pattern))
    for x in range(3):
        assert player.state(f"voice[{x}].key") == NOTE
        assert player.state(f"voice[{x}].dur") == 4
        assert player.state(f"voice[{x}].left") == 4
        assert player.state(f"voice[{x}].instr") == 0


def test_the_pattern_end_moves_the_orderlist_on_once_the_repeats_are_played():
    seq = (c.SEQ_REPEAT | 1, 0x00, 0x00, 0xFF)
    song = _build(0x00, _NOTE_PATTERN, seq=seq)
    player = FutureComposerPlayer(song)
    positions = []
    for _ in range(40):
        player.play_frame()
        positions.append(player.state("voice[0].seqpos"))
    assert positions[0] == 1
    assert sorted(set(positions)) == [1, 2, 3]
    assert positions.index(2) < positions.index(3)


def test_a_slide_command_sets_the_rate_delay_and_direction():
    pattern = (c.PORTA_MIN | 5, 0x35, c.INSTR_MIN | 0, NOTE, c.PATTERN_END)
    player = _play(_build(0x00, pattern))
    assert player.state("slide_rate") == (5 >> 1 & 7) << 8 | 0x30
    assert player.state("slide_delay") == 5
    assert player.state("voice[0].slide") == 2
    even = _play(
        _build(0x00, (c.PORTA_MIN | 4, 0x35, c.INSTR_MIN | 0, NOTE, c.PATTERN_END))
    )
    assert even.state("voice[0].slide") == 1


@pytest.mark.parametrize("first", [c.INSTR_MIN | 1, c.PORTA_MIN | 1, c.ROWMARK_MIN | 1])
def test_a_byte_that_cannot_follow_an_instrument_is_the_note(first):
    pattern = (c.INSTR_MIN | 0, first, c.PATTERN_END)
    player = _play(_build(0x00, pattern))
    assert player.state("voice[0].key") == first
    assert player.state("voice[0].instr") == 0


@pytest.mark.parametrize("second,ctrl", [((c.ROWMARK_MIN | 0,), 0x40), ((), 0x41)])
def test_a_row_marker_plays_a_note_without_restarting_the_instrument(second, ctrl):
    first = (c.DUR_MIN | 8, c.INSTR_MIN | 0, NOTE)
    song = _build(0x00, first + second + (NOTE + 2, c.PATTERN_END))
    player = FutureComposerPlayer(song)
    player.play_frame()
    while player.state("voice[0].key") == NOTE:
        player.play_frame()
    assert player.state("voice[0].key") == NOTE + 2
    assert player.state("voice[0].ctrl") == ctrl


def test_the_gate_opens_with_the_note_and_closes_on_the_next_row():
    player = FutureComposerPlayer(
        _build(0x00, (c.DUR_MIN | 8, c.INSTR_MIN | 0, NOTE, c.PATTERN_END))
    )
    player.play_frame()
    assert player.state("voice[0].ctrl") == 0x41
    for _ in range(3):
        player.play_frame()
    assert player.state("voice[0].ctrl") == 0x40


def test_state_one_restarts_the_voices_and_clears_itself():
    player = FutureComposerPlayer(_build(0x00, _NOTE_PATTERN))
    for _ in range(5):
        player.play_frame()
    player.set_state("play_state", 1)
    writes = player.play_frame()
    assert not writes or all(reg != 0x18 for reg, _ in writes)
    assert player.state("play_state") == 0
    assert player.state("voice[0].patpos") == 0
    assert player.state("voice[0].key") == 0
    for _ in range(3):
        player.play_frame()
    assert player.state("voice[0].key") == NOTE


def test_state_two_silences_every_call():
    player = FutureComposerPlayer(_build(0x00, _NOTE_PATTERN))
    player.play_frame()
    player.set_state("play_state", 2)
    assert not player.play_frame()
    assert player.finished


def _variant(work, tempo, voice_base, found):
    resolved = SimpleNamespace(work=work, tempo=tempo, voice_base=voice_base, pw_step=0)
    return SimpleNamespace(
        resolve=lambda: resolved,
        source=lambda _name: SimpleNamespace(kind="detected" if found else "default"),
    )


@pytest.mark.parametrize("table", ["tempo", "voice_base"])
def test_a_work_area_over_the_speed_or_voice_base_table_is_refused(table):
    song = _build(0x00, _NOTE_PATTERN)
    tables = {"tempo": 0x6E8, "voice_base": 0x6E9}
    tables[table] = 0x27D - song.load
    why = refusal(song, _variant(0x278, tables["tempo"], tables["voice_base"], True))
    assert why == f"the work area at $0278 overlaps the {table} table"
    assert refusal(song, _variant(0x278, 0x6E8, 0x6E9, True)) is None


def test_a_play_routine_that_does_not_start_at_the_entry_is_refused():
    song = _build(0x00, _NOTE_PATTERN)
    assert refusal(song, _variant(0x278, 0x6E8, 0x6E9, False), song.play) is None
    assert "does not start" in refusal(
        song, _variant(0x278, 0x6E8, 0x6E9, False), song.play + 0x200
    )
    assert refusal(song, _variant(0x278, 0x6E8, 0x6E9, True), song.play + 0x200) is None
    with pytest.raises(FutureComposerParseError, match="work area"):
        binding(song, found=_variant(0x1800 + 0x6E8, 0x6E8, 0x6E9, True))


def test_a_pulse_program_row_past_the_table_reads_the_variable_it_lies_over():
    song = _build(0x00, _NOTE_PATTERN)
    resolved = SimpleNamespace(work=song.load + 0x100 - 0x36, pw_step=0x100 - 0xFC)
    assert _stray(song, resolved) == [1, 2, 3, 4]
    assert _stray(song, SimpleNamespace(work=0x4000, pw_step=0x100)) == [0, 0, 0, 0]
