"""Write a :class:`Song` back into a form Future Composer can load.

Future Composer carries its driver code and authored data (sequences, patterns,
instruments and the modulation tables) INLINE in a single C64 memory image; the
editor's native module is exactly that image saved as a plain C64 program -- a
two-byte little-endian load address followed by the driver+data bytes.  A
canonical build loads at ``$1800`` (init ``$1800`` / play ``$1806``);
:func:`to_prg` emits precisely this, so a canonical tune round-trips straight
back into the FutureComposer editor.

:func:`to_sid` re-wraps the same image in a PSID container, preserving the
load/init/play entry points and the ``name``/``author``/``released`` metadata so
``read(to_sid(song))`` reconstructs an equal :class:`Song` and HVSC players still
play it.  A relocated rip (load other than ``$1800``) is emitted verbatim at its
own load address: it is a valid C64 program and round-trips through
:func:`~pyfuturecomposer.reader.read`, but only the canonical ``$1800`` build
loads directly into the editor (:func:`is_editor_native`).
"""

from pathlib import Path

from pysidtracker import load_prefix, write_psid

from pyfuturecomposer import constants
from pyfuturecomposer.model import Song

# Canonical FutureComposer editor module: driver at $1800, play at $1806.
EDITOR_LOAD = 0x1800

# Longest PSID header string (a 32-byte field with its NUL terminator).
_STR_MAX = 31


def is_editor_native(song: Song) -> bool:
    """True if ``song`` is the canonical build the FC editor loads directly.

    The editor expects the driver at :data:`EDITOR_LOAD` with ``play = load + 6``
    (:data:`~pyfuturecomposer.constants.DEFAULT_PLAY_OFFSET`); a relocated rip
    still writes a valid C64 program but will not load back into the editor.
    """
    return (
        song.load == EDITOR_LOAD
        and song.play - song.load == constants.DEFAULT_PLAY_OFFSET
    )


def to_prg(song: Song) -> bytes:
    """Serialize ``song`` as a C64 program image (the FC editor's native module).

    The two-byte little-endian load address followed by the driver code and
    inline song tables exactly as they sit in C64 memory.
    """
    return load_prefix(song.load) + song.image


def write_prg(song: Song, path) -> None:
    """Write :func:`to_prg` output for ``song`` to ``path``."""
    Path(path).write_bytes(to_prg(song))


def to_sid(song: Song) -> bytes:
    """Serialize ``song`` as a PSID v2 container (round-trips through ``read``).

    The load address is embedded in the first two body bytes, matching HVSC;
    metadata longer than a header field (31 characters) is truncated.
    """
    return write_psid(
        load=song.load,
        init=song.init,
        play=song.play,
        image=song.image,
        name=song.name[:_STR_MAX],
        author=song.author[:_STR_MAX],
        released=song.released[:_STR_MAX],
        embed_load=True,
    )


def write_sid(song: Song, path) -> None:
    """Write :func:`to_sid` output for ``song`` to ``path``."""
    Path(path).write_bytes(to_sid(song))
