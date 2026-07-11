"""SID register write logs (the shared py* register-surface convention).

A register log is the player's output flattened to timed chip writes: one
:class:`~pysidtracker.reglog.RegWrite` per SID register write, with an absolute
clock in C64 CPU cycles.  The :class:`RegWrite` container, the ``read_reglog`` /
``write_reglog`` text (de)serializers and the framing loop are the shared
:mod:`pysidtracker.reglog` surface, re-exported here; :func:`iter_register_writes`
drives the base :func:`~pysidtracker.reglog.register_writes_from_player` framer off
a :class:`~pyfuturecomposer.player.FutureComposerPlayer`.
"""

from typing import Iterator, Union

from pysidtracker.reglog import (  # re-exported shared register-log surface
    DEFAULT_WRITE_SPACING,
    REGLOG_HEADER,
    RegWrite,
    read_reglog,
    register_writes_from_player,
    write_reglog,
)

from pyfuturecomposer import constants
from pyfuturecomposer.model import Song
from pyfuturecomposer.player import FutureComposerPlayer

__all__ = [
    "DEFAULT_WRITE_SPACING",
    "REGLOG_HEADER",
    "RegWrite",
    "iter_register_writes",
    "read_reglog",
    "write_reglog",
]


def iter_register_writes(
    source: Union[Song, bytes, FutureComposerPlayer],
    max_frames: int = 50 * 60,
    cycles_per_frame: int = constants.PAL_CYCLES_PER_FRAME,
    write_spacing: int = DEFAULT_WRITE_SPACING,
) -> Iterator[RegWrite]:
    """Yield :class:`RegWrite` for a Future Composer song, frame by frame.

    The player loops forever, so ``max_frames`` bounds the log (default one minute
    at 50 Hz).  The post-init SID baseline is emitted at clock 0 and each frame's
    changed registers follow via the shared
    :func:`~pysidtracker.reglog.register_writes_from_player` framer, so the log is
    byte-comparable to the sidtrace oracle framing.  Raises
    :class:`~pysidtracker.SidParseError` if ``write_spacing`` overruns one frame.
    """
    player = (
        source
        if isinstance(source, FutureComposerPlayer)
        else FutureComposerPlayer(source)
    )
    return register_writes_from_player(
        player, max_frames, cycles_per_frame, write_spacing
    )
