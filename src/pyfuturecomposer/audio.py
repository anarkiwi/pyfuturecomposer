"""Render Future Composer songs through an emulated SID to samples or WAV.

Thin Future Composer wrappers over the shared :mod:`pysidtracker.audio` renderer.
By default the emulated SID is `pyresidfp <https://pypi.org/project/pyresidfp/>`_
(install ``pysidtracker[audio]``).  Any object with ``write_register(reg, value)``,
``clock(timedelta) -> samples`` and a ``sampling_frequency`` attribute can be
passed as ``device`` instead (e.g. for tests or a different emulator).
"""

from pathlib import Path

from pysidtracker.audio import CHIP_MODELS, write_wav
from pysidtracker.audio import render_samples as _render_samples
from pysidtracker.audio import device_sampling_frequency, resolve_device
from pysidtracker.errors import AudioUnavailable
from pysidtracker.reglog import DEFAULT_WRITE_SPACING

from pyfuturecomposer import constants
from pyfuturecomposer.errors import FutureComposerError
from pyfuturecomposer.model import Song
from pyfuturecomposer.player import FutureComposerPlayer

__all__ = ["CHIP_MODELS", "render_samples", "render_wav", "write_wav"]


def render_samples(
    song: Song,
    seconds: float = 60.0,
    model: str = "8580",
    sampling_frequency=None,
    device=None,
    cycles_per_frame: int = constants.PAL_CYCLES_PER_FRAME,
    clock_frequency: float = constants.PAL_CLOCK_HZ,
):
    """Render ``song`` on an emulated SID.

    Returns ``(samples, sampling_frequency)`` where samples are signed 16-bit
    mono.  Rendering stops at ``seconds`` (the player loops, so a duration is
    required).  The per-frame writes are framed by :mod:`pysidtracker.audio`.
    """
    try:
        device = resolve_device(device, model, sampling_frequency)
    except ValueError as exc:
        raise FutureComposerError(str(exc)) from exc
    except AudioUnavailable as exc:
        raise FutureComposerError(
            "pyresidfp is required to render audio; "
            "install with: pip install pysidtracker[audio]"
        ) from exc
    frame_seconds = cycles_per_frame / clock_frequency
    max_frames = max(1, round(seconds / frame_seconds))
    samples = _render_samples(
        FutureComposerPlayer(song).iter_frames(max_frames),
        model=model,
        cycles_per_frame=cycles_per_frame,
        clock_frequency=clock_frequency,
        write_spacing=DEFAULT_WRITE_SPACING,
        device=device,
    )
    return samples, device_sampling_frequency(device)


def render_wav(song: Song, dst, seconds: float = 60.0, **options) -> Path:
    """Render ``song`` to a WAV file; returns the path written.

    Keyword options are those of :func:`render_samples`.
    """
    samples, sampling_frequency = render_samples(song, seconds=seconds, **options)
    write_wav(dst, samples, sampling_frequency)
    return Path(dst)
