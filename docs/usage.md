# Usage

Reading a `.sid`/`.prg` into a `Song` and iterating per-frame writes is covered
in the [README](../README.md). This document covers the rest of the API. For the
format and playroutine, see [format.md](format.md).

```python
import pyfuturecomposer as fc

song = fc.read("tune.sid")            # PSID/.sid or bare .prg

# The playroutine is a pysidtracker MemPlayer (accepts a Song, bytes, or .sid/.prg).
player = fc.FutureComposerPlayer(song)

# Per-frame SID register writes (frame 0 is the full 25-register file; later
# frames are only the changed registers).
for writes in player.iter_frames(50 * 60):
    ...                               # writes: list[(register, value)]

# Forward-filled 25-register-per-frame snapshot grid (the oracle form).
grid = fc.FutureComposerPlayer(song).render_grid(400)

# Register log (clock reg val triples), and WAV via an emulated SID.
fc.write_reglog(fc.iter_register_writes(song, max_frames=2500), "tune.reglog")
fc.render_wav(song, "tune.wav", seconds=30)   # needs the audio extra
```

## Export (write a form Future Composer can load)

A Future Composer module is the driver code plus the authored data (sequences,
patterns, instruments, modulation tables) held inline in one C64 image; the
editor's native module is exactly that image as a plain C64 program. `to_prg`
emits it (two-byte little-endian load address + driver/data), and a canonical
build (load `$1800`, play `$1806` — `fc.is_editor_native(song)`) loads straight
back into the FutureComposer editor. `to_sid` re-wraps the same image as a PSID,
preserving init/play and the name/author/released metadata, so
`fc.read(fc.to_sid(song)) == song` and HVSC players still play it. A relocated
rip is written verbatim at its own load address — valid and round-trippable, but
only the `$1800` build loads directly into the editor.

```python
fc.write_prg(song, "tune.prg")        # editor-loadable C64 module
fc.write_sid(song, "tune.sid")        # PSID re-wrap (byte-exact model round-trip)
fc.to_prg(song)                       # -> bytes
```

## Command line

```bash
pyfuturecomposer info   tune.sid
pyfuturecomposer reglog tune.sid tune.reglog --seconds 30
pyfuturecomposer wav    tune.sid tune.wav --seconds 30 --model 8580
pyfuturecomposer export tune.sid tune.prg          # editor module (.prg or .sid by extension)
pyfuturecomposer export tune.sid out.bin --format sid
```
