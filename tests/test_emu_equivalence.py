"""The spec-driven player against the tune's own 6502 play routine."""

from pysidtracker import EmuPlayer

from pyfuturecomposer import FutureComposerPlayer, read

FRAMES = 800
STACK = range(0x100, 0x200)


def test_memory_equals_the_tune_6502_run(tune_path):
    song = read(tune_path.read_bytes())
    player = FutureComposerPlayer(song)
    reference = EmuPlayer(song.image, song.load, song.init, song.play)
    for frame in range(FRAMES):
        assert player.play_frame() == reference.play_frame(), frame
        ours, theirs = player.memory, bytes(
            reference._mem
        )  # pylint: disable=protected-access
        differing = [
            a for a in range(0x10000) if ours[a] != theirs[a] and a not in STACK
        ]
        assert not differing, (frame, [hex(a) for a in differing[:8]])
