"""SID register write logs (the shared py* register-surface convention).

A register log is the player's output flattened to timed chip writes: one
:class:`~pysidtracker.reglog.RegWrite` per SID register write, with an absolute
clock in C64 CPU cycles.  The :class:`RegWrite` container plus the
``read_reglog`` / ``write_reglog`` text (de)serializers and the per-frame
``frame_writes`` framing loop are the shared :mod:`pysidtracker.reglog` surface,
re-exported here; :func:`iter_register_writes` is the Future Composer wrapper that
feeds the player's per-frame writes through that framer.
"""

from typing import Iterator

from pysidtracker.reglog import (  # re-exported shared register-log surface
    DEFAULT_WRITE_SPACING,
    REGLOG_HEADER,
    RegWrite,
    frame_writes,
    read_reglog,
    write_reglog,
)

from pyfuturecomposer import constants
from pyfuturecomposer.errors import FutureComposerError
from pyfuturecomposer.model import Song
from pyfuturecomposer.player import iter_frames

__all__ = [
    "DEFAULT_WRITE_SPACING",
    "REGLOG_HEADER",
    "RegWrite",
    "frame_writes",
    "iter_register_writes",
    "read_reglog",
    "write_reglog",
]


def iter_register_writes(
    song: Song,
    max_frames: int = 50 * 60,
    cycles_per_frame: int = constants.PAL_CYCLES_PER_FRAME,
    write_spacing: int = DEFAULT_WRITE_SPACING,
) -> Iterator[RegWrite]:
    """Yield :class:`RegWrite` for ``song``, frame by frame.

    The Future Composer player loops forever, so ``max_frames`` bounds the log
    (default one minute at 50 Hz).  The player already yields ``0..24`` register
    offsets, so the per-frame writes go straight through the shared
    :func:`~pysidtracker.reglog.frame_writes` framer (``sid_reg_base=0``): writes
    within a frame are spaced ``write_spacing`` cycles apart and frames are
    ``cycles_per_frame`` apart -- the same framing the ``deplayroutine`` oracle
    uses, so the two are byte-comparable.
    """
    if write_spacing * constants.SID_REG_COUNT >= cycles_per_frame:
        raise FutureComposerError("write_spacing too large for one frame")
    yield from frame_writes(
        iter_frames(song, max_frames=max_frames),
        cycles_per_frame=cycles_per_frame,
        write_spacing=write_spacing,
        sid_reg_base=0,
        reg_count=constants.SID_REG_COUNT,
    )
