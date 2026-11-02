"""The Future Composer play routine, run as ``specs/futurecomposer.play``.

:class:`FutureComposerPlayer` is a :class:`pysidtracker.playspec.SpecPlayer`: the
tune's own init runs on the emulated 6502, then each play call runs the spec.  The
play variables are the spec's own state, started from the memory the init left;
:mod:`pyfuturecomposer.layout` locates the tables and operands of the tune's build,
which :func:`binding` hands the spec as its ``layout``.
"""

import re
from functools import lru_cache
from importlib import resources
from typing import Callable, Dict, Iterator, Optional, Tuple, Union

from pysidtracker import SidParseError
from pysidtracker.formats import SpecBinding
from pysidtracker.playspec import SpecPlayer, SpecRuntimeError, parse

from pyfuturecomposer import constants, layout
from pyfuturecomposer.errors import FutureComposerParseError
from pyfuturecomposer.model import Song
from pyfuturecomposer.reader import parse as parse_song

SPEC_RESOURCE = "specs/futurecomposer.play"
ADDRESSES = (
    "freq_lo",
    "freq_hi",
    "seq_lo",
    "seq_hi",
    "pat_ptr",
    "instr",
    "mod",
    "voice_base",
    "tempo",
    "volume",
    "pw_step",
    "filter",
    "wave_arp",
    "arp_delay",
    "filt_lo",
    "filt_hi",
    "wave_prog_ptr",
    "slide",
)
VOICES = 3


def spec_source() -> str:
    """The text of the packaged playspec."""
    return resources.files("pyfuturecomposer").joinpath(SPEC_RESOURCE).read_text()


@lru_cache(maxsize=1)
def spec():
    """The parsed :class:`~pysidtracker.playspec.Spec` of the packaged playspec."""
    return parse(spec_source())


def initial(
    view: bytes, work: int, slide: int, scratch: int
) -> Dict[str, Union[int, list]]:
    """``init_<variable>``: what the tune's init left in each play variable of the work
    area at ``work`` (a list over the voices for a voice's own) and in the slide delay at
    ``slide`` and in the arpeggio's zero-page byte at ``scratch``; the spec keeps them as state
    from there."""

    def byte(addr: int) -> int:
        return view[addr & 0xFFFF]

    voices = range(VOICES)
    out: Dict[str, Union[int, list]] = {
        f"init_{name}": [byte(work + offset + x) for x in voices]
        for name, offset in constants.VOICE_BYTES.items()
    }
    out.update(
        {
            f"init_{name}": [
                byte(work + lo + x) | byte(work + hi + x) << 8 for x in voices
            ]
            for name, (lo, hi) in constants.VOICE_WORDS.items()
        }
    )
    out.update(
        {
            f"init_{name}": byte(work + offset)
            for name, offset in constants.SHARED_BYTES.items()
        }
    )
    out.update(
        {
            f"init_{name}": byte(work + lo) | byte(work + hi) << 8
            for name, (lo, hi) in constants.SHARED_WORDS.items()
        }
    )
    out["init_slide_delay"] = byte(slide)
    out["init_arp_scratch"] = byte(scratch)
    return out


def play_variables(
    work: int, memory: Callable[[int], int]
) -> Iterator[Tuple[str, int]]:
    """``(state name, value)`` of every play variable as the routine itself keeps it in the
    work area at ``work`` (``memory`` reads a 6502 run's): what the spec's state holds.
    """
    for x in range(VOICES):
        for name, offset in constants.VOICE_BYTES.items():
            yield f"voice[{x}].{name}", memory(work + offset + x)
        for name, (lo, hi) in constants.VOICE_WORDS.items():
            yield f"voice[{x}].{name}", memory(work + lo + x) | memory(
                work + hi + x
            ) << 8
    for name, offset in constants.SHARED_BYTES.items():
        yield name, memory(work + offset)
    for name, (lo, hi) in constants.SHARED_WORDS.items():
        yield name, memory(work + lo) | memory(work + hi) << 8


def refusal(song: Song, variant, entry: Optional[int] = None) -> Optional[str]:
    """Why the spec cannot play ``song``, or None.  A build whose work area lies over its
    speed or voice-base table was not placed; so was one whose play routine runs beside the
    spec because the entry the spec stands in for is not where the routine starts."""
    resolved = variant.resolve()
    for name, size in (("tempo", 1), ("voice_base", VOICES)):
        at = (song.load + getattr(resolved, name)) & 0xFFFF
        if at < resolved.work + constants.WORK_SIZE and resolved.work < at + size:
            return f"the work area at ${resolved.work:04x} overlaps the {name} table"
    if (
        entry is not None
        and entry != song.play
        and variant.source("play").kind != "detected"
    ):
        return f"the play routine at ${song.play:04x} does not start at the entry ${entry:04x}"
    return None


