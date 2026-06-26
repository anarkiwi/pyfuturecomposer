"""Read, play, and render Future Composer (MoN / Deenen) SID songs."""

from pyfuturecomposer.audio import render_samples, render_wav, write_wav
from pyfuturecomposer.errors import FutureComposerError, SidParseError
from pyfuturecomposer.model import Song
from pyfuturecomposer.player import Player, iter_frames, render_grid
from pyfuturecomposer.reader import parse, read
from pyfuturecomposer.reglog import (
    RegWrite,
    iter_register_writes,
    read_reglog,
    write_reglog,
)

__version__ = "0.1.0"

__all__ = [
    "FutureComposerError",
    "Player",
    "RegWrite",
    "SidParseError",
    "Song",
    "__version__",
    "iter_frames",
    "iter_register_writes",
    "parse",
    "read",
    "read_reglog",
    "render_grid",
    "render_samples",
    "render_wav",
    "write_reglog",
    "write_wav",
]
