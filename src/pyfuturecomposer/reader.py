"""Read a Future Composer tune (PSID/RSID ``.sid`` or bare ``.prg``) into a :class:`Song`.

The container is decoded by :mod:`pysidtracker`; a missing header init/play falls
back to load / load + 6.  Tables are placed later by :mod:`pyfuturecomposer.layout`.
"""

from typing import Any, Tuple

from pysidtracker import BaseSidParser, SidError, SidImage, read_bytes, reraise_as

from pyfuturecomposer import constants
from pyfuturecomposer.errors import SidParseError
from pyfuturecomposer.layout import SIGNATURE
from pyfuturecomposer.model import Song
from pyfuturecomposer.streams import streams


def _parse_container(data: bytes) -> Tuple[int, int, int, str, str, str, bytes]:
    """Return (load, init, play, name, author, released, image)."""
    with reraise_as(SidParseError, SidError):
        image = SidImage.from_bytes(data)
    load = image.load
    header = image.header
    if header is None:
        # Bare .prg: init = load, play = load + 6.
        return (
            load,
            load + constants.DEFAULT_INIT_OFFSET,
            load + constants.DEFAULT_PLAY_OFFSET,
            "",
            "",
            "",
            image.image,
        )
    init = header.init_address or load + constants.DEFAULT_INIT_OFFSET
    play = header.play_address or load + constants.DEFAULT_PLAY_OFFSET
    return (load, init, play, header.name, header.author, header.released, image.image)


def parse(data: bytes, validate: bool = False) -> Song:
    """Parse a PSID/RSID/.prg byte string into a :class:`Song`.

    With ``validate``, every sequence, pattern and instrument the player reaches
    must parse as its :mod:`~pyfuturecomposer.streams` grammar rule, else
    :class:`~pyfuturecomposer.errors.SidParseError`.
    """
    load, init, play, name, author, released, image = _parse_container(data)
    song = Song(
        image=image,
        load=load,
        init=init,
        play=play,
        name=name,
        author=author,
        released=released,
    )
    if validate:
        for _ in streams(song):
            pass
    return song


def read(source, validate: bool = False) -> Song:
    """Read a Future Composer tune from a path, bytes or binary file object."""
    return parse(read_bytes(source), validate)


class FutureComposerSidParser(BaseSidParser):
    """:class:`~pysidtracker.BaseSidParser` binding for Future Composer.

    Provides the shared ``read``/``parse``/``detect`` surface. Future Composer is
    a plain direct-load player, so :meth:`recognize` locates its fixed player code
    by a relocation-independent signature and :meth:`detect` reports ``DIRECT``.
    """

    error_class: type = SidParseError

    def parse(self, data: bytes, **kwargs: Any) -> Song:
        """Decode raw ``.sid``/``.prg`` ``data`` into a :class:`Song`."""
        return parse(data, bool(kwargs.get("validate")))

    def recognize(self, image):
        """Return the C64 address of the FC player signature, or ``None``.

        :data:`~pyfuturecomposer.layout.SIGNATURE` wildcards every absolute operand,
        so a match is relocation-independent and classifies the tune ``DIRECT``.
        """
        hit = SIGNATURE.find_first(image)
        return None if hit is None else hit.addr