def _stray(song: Song, resolved) -> list:
    """What each byte of the pulse program row a sweep byte without a program index reads
    is: 1 the shift count, 2 + voice a voice's depth, 0 the memory at that address."""
    kinds = {constants.SHARED_BYTES["ae"]: 1}
    kinds.update({constants.VOICE_BYTES["depth"] + x: 2 + x for x in range(VOICES)})
    base = song.load + resolved.pw_step + 0xFC
    return [kinds.get((base + k - resolved.work) & 0xFFFF, 0) for k in range(4)]


def binding(
    song: Song, view: Optional[bytes] = None, found=None, entry: Optional[int] = None
) -> Dict[str, Union[int, bool, list]]:
    """The spec's ``layout`` values for ``song``'s build: the addresses of its tables and
    the play variables ``view`` holds (default: the memory its init leaves).

    Raises:
      FutureComposerParseError: the build is one the spec does not place (:func:`refusal`).
    """
    variant = found or layout.variant(song)
    resolved = variant.resolve()
    why = refusal(song, variant, entry)
    if why:
        raise FutureComposerParseError(why)
    if view is None:
        view = bytes(layout.initialised(song).mem)
    values: Dict[str, Union[int, bool, list]] = {
        name: (song.load + getattr(resolved, name)) & 0xFFFF for name in ADDRESSES
    }
    values["has_state"] = bool(resolved.state)
    for name in ("arp_zp", "order_zp", "pat_zp", "voice_zp"):
        values[name] = getattr(resolved, name)
    values["pw_wild"] = _stray(song, resolved)
    values.update(initial(view, resolved.work, values.pop("slide"), resolved.arp_zp))
    return values


ENDLESS = {
    "next_note": "sequence never reaches a pattern",
    "read_pattern": "pattern never reaches a note",
}


def _bound_loop(exc: SpecRuntimeError) -> str:
    """What the spec's bounded loop that ``exc`` reports was looking for."""
    match = re.search(r"loop at line (?:[^:\s]+:)?(\d+)", str(exc))
    if match is None:
        return str(exc)
    lines = spec_source().splitlines()
    for text in reversed(lines[: int(match.group(1))]):
        proc = re.match(r"\s*proc (\w+)", text)
        if proc:
            return ENDLESS.get(proc.group(1), str(exc))
    return str(exc)


def spec_binding(song: Song) -> SpecBinding:
    """The :class:`~pysidtracker.formats.SpecBinding` :class:`FutureComposerPlayer`
    plays ``song`` with: the packaged spec, the build's layout and the play entries
    its first call reaches."""
    return FutureComposerPlayer(song).binding


class FutureComposerPlayer(SpecPlayer):
    """The Future Composer play routine over a parsed :class:`Song`.

    Tables and the addresses a build moves are placed by :attr:`variant`
    (:func:`pyfuturecomposer.layout.detect`); the play variables start from what the
    tune's own init left (:func:`binding`).  A sequence or pattern the routine cannot walk
    to a note raises :class:`~pyfuturecomposer.errors.FutureComposerParseError`.
    :attr:`binding` is the :class:`~pysidtracker.formats.SpecBinding` it plays.
    """

    def __init__(self, source: Union[Song, bytes, bytearray], subtune: int = 0):
        song = source if isinstance(source, Song) else parse_song(bytes(source), False)
        self.song = song
        self.variant = layout.variant(song)
        play_entry = song.load + self.variant.resolve().play
        for entries in ({play_entry}, {song.play, play_entry}):
            self.binding = SpecBinding(
                spec(),
                lambda view, entry: binding(song, view, self.variant, entry),
                song.image,
                entries=lambda _view, found=frozenset(entries): found,
                subtune=subtune,
            )
            try:
                super().__init__(
                    spec(),
                    song.image,
                    song.load,
                    song.init,
                    song.play,
                    subtune,
                    bind=self.binding.bind,
                    entries=self.binding.entries,
                )
                break
            except SidParseError:
                if song.play in entries:
                    raise

    @property
    def finished(self) -> bool:
        """True once the song has reached its end-of-song step."""
        return self.state("play_state") == 2

    def _frame(self) -> None:
        try:
            super()._frame()
        except SpecRuntimeError as exc:
            raise FutureComposerParseError(_bound_loop(exc)) from exc
