"""The Future Composer play routine, run as ``specs/futurecomposer.play``.

:class:`FutureComposerPlayer` is a :class:`pysidtracker.playspec.SpecPlayer`: the
tune's own init runs on the emulated 6502, then each play call runs the spec on
the memory it left.  :mod:`pyfuturecomposer.layout` binds the spec's ``layout``
block to the addresses of the tune's build.
"""

import re
from functools import lru_cache
from importlib import resources
from typing import Dict, Union

from pysidtracker.playspec import SpecPlayer, SpecRuntimeError, parse

from pyfuturecomposer import constants, layout
from pyfuturecomposer.errors import FutureComposerParseError
from pyfuturecomposer.model import Song
from pyfuturecomposer.reader import parse as parse_song

SPEC_RESOURCE = "specs/futurecomposer.play"
TABLES = (
    "freq_lo",
    "freq_hi",
    "seq_lo",
    "seq_hi",
    "pat_ptr",
    "instr",
    "voice_base",
    "tempo",
    "pw_step",
    "filter",
    "wave_arp",
    "arp_delay",
    "wave_prog_ptr",
    "mod",
    "slide",
    "pw_carry",
    "filt_lo",
    "filt_hi",
    "wave_ctrl",
    "wave_pitch",
)
VOICE_ORDER = (2, 1, 0)


def spec_source() -> str:
    """The text of the packaged playspec."""
    return resources.files("pyfuturecomposer").joinpath(SPEC_RESOURCE).read_text()


@lru_cache(maxsize=1)
def spec():
    """The parsed :class:`~pysidtracker.playspec.Spec` of the packaged playspec."""
    return parse(spec_source())


def binding(song: Song, found=None) -> Dict[str, Union[int, tuple]]:
    """The spec's ``layout`` values for ``song``'s build (absolute addresses)."""
    resolved = (found or layout.variant(song)).resolve()
    values: Dict[str, Union[int, tuple]] = {
        name: (song.load + getattr(resolved, name)) & 0xFFFF for name in TABLES
    }
    values["work"] = resolved.work
    values["has_state"] = bool(resolved.state)
    values["voices"] = VOICE_ORDER
    return values


def _bound_loop(exc: SpecRuntimeError) -> str:
    """The name of the spec proc whose bounded loop ``exc`` reports."""
    match = re.search(r"loop at line (\d+)", str(exc))
    if match is None:
        return str(exc)
    lines = spec_source().splitlines()
    for text in reversed(lines[: int(match.group(1))]):
        proc = re.match(r"\s*proc (\w+)", text)
        if proc:
            return f"{proc.group(1)} never reaches a note"
    return str(exc)


class FutureComposerPlayer(SpecPlayer):
    """The Future Composer play routine over a parsed :class:`Song`.

    Tables, work area and self-modified operands are placed by :attr:`variant`
    (:func:`pyfuturecomposer.layout.detect`).  With ``validate`` every sequence,
    pattern and instrument the routine opens must parse as its
    :data:`pyfuturecomposer.streams.GRAMMAR` rule, else the frame raises
    :class:`~pyfuturecomposer.errors.FutureComposerParseError`.
    """

    def __init__(
        self,
        source: Union[Song, bytes, bytearray],
        subtune: int = 0,
        validate: bool = False,
    ):
        song = source if isinstance(source, Song) else parse_song(bytes(source))
        self.song = song
        self.variant = layout.variant(song)
        values = binding(song, self.variant)
        resolved = self.variant.resolve()
        play_entry = song.load + resolved.play
        self._state = values["work"] + constants.WORK_STATE - constants.WORK_BASE
        super().__init__(
            spec(),
            song.image,
            song.load,
            song.init,
            song.play,
            subtune,
            bind=lambda _view, _entry: values,
            entries=lambda _view: {song.play, play_entry},
            validate=validate,
        )

    @property
    def finished(self) -> bool:
        """True once the song has reached its end-of-song step."""
        return self._rd(self._state) == 2

    def _frame(self) -> None:
        try:
            super()._frame()
        except SpecRuntimeError as exc:
            raise FutureComposerParseError(_bound_loop(exc)) from exc
        if self.validator is not None:
            for (rule, base), message in self.validator.failures().items():
                raise FutureComposerParseError(
                    f"stream at ${base:04x} is not {rule.rsplit(':', 1)[1]}: {message}"
                )
