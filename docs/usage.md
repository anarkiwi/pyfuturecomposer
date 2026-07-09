# Usage

Reading a `.sid`/`.prg` into a `Song` and iterating per-frame writes is covered
in the [README](../README.md). This document covers the rest of the API. For the
format and playroutine, see [format.md](format.md).

```python
import pyfuturecomposer as fc

song = fc.read("tune.sid")            # PSID/.sid or bare .prg

# Per-frame SID register writes (the writes the playroutine emits each frame).
for writes in fc.iter_frames(song, max_frames=50 * 60):
    ...                               # writes: list[(register, value)]

# Forward-filled 25-register-per-frame snapshot grid (the oracle form).
grid = fc.render_grid(song, nframes=400)

# Register log (clock reg val triples), and WAV via an emulated SID.
fc.write_reglog(fc.iter_register_writes(song, max_frames=2500), "tune.reglog")
fc.render_wav(song, "tune.wav", seconds=30)   # needs the audio extra
```

## Command line

```bash
pyfuturecomposer info   tune.sid
pyfuturecomposer reglog tune.sid tune.reglog --seconds 30
pyfuturecomposer wav    tune.sid tune.wav --seconds 30 --model 8580
```
