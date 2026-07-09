"""pysidtracker base-integration tests: shared error hierarchy and parser API."""

import struct

import pysidtracker

from pyfuturecomposer import FutureComposerError, FutureComposerSidParser, parse


def _psid(image: bytes, load=0x1800, init=0x1800, play=0x1806) -> bytes:
    header = struct.pack(">4sHHHHHHHI", b"PSID", 2, 0x7C, load, init, play, 1, 0, 0)
    header += b"\0" * (0x7C - len(header))
    return header + image


def test_error_base_subclasses_pysidtracker_siderror():
    assert issubclass(FutureComposerError, pysidtracker.SidError)


def test_parser_read_matches_parse():
    data = _psid(b"\x00" * 64)
    assert FutureComposerSidParser().read(data) == parse(data)
