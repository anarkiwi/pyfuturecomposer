"""The spec-driven player against the tune's own 6502 play routine."""

from pysidtracker import EmuPlayer

from pyfuturecomposer import FutureComposerPlayer, read
from pyfuturecomposer.player import play_variables

FRAMES = 800


def test_registers_and_play_variables_equal_the_tune_6502_run(tune_path):
    song = read(tune_path.read_bytes())
    player = FutureComposerPlayer(song)
    reference = EmuPlayer(song.image, song.load, song.init, song.play)
    found = player.variant.resolve()
    for frame in range(FRAMES):
        assert player.play_frame() == reference.play_frame(), frame
        differing = [
            (name, player.state(name), theirs)
            for name, theirs in play_variables(found.work, reference._rd)
            if player.state(name) != theirs
        ]
        assert not differing, (frame, differing[:4])
        assert player.state("slide_delay") == reference._rd(song.load + found.slide)
