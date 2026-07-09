"""Read a Future Composer tune (PSID/.sid or .prg image) into a :class:`Song`.

A PSID/RSID container wraps the raw C64 image (player code + inline song data)
with a header giving the load/init/play addresses.  Future Composer is
relocatable (init = load, play = load + 6) and carries its data tables inline at
fixed offsets-from-load, so the reader only needs to unwrap the container; the
player walks the inline tables from the image directly.

Container/header decoding is delegated to :mod:`pysidtracker` (the shared
``parse_sid_header``/``SidImage``); the Future Composer init/play fallbacks and
the bare ``.prg`` path are applied on top.
"""

from pathlib import Path
from typing import Any, Tuple

from pysidtracker import (
    BaseSidParser,
    CodePattern,
    SidError,
    SidImage,
    find_code_first,
)

from pyfuturecomposer import constants
from pyfuturecomposer.errors import SidParseError
from pyfuturecomposer.model import Song

# Relocation-independent MoN/FutureComposer player signatures.  Every operand
# that carries an absolute address (relocation-dependent) or a per-tune zero-page
# pointer is a wildcard (``??``); only the opcodes and fixed immediates remain.
# Both patterns were verified byte-for-byte against the MoN/FutureComposer HVSC
# corpus: the first (a fragment of the per-voice row/duration advance -- INC ,X /
# LDY ,X / LDA (zp),Y / CMP #$FF ...) matches the vast majority; the second (the
# STA $D417 filter store followed by LDY #6 / six DEY / LDA (zp),Y) covers the
# handful of player revisions the first misses.  Together they cover the corpus.
_FC_PATS: Tuple[CodePattern, ...] = tuple(
    CodePattern(spec)
    for spec in (
        "FE ?? ?? BC ?? ?? B1 ?? C9 FF D0 ?? A9 00 9D ?? ?? "
        "BD ?? ?? F0 05 DE ?? ?? 10 03",
        "8D 17 D4 A0 06 88 88 88 88 88 88 B1 ??",
    )
)


def _parse_container(data: bytes) -> Tuple[int, int, int, str, str, str, bytes]:
    """Return (load, init, play, name, author, released, image)."""
    if data[:4] in (b"PSID", b"RSID"):
        try:
            image = SidImage.from_sid(data)
        except SidError as exc:
            raise SidParseError(str(exc)) from exc
        header = image.header
        load = image.load
        init = header.init_address or load + constants.DEFAULT_INIT_OFFSET
        play = header.play_address or load + constants.DEFAULT_PLAY_OFFSET
        return (
            load,
            init,
            play,
            header.name,
            header.author,
            header.released,
            image.image,
        )
    # Bare .prg: 2-byte little-endian load address + image.
    try:
        image = SidImage.from_prg(data)
    except SidError as exc:
        raise SidParseError(str(exc)) from exc
    load = image.load
    return (
        load,
        load + constants.DEFAULT_INIT_OFFSET,
        load + constants.DEFAULT_PLAY_OFFSET,
        "",
        "",
        "",
        image.image,
    )


def parse(data: bytes) -> Song:
    """Parse a PSID/RSID/.prg byte string into a :class:`Song`."""
    load, init, play, name, author, released, image = _parse_container(data)
    return Song(
        image=image,
        load=load,
        init=init,
        play=play,
        name=name,
        author=author,
        released=released,
    )


def read(path) -> Song:
    """Read a Future Composer tune from a path into a :class:`Song`."""
    return parse(Path(path).read_bytes())


class FutureComposerSidParser(BaseSidParser):
    """:class:`~pysidtracker.BaseSidParser` binding for Future Composer.

    Provides the shared ``read``/``parse``/``detect`` surface. Future Composer is
    a plain direct-load player, so :meth:`recognize` locates its fixed player code
    by a relocation-independent signature and :meth:`detect` reports ``DIRECT``.
    """

    error_class: type = SidParseError

    def parse(self, data: bytes, **_kwargs: Any) -> Song:
        """Decode raw ``.sid``/``.prg`` ``data`` into a :class:`Song`."""
        return parse(data)

    def recognize(self, image):
        """Return the C64 address of the FC player signature, or ``None``.

        Future Composer relocates cleanly (its data offsets are load-relative)
        and loads directly, so the player code is present in the freshly loaded
        image.  The patterns in :data:`_FC_PATS` wildcard every absolute
        operand, so a match is relocation-independent; the returned address is a
        truthy anchor that classifies the tune as ``DIRECT``.
        """
        for pattern in _FC_PATS:
            match = find_code_first(image, pattern)
            if match is not None:
                return match.addr
        return None
