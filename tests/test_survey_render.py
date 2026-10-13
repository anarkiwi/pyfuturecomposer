"""The ``scripts/oracle_hvsc.py`` survey renderer and its render contract."""

import json
import re
import struct

import numpy as np
import oracle_hvsc
import pytest

import pysidtracker
from pysidtracker.cadence import Cadence, playroutine_cadence
from pysidtracker.registers import PAL_CLOCK_HZ, PAL_CYCLES_PER_FRAME
from pysidtracker.sidid import sidid_signatures

from pyfuturecomposer import FutureComposerParseError, FutureComposerPlayer


def _psid(image: bytes) -> bytes:
    header = struct.pack(
        ">4sHHHHHHHI", b"PSID", 2, 0x7C, 0x1800, 0x1800, 0x1806, 1, 0, 0
    )
    return header + b"\0" * (0x7C - len(header)) + image


def test_render_matches_player(tune_path):
    data = tune_path.read_bytes()
    grid, info = oracle_hvsc.render(data, 1, 120)
    assert grid.shape == (120, 25)
    assert grid.dtype == np.int16
    np.testing.assert_array_equal(grid, FutureComposerPlayer(data).render_grid(120))
    assert json.loads(json.dumps(info)) == info
    assert info == {
        "layout": 0,
        "init": 0,
        "play": 6,
        "rsid": False,
        "trigger": "pal_video",
        "speed": 1,
    }


def test_render_reports_unknown_trigger(tune_path, monkeypatch):
    unknown = Cadence(PAL_CYCLES_PER_FRAME, None, PAL_CLOCK_HZ)
    monkeypatch.setattr(oracle_hvsc, "playroutine_cadence", lambda *_, **__: unknown)
    info = oracle_hvsc.render(tune_path.read_bytes(), 1, 1)[1]
    assert (info["trigger"], info["speed"]) == (None, 1)


def test_render_selects_one_based_subtune(tune_path, monkeypatch):
    seen = []

    def player(tune, subtune):
        seen.append(("player", subtune))
        return FutureComposerPlayer(tune, subtune)

    def cadence(data, subtune):
        seen.append(("cadence", subtune))
        return playroutine_cadence(data, subtune=subtune)

    monkeypatch.setattr(oracle_hvsc, "FutureComposerPlayer", player)
    monkeypatch.setattr(oracle_hvsc, "playroutine_cadence", cadence)
    oracle_hvsc.render(tune_path.read_bytes(), 3, 10)
    assert sorted(seen) == [("cadence", 2), ("player", 2)]


@pytest.mark.parametrize("data", [b"PSID", _psid(b"\x00" * 0x800)])
def test_non_fc_raises_sid_parse_error(data):
    with pytest.raises(pysidtracker.SidParseError) as exc:
        oracle_hvsc.render(data, 1, 10)
    assert isinstance(exc.value, FutureComposerParseError)


def test_player_regex_selects_fc_signature():
    names = [name for name, _ in sidid_signatures()]
    assert [n for n in names if re.search(oracle_hvsc.PLAYER, n, re.I)] == [
        "MoN/FutureComposer"
    ]
