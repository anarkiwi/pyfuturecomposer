"""Read, play, and render Future Composer (MoN / Deenen) SID songs."""

from pyfuturecomposer.audio import render_samples, render_wav, write_wav
from pyfuturecomposer.errors import FutureComposerError, SidParseError
from pyfuturecomposer.model import Song
from pyfuturecomposer.player import Player, iter_frames, render_grid
from pyfuturecomposer.reader import FutureComposerSidParser, parse, read
from pyfuturecomposer.reglog import (
    RegWrite,
    iter_register_writes,
    read_reglog,
    write_reglog,
)
from pyfuturecomposer.writer import (
    is_editor_native,
    to_prg,
    to_sid,
    write_prg,
    write_sid,
)

__version__ = "0.1.0"

__all__ = [
    "FutureComposerError",
    "FutureComposerSidParser",
    "Player",
    "RegWrite",
    "SidParseError",
    "Song",
    "__version__",
    "is_editor_native",
    "iter_frames",
    "iter_register_writes",
    "parse",
    "read",
    "read_reglog",
    "render_grid",
    "render_samples",
    "render_wav",
    "to_prg",
    "to_sid",
    "write_prg",
    "write_reglog",
    "write_sid",
    "write_wav",
]
