"""Audio rendering via a fake SID device (no pyresidfp dependency)."""

from array import array

import pytest

from pyfuturecomposer import audio, reader
from pyfuturecomposer.errors import FutureComposerError


class _FakeSid:
    """Minimal device: one sample per clock call, counts register writes."""

    def __init__(self):
        self.sampling_frequency = 44100
        self.writes = 0

    def write_register(self, reg, value):  # pylint: disable=unused-argument
        self.writes += 1

    def clock(self, _delta):
        return array("h", [0])


def test_render_samples_with_fake_device(tune_path):
    device = _FakeSid()
    samples, freq = audio.render_samples(
        reader.read(tune_path), seconds=0.1, device=device
    )
    assert freq == 44100
    assert len(samples) > 0
    assert device.writes > 0


def test_render_wav_writes_file(tune_path, tmp_path):
    out = audio.render_wav(
        reader.read(tune_path),
        tmp_path / "out.wav",
        seconds=0.05,
        device=_FakeSid(),
    )
    assert out.exists()
    assert out.read_bytes()[:4] == b"RIFF"


def test_write_wav_accepts_iterables(tmp_path):
    audio.write_wav(tmp_path / "x.wav", [0, 1, 2, 3], 8000)
    assert (tmp_path / "x.wav").exists()


def test_bad_model(tune_path):
    with pytest.raises(FutureComposerError):
        audio.render_samples(reader.read(tune_path), model="nope", device=_FakeSid())


def test_default_device_requires_pyresidfp(monkeypatch, tune_path):
    """Without pyresidfp installed, a helpful error is raised."""
    import builtins  # pylint: disable=import-outside-toplevel

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name.startswith("pyresidfp"):
            raise ImportError("no pyresidfp")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    with pytest.raises(FutureComposerError):
        audio.render_samples(reader.read(tune_path), seconds=0.01)
