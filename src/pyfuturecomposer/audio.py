"""Render Future Composer songs through an emulated SID to samples or WAV.

Thin Future Composer wrappers over the shared :mod:`pysidtracker.audio` renderer.
By default the emulated SID is `pylibresidfp <https://pypi.org/project/pylibresidfp/>`_
(a core pysidtracker dependency).  Any object with ``run(writes, until) -> int16
samples`` (``writes`` an ``(N, 3)`` array of absolute ``(cycle, reg, value)``) and a
``sampling_hz`` attribute can be passed as ``device`` instead (e.g. for tests or a
different emulator).
"""

from pathlib import Path

from pysidtracker.audio import CHIP_MODELS, write_wav
from pysidtracker.audio import render_player_samples, resolve_device
from pysidtracker.errors import AudioUnavailable

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
    **options,
):
    """Render ``song`` on an emulated SID.

    Returns ``(samples, sampling_frequency)`` where samples are signed 16-bit
    mono.  Rendering stops at ``seconds`` (the player loops, so a duration is
    required).  ``options`` (``cycles_per_frame``, ``clock_frequency``,
    ``progress``, ...) are :func:`pysidtracker.audio.render_player_samples`'s.
    """
    try:
        device = resolve_device(
            device, model, sampling_frequency, options.get("clock_frequency")
        )
    except ValueError as exc:
        raise FutureComposerError(str(exc)) from exc
    except AudioUnavailable as exc:
        raise FutureComposerError(
            "pylibresidfp is required to render audio; "
            "install with: pip install pylibresidfp"
        ) from exc
    return render_player_samples(
        FutureComposerPlayer(song),
        seconds=seconds,
        model=model,
        device=device,
        **options,
    )


def render_wav(song: Song, dst, seconds: float = 60.0, **options) -> Path:
    """Render ``song`` to a WAV file; returns the path written.

    Keyword options are those of :func:`render_samples`.
    """
    samples, sampling_frequency = render_samples(song, seconds=seconds, **options)
    write_wav(dst, samples, sampling_frequency)
    return Path(dst)
