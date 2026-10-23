"""pysidtracker base-integration tests: shared error hierarchy and parser API."""

import pysidtracker
from pysidtracker.header import write_psid

from pyfuturecomposer import (
    FutureComposerError,
    FutureComposerParseError,
    FutureComposerSidParser,
    SidParseError,
    parse,
)


def _psid(image: bytes, load=0x1800, init=0x1800, play=0x1806) -> bytes:
    return write_psid(load=load, init=init, play=play, image=image)


def test_error_base_subclasses_pysidtracker_siderror():
    assert issubclass(FutureComposerError, pysidtracker.SidError)


def test_parse_error_is_both_package_and_base_parse_error():
    assert issubclass(FutureComposerParseError, FutureComposerError)
    assert issubclass(FutureComposerParseError, pysidtracker.SidParseError)
    assert SidParseError is FutureComposerParseError


def test_parser_read_matches_parse():
    data = _psid(b"\x00" * 64)
    assert FutureComposerSidParser().read(data) == parse(data)
