"""Builds whose play entry is not at the header's play address play like their 6502."""

import pytest
from pysidtracker import EmuPlayer

from pyfuturecomposer import FutureComposerPlayer, layout, parse

FRAMES = 400

# header play address is not the routine: NOPs before it, a JMP trampoline patched
# by the init, a JMP past padding to an entry with no state-byte test.
BUILDS = {
    "nops": "DEMOS/UNKNOWN/Mild_part_4.sid",
    "patched_jmp": "GAMES/G-L/Holo.sid",
    "relocated": "MUSICIANS/G/Gillies_Ewen/Funky_Ride_remix.sid",
    "no_state_byte": "MUSICIANS/L/Leffty/Bangkok_Fe.sid",
}


@pytest.fixture(name="build", params=BUILDS.values(), ids=BUILDS.keys())
def build_fixture(request, hvsc):
    return parse(hvsc.read(request.param))


def test_play_chain_is_detected(build):
    found = layout.variant(build)
    assert found.source("play").kind == "detected"
    assert found.source("work").kind == "detected"


def test_registers_equal_the_tune_6502_run(build):
    player = FutureComposerPlayer(build)
    reference = EmuPlayer(build.image, build.load, build.init, build.play)
    for frame in range(FRAMES):
        assert player.play_frame() == reference.play_frame(), frame


def test_a_build_without_a_state_byte_has_no_state(hvsc):
    song = parse(hvsc.read(BUILDS["no_state_byte"]))
    assert not layout.variant(song).resolve().state
