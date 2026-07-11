"""Player unit tests (byte-exact oracle validation lives in test_oracle_hvsc.py)."""

from pyfuturecomposer import FutureComposerPlayer, read

NREG = 25


def test_render_grid_shape(tune_path):
    grid = FutureComposerPlayer(read(tune_path)).render_grid(32)
    assert len(grid) == 32
    assert all(len(row) == NREG for row in grid)


def test_player_accepts_bytes_and_song(tune_path):
    data = tune_path.read_bytes()
    assert FutureComposerPlayer(data).render_grid(16) == FutureComposerPlayer(
        read(tune_path)
    ).render_grid(16)


def test_iter_frames_yields_writes(tune_path):
    frames = list(FutureComposerPlayer(read(tune_path)).iter_frames(8))
    assert len(frames) == 8
    # Every frame writes the master volume ($D418 -> reg 0x18); frame 0 emits all
    # 25 registers, later frames emit only changed registers (MemPlayer diffing).
    assert any(reg == 0x18 for reg, _ in frames[0])


def test_player_is_deterministic(tune_path):
    song = read(tune_path)
    assert FutureComposerPlayer(song).render_grid(64) == FutureComposerPlayer(
        song
    ).render_grid(64)


def test_pw_high_masked_to_nibble(tune_path):
    grid = FutureComposerPlayer(read(tune_path)).render_grid(64)
    for row in grid:
        for reg in (0x03, 0x0A, 0x11):
            assert row[reg] <= 0x0F


def test_two_players_independent(tune_path):
    song = read(tune_path)
    p1 = FutureComposerPlayer(song)
    p2 = FutureComposerPlayer(song)
    p1.play_frame()  # advance p1 only
    assert p2.play_frame()  # p2's first frame still produces writes
