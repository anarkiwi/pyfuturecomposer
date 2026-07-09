"""Real-HVSC corpus validation for the Future Composer parser/recogniser.

A deterministic representative sample of MoN/FutureComposer HVSC tunes (paths in
``tests/fixtures/fc_corpus.txt`` -- copyright tunes are never committed) is each
resolved from a local HVSC tree (``$HVSC``) or the fetch mirror and asserted to
(1) parse into a :class:`~pyfuturecomposer.Song` and (2) classify as
:attr:`~pysidtracker.detect.PlayroutineKind.DIRECT` via the static player
signature.  Each tune skips cleanly when it cannot be obtained (offline CI), so
the test SKIPs without a corpus and RUNs for real against ``$HVSC``.

The synthetic recogniser tests below always run: they exercise
:meth:`FutureComposerSidParser.recognize` on crafted images without needing HVSC.
"""

import struct
import sys
from pathlib import Path

import pytest

from pysidtracker.detect import PlayroutineKind

from pyfuturecomposer import FutureComposerSidParser, parse

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import fetch_tunes  # noqa: E402  (after sys.path tweak)

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# The concrete second player signature (STA $D417; LDY #6; six DEY; LDA ($F9),Y),
# used to build synthetic images that recognize() must accept.
_FC_SIGNATURE_BYTES = bytes.fromhex("8D17D4A006888888888888B1F9")


def _load_corpus():
    lines = (FIXTURES / "fc_corpus.txt").read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]


CORPUS = _load_corpus()


def _psid(image: bytes, load=0x1800, init=0x1800, play=0x1806) -> bytes:
    header = struct.pack(">4sHHHHHHHI", b"PSID", 2, 0x7C, load, init, play, 1, 0, 0)
    header += b"\0" * (0x7C - len(header))
    return header + image


@pytest.fixture(params=CORPUS)
def corpus_tune(request):
    """Resolve a corpus tune path to bytes, skipping if unavailable."""
    rel = request.param
    try:
        path = fetch_tunes.resolve(rel)
    except Exception:  # pylint: disable=broad-except  # offline -> skip
        pytest.skip(f"corpus tune unavailable (offline, not cached): {rel}")
    return rel, path.read_bytes()


def test_corpus_parses_and_detects_direct(corpus_tune):
    """Every real FC corpus tune parses and detects as DIRECT."""
    rel, data = corpus_tune
    song = parse(data)
    assert len(song.image) > 0, rel
    assert song.load > 0, rel
    detection = FutureComposerSidParser().detect(data)
    assert detection.kind is PlayroutineKind.DIRECT, f"{rel}: {detection.kind}"
    assert detection.anchor, rel  # the located signature address


def test_recognize_finds_signature():
    """recognize() returns the player-code address for a signed image."""
    image = b"\x00" * 32 + _FC_SIGNATURE_BYTES + b"\x00" * 32
    data = _psid(image)
    parser = FutureComposerSidParser()
    sid_image = parser.load_image(data)
    assert parser.recognize(sid_image) == 0x1800 + 32


def test_recognize_direct_via_detect():
    """detect() classifies a signed image as DIRECT without emulating init."""
    data = _psid(b"\x11" * 16 + _FC_SIGNATURE_BYTES)
    detection = FutureComposerSidParser().detect(data)
    assert detection.kind is PlayroutineKind.DIRECT
    assert detection.ran_init is False


def test_recognize_absent_signature_is_none():
    """recognize() returns None when no FC signature is present."""
    data = _psid(b"\x00" * 64)
    parser = FutureComposerSidParser()
    assert parser.recognize(parser.load_image(data)) is None
