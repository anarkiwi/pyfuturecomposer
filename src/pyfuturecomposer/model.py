"""The Future Composer song model.

Future Composer carries its authored data (sequences, patterns, instruments and
the modulation tables) INLINE in the module image at fixed offsets-from-load, and
the player walks that image directly every frame.  A :class:`Song` therefore holds
the loaded image bytes + the load address + the SID header metadata; the player
(:mod:`pyfuturecomposer.player`) reads the inline tables from the image as the
6502 player does, so the model stays a faithful, minimal container.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Song:
    """A parsed Future Composer tune.

    ``image`` is the raw C64 image (player code + inline song data); ``load`` is
    its load address; ``init`` / ``play`` are the player entry points (init =
    load, play = load + 6 for FC); ``name`` / ``author`` / ``released`` are the
    PSID header strings (empty for a bare ``.prg``).
    """

    image: bytes
    load: int
    init: int
    play: int
    name: str = ""
    author: str = ""
    released: str = ""

    def byte(self, addr: int) -> int:
        """Read the image byte at absolute C64 ``addr`` (0 outside the image)."""
        idx = addr - self.load
        if 0 <= idx < len(self.image):
            return self.image[idx]
        return 0
