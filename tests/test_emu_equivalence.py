"""The Python player against the tune's own 6502 play routine."""

from pysidtracker import EmuPlayer

from pyfuturecomposer import FutureComposerPlayer, read

FRAMES = 800


def test_register_writes_equal_the_tune_6502_run(tune_path):
    song = read(tune_path.read_bytes())
    player = FutureComposerPlayer(song)
    reference = EmuPlayer(song.image, song.load, song.init, song.play)
    for frame in range(FRAMES):
        assert player.play_frame() == reference.play_frame(), frame
