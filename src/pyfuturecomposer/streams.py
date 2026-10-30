"""Future Composer song streams: sequences, patterns and instruments.

:data:`GRAMMAR` is the ``futurecomposer.lark`` :class:`~pysidtracker.ByteGrammar`.
:func:`read_streams` reads every stream a tune's player reaches through its
pointer tables, raising :class:`~pyfuturecomposer.errors.FutureComposerParseError`
for bytes that are not one stream.  Pattern ids come from the sequences and
instrument ids from the patterns, as the player reaches them.
"""

from dataclasses import dataclass
from typing import Iterator, Tuple, Union

from lark import Token, Transformer
from pysidtracker import (
    ByteGrammar,
    Parsed,
    SidError,
    SidImage,
    Variant,
    image_after_init,
)

from pyfuturecomposer import constants, layout
from pyfuturecomposer.errors import FutureComposerParseError
from pyfuturecomposer.model import Song

VOICES = 3
PATTERN_IDS = 0x40
INSTRUMENT_IDS = 0x20
INSTRUMENT_SIZE = 8

Step = Tuple[str, int]
Command = Tuple[str, Tuple[int, ...]]


@dataclass(frozen=True)
class Sequence:
    """A voice's orderlist: ``("pattern"|"repeat"|"transpose", value)`` steps."""

    steps: Tuple[Step, ...]
    loops: bool

    def to_bytes(self) -> bytes:
        """The stream bytes, terminator included."""
        out = bytearray()
        for kind, value in self.steps:
            out.append(value | _STEP_BITS[kind])
        out.append(constants.SEQ_LOOP if self.loops else constants.SEQ_END)
        return bytes(out)

    @property
    def patterns(self) -> Tuple[int, ...]:
        """Pattern ids in play order."""
        return tuple(v for kind, v in self.steps if kind == "pattern")


@dataclass(frozen=True)
class Pattern:
    """A note stream: ``(kind, operands)`` commands in stream order."""

    commands: Tuple[Command, ...]

    def to_bytes(self) -> bytes:
        """The stream bytes, terminator included."""
        out = bytearray()
        for kind, operands in self.commands:
            first, rest = operands[0], operands[1:]
            out.append(first | _COMMAND_BITS[kind])
            out.extend(rest)
        out.append(constants.PATTERN_END)
        return bytes(out)

    @property
    def instruments(self) -> Tuple[int, ...]:
        """Instrument ids selected, in stream order."""
        return tuple(ops[0] for kind, ops in self.commands if kind == "instr")


@dataclass(frozen=True)
class Instrument:
    """An 8-byte sound record."""

    pulse_ctrl: int
    waveform: int
    attack_decay: int
    sustain_release: int
    aux: int
    vib_ctrl: int
    pw_ctrl: int
    master_ctrl: int

    def to_bytes(self) -> bytes:
        """The record bytes."""
        return bytes(
            (
                self.pulse_ctrl,
                self.waveform,
                self.attack_decay,
                self.sustain_release,
                self.aux,
                self.vib_ctrl,
                self.pw_ctrl,
                self.master_ctrl,
            )
        )


Model = Union[Sequence, Pattern, Instrument]

_STEP_BITS = {"pattern": 0, "repeat": constants.SEQ_REPEAT, "transpose": 0x80}
_COMMAND_BITS = {
    "note": 0,
    "duration": constants.DUR_MIN,
    "instr": constants.INSTR_MIN,
    "slide": constants.PORTA_MIN,
    "row": constants.ROWMARK_MIN,
}


def _value(token: Token) -> int:
    return ord(token)


class _Transformer(Transformer):
    """Builds each start rule's :class:`~pysidtracker.Parsed`."""

    def step(self, children):
        return ("pattern", _value(children[0]))

    def repeat(self, children):
        return ("repeat", _value(children[0]) & 0x3F)

    def transpose(self, children):
        return ("transpose", _value(children[0]) & 0x7F)

    def sequence(self, children):
        *steps, stop = children
        return Parsed(Sequence(tuple(steps), stop.type == "SEQ_LOOP"), stop.end_pos)

    def note(self, children):
        return ("note", (_value(children[0]),))

    def duration(self, children):
        return ("duration", (_value(children[0]) & 0x3F,))

    def instr(self, children):
        return ("instr", (_value(children[0]) & 0x1F,))

    def slide(self, children):
        return ("slide", (_value(children[0]) & 0x0F, _value(children[1])))

    def row(self, children):
        return ("row", (_value(children[0]) & 0x0F, _value(children[1])))

    def first_row(self, children):
        return ("row", (_value(children[0]) & 0x0F, _value(children[1])))

    def pattern(self, children):
        *commands, end = children
        return Parsed(Pattern(tuple(commands)), end.end_pos)

    def instrument(self, children):
        return Parsed(Instrument(*map(_value, children)), children[-1].end_pos)


GRAMMAR = ByteGrammar(
    "pyfuturecomposer",
    "futurecomposer.lark",
    ("sequence", "pattern", "instrument"),
    _Transformer(),
    FutureComposerParseError,
)


def _model(image: SidImage, addr: int, rule: str, what: str) -> Model:
    return GRAMMAR.read(image, addr, rule, what).model


def _after_init(loaded: SidImage) -> SidImage:
    """``loaded`` after its own init, else as loaded (a bare ``.prg``)."""
    try:
        return image_after_init(loaded)
    except SidError:
        return loaded


def streams(song: Song) -> Iterator[Tuple[str, Model, str]]:
    """``(name, model, rule)`` of every stream ``song``'s player reaches.

    Raises:
      FutureComposerParseError: a pointer leads to bytes that are not one stream.
    """
    loaded = layout.song_image(song)
    found: Variant = layout.detect(loaded)
    var = found.resolve()
    image = _after_init(loaded)
    seq_lo, seq_hi = song.load + var.seq_lo, song.load + var.seq_hi
    patterns = set()
    for voice in range(VOICES):
        what = f"voice {voice} sequence"
        model = GRAMMAR.entry(image, seq_lo, seq_hi, voice, "sequence", what).model
        patterns.update(model.patterns)
        yield what, model, "sequence"
    pat_lo = song.load + var.pat_ptr
    instruments = set()
    for ident in sorted(patterns):
        what = f"pattern {ident}"
        model = GRAMMAR.entry(image, pat_lo, pat_lo + 1, 2 * ident, "pattern", what)
        instruments.update(model.model.instruments)
        yield what, model.model, "pattern"
    for ident in range(max(instruments, default=-1) + 1):
        what = f"instrument {ident}"
        addr = song.load + var.instr + ident * INSTRUMENT_SIZE
        yield what, _model(image, addr, "instrument", what), "instrument"
