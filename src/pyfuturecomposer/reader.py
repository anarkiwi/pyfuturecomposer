"""Read a Future Composer tune (PSID/.sid or .prg image) into a :class:`Song`.

A PSID/RSID container wraps the raw C64 image (player code + inline song data)
with a header giving the load/init/play addresses.  Future Composer is
relocatable (init = load, play = load + 6) and carries its data tables inline at
fixed offsets-from-load, so the reader only needs to unwrap the container; the
player walks the inline tables from the image directly.
"""

import struct
from pathlib import Path
from typing import Tuple

from pyfuturecomposer import constants
from pyfuturecomposer.errors import SidParseError
from pyfuturecomposer.model import Song

_PSID_HEADER = struct.Struct(">4sHHHHHHHI")  # magic..speed


def _read_cstr(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("latin-1")


def _parse_container(data: bytes) -> Tuple[int, int, int, str, str, str, bytes]:
    """Return (load, init, play, name, author, released, image)."""
    magic = data[:4]
    if magic in (b"PSID", b"RSID"):
        if len(data) < _PSID_HEADER.size:
            raise SidParseError("truncated PSID/RSID header")
        _m, _ver, data_off, load, init, play, _songs, _start, _speed = (
            _PSID_HEADER.unpack_from(data, 0)
        )
        name = _read_cstr(data[22:54])
        author = _read_cstr(data[54:86])
        released = _read_cstr(data[86:118])
        body = data[data_off:]
        if load == 0:  # load address is the first 2 bytes of the body
            if len(body) < 2:
                raise SidParseError("truncated PSID body")
            load = body[0] | (body[1] << 8)
            image = body[2:]
        else:
            image = body
        if init == 0:
            init = load + constants.DEFAULT_INIT_OFFSET
        if play == 0:
            play = load + constants.DEFAULT_PLAY_OFFSET
        return load, init, play, name, author, released, image
    # Bare .prg: 2-byte little-endian load address + image.
    if len(data) < 2:
        raise SidParseError("truncated .prg image")
    load = data[0] | (data[1] << 8)
    return (
        load,
        load + constants.DEFAULT_INIT_OFFSET,
        load + constants.DEFAULT_PLAY_OFFSET,
        "",
        "",
        "",
        data[2:],
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
