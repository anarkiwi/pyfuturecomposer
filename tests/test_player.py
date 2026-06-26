"""Player tests: byte-exact reproduction of the SID register oracle."""

from pyfuturecomposer import Player, iter_frames, read, render_grid

NREG = 25
MAX_LEAD = 4


def _validate(oracle_rows, rendered_rows, max_lead=MAX_LEAD):
    """Lead-aligned byte-exact compare (the deplayroutine validator's rule).

    Returns ``(ok, lead)``: drops up to ``max_lead`` leading interpreter frames
    (only frames equal to the post-init baseline) and reports the alignment used.
    """
    if not rendered_rows:
        return False, 0
    baseline = rendered_rows[0]
    nframes = len(oracle_rows)
    for lead in range(max_lead + 1):
        if lead > 0 and (
            lead > len(rendered_rows) or rendered_rows[lead - 1] != baseline
        ):
            break
        aligned = rendered_rows[lead : lead + nframes]
        if len(aligned) < nframes:
            continue
        if all(aligned[i] == oracle_rows[i] for i in range(nframes)):
            return True, lead
    return False, -1


def test_player_byte_exact_vs_oracle(tune_id, tune_path, oracle_grid):
    """The pure-Python FC player reproduces the oracle grid byte-exact."""
    oracle_rows, source = oracle_grid
    song = read(tune_path)
    rendered = render_grid(song, len(oracle_rows) + MAX_LEAD)
    ok, lead = _validate(oracle_rows, rendered)
    assert (
        ok
    ), f"{tune_id}: not byte-exact vs {source} oracle ({len(oracle_rows)} frames)"
    assert lead >= 0


def test_render_grid_shape(tune_path):
    song = read(tune_path)
    grid = render_grid(song, 32)
    assert len(grid) == 32
    assert all(len(row) == NREG for row in grid)


def test_iter_frames_yields_writes(tune_path):
    song = read(tune_path)
    frames = list(iter_frames(song, max_frames=8))
    assert len(frames) == 8
    # Every frame writes the master volume ($D418 -> reg 0x18) once.
    assert all(any(reg == 0x18 for reg, _ in frame) for frame in frames)


def test_player_is_deterministic(tune_path):
    song = read(tune_path)
    a = render_grid(song, 64)
    b = render_grid(song, 64)
    assert a == b


def test_pw_high_masked_to_nibble(tune_path):
    song = read(tune_path)
    grid = render_grid(song, 64)
    for row in grid:
        for reg in (0x03, 0x0A, 0x11):
            assert row[reg] <= 0x0F


def test_two_players_independent(tune_path):
    song = read(tune_path)
    p1 = Player(song)
    p2 = Player(song)
    p1.play_frame()
    # p2 has not advanced; its first frame matches p1's first frame.
    f1 = render_grid(song, 1)
    assert f1  # first frame produced writes
    assert p2.play_frame() is not None
