"""The ``scripts/oracle_hvsc.py`` survey renderer and its render contract."""

import json
import re

import numpy as np
import oracle_hvsc
import pytest

import pysidtracker
from pysidtracker.cadence import cadence_info
from pysidtracker.header import write_psid
from pysidtracker.sidid import sidid_signatures

from pyfuturecomposer import FutureComposerParseError, FutureComposerPlayer


def _psid(image: bytes) -> bytes:
    return write_psid(load=0x1800, init=0x1800, play=0x1806, image=image)


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
        "dynamic": False,
    }


def test_render_selects_one_based_subtune(tune_path, monkeypatch):
    seen = []

    def player(tune, subtune):
        seen.append(("player", subtune))
        return FutureComposerPlayer(tune, subtune)

    def cadence(data, song):
        seen.append(("cadence", song))
        return cadence_info(data, song)

    monkeypatch.setattr(oracle_hvsc, "FutureComposerPlayer", player)
    monkeypatch.setattr(oracle_hvsc, "cadence_info", cadence)
    oracle_hvsc.render(tune_path.read_bytes(), 3, 10)
    assert sorted(seen) == [("cadence", 3), ("player", 2)]


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
