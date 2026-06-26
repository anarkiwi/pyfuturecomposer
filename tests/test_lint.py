"""Smoke tests: the package imports and exposes its public surface."""

import pyfuturecomposer


def test_version():
    assert pyfuturecomposer.__version__


def test_public_surface():
    for name in (
        "read",
        "parse",
        "Song",
        "Player",
        "iter_frames",
        "render_grid",
        "iter_register_writes",
        "RegWrite",
        "read_reglog",
        "write_reglog",
    ):
        assert hasattr(pyfuturecomposer, name), name
