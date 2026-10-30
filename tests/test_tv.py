"""Translation validation: spec routines against the reference tune's 6502 code."""

import pytest
import z3
from pysidtracker.playspec import parse
from pysidtracker.playspec.tv import replay, validate

from pyfuturecomposer import layout, read
from pyfuturecomposer.player import binding, spec, spec_source

REINIT = ("clock.reinit", 0x1D74)
COLD_INIT = ("clock.cold_init", 0x1D65)
NOTE_ROW = 0x193A
VOICE_INDEX = 0xFF
ROW_RETURN = 0x1D35
SEED_ADDRESS = 0x02C9


@pytest.fixture(name="reference")
def reference_fixture(tune_path):
    song = read(tune_path.read_bytes())
    image = bytes(layout.song_image(song).window(0, 0x10000))
    return binding(song), image


def test_reinit_equals_the_6502_routine(reference):
    values, image = reference
    routine, pc = REINIT
    result = validate(spec(), values, routine, image, pc)
    assert result.proven, result.counterexample


@pytest.mark.parametrize("voice", range(3))
def test_note_row_equals_the_6502_stretch(reference, voice):
    values, image = reference
    result = validate(
        spec(),
        values,
        f"voice[{voice}].tv_note_row",
        image,
        NOTE_ROW,
        registers={"X": voice},
        stop=ROW_RETURN,
        assume=[lambda mem, _regs: mem[z3.BitVecVal(VOICE_INDEX, 16)] == voice],
    )
    assert result.proven, result.counterexample


@pytest.mark.oracle
def test_cold_init_equals_the_6502_routine(reference):
    values, image = reference
    routine, pc = COLD_INIT
    result = validate(spec(), values, routine, image, pc)
    assert result.proven, result.counterexample


@pytest.mark.oracle
def test_a_wrong_seed_is_refuted_and_replays(reference):
    values, image = reference
    routine, pc = COLD_INIT
    broken = parse(spec_source().replace("c9 := 0xB0;", "c9 := 0xB1;"))
    result = validate(broken, values, routine, image, pc)
    assert not result.proven
    assert result.counterexample["address"] == SEED_ADDRESS
    memory = result.counterexample["memory"]
    assert replay(broken, values, routine, memory, pc) == [SEED_ADDRESS]
