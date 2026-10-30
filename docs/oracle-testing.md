# Oracle testing

`tests/test_oracle_hvsc.py` renders a tune with `FutureComposerPlayer` and asserts
the per-frame SID register grid matches [`sidtrace`](https://github.com/anarkiwi/sidtrace)
— a patched `sidplayfp` run in the `anarkiwi/sidtrace` Docker image — frame for
frame. It reuses `pysidtracker.make_oracle_fixtures`, so the resolve/render/frame/
compare machinery is the shared base (see the base package's
[oracle-testing docs](https://github.com/anarkiwi/pysidtracker/blob/main/docs/oracle-testing.md)).

```python
tune_id, oracle_match = make_oracle_fixtures(TUNES, player=FutureComposerPlayer)
```

The comparison covers the start song's whole length (`pysidtracker.song_frames`).

A mismatch fails with pysidtracker's
[whydiff](https://github.com/anarkiwi/pysidtracker/blob/main/docs/whydiff.md)
report: the diverging cell and the Python lines and 6502 instructions its value
came from, side by side.

- **Marked `oracle`**, excluded from the default suite (`-m 'not oracle'`); a
  dedicated CI job runs `pytest -m oracle -n auto` with Docker.
- **Never skipped**: an unavailable tune raises `TuneFetchError` and a failed
  oracle render raises `SidtraceUnavailable`, so a broken download or render
  fails the test instead of hiding a regression.
- HVSC `.sid` files are copyright works: downloaded to pysidtracker's
  `.tunecache` (or read from a local `$HVSC` tree), never committed.

## Coverage

The CI oracle covers the `We R Da Best (tune 2)` reference tune. Other builds
are placed by their variant (see [format](format.md#build-variants)). The HVSC
survey and `scripts/fc_memdiff.py` below measure how far that reaches.

## HVSC oracle survey

[`scripts/oracle_hvsc.py`](../scripts/oracle_hvsc.py) plugs `FutureComposerPlayer`
into the
[`pysidtracker.survey`](https://github.com/anarkiwi/pysidtracker/blob/main/docs/survey.md)
whole-song comparison against the `sidtrace` oracle (Docker), over every subtune
of every HVSC tune SIDId names `MoN/FutureComposer` (`PLAYER`). Its `info` is the
player's `Variant.as_info()`. That is every facet value (`signature`,
`layout`, `init`, `play`, `work`, `tempo` and the table offsets) plus a
`<facet>.src` provenance key, followed by `pysidtracker.cadence.cadence_info`'s
`rsid`, play `trigger`, `speed` (calls per PAL frame) and `dynamic`. A
tune without the FC player signature raises `FutureComposerParseError` (a
`pysidtracker.SidParseError`), which the survey records as `not_decompiled`.

```bash
pip install "pysidtracker[survey]>=0.47.0"
python -m pysidtracker.survey find $HVSC --player '^mon/futurecomposer$' --out .hvsc-survey/tunes.csv
PYTHONPATH=scripts python -m pysidtracker.survey run $HVSC .hvsc-survey/tunes.csv \
    --work .hvsc-survey --render oracle_hvsc:render --jobs 32
python -m pysidtracker.survey report .hvsc-survey/results.csv
python -m pysidtracker.survey triage .hvsc-survey
PYTHONPATH=scripts python -m pysidtracker.survey diff $HVSC .hvsc-survey/tunes.csv <md5>_<song> \
    --work .hvsc-survey --render oracle_hvsc:render
```

`.hvsc-survey/` holds copyright-derived traces and is gitignored.

## Lockstep check against the tune's own code

`scripts/fc_memdiff.py` runs `FutureComposerPlayer` frame by frame beside
`pysidtracker.oracle.EmuPlayer`, which executes the tune's own 6502 code. It
compares the SID registers and the work area, and names each work byte by its
reference-build address. It needs no Docker. Given a survey `find` CSV, it
groups every tune by the first byte that diverges:

```bash
python scripts/fc_memdiff.py tune.sid --frames 500
python scripts/fc_memdiff.py .hvsc-survey/tunes.csv --hvsc $HVSC --jobs 64
```


## Translation validation

`tests/test_tv.py` proves spec routines equal to the reference tune's 6502 code
for all initial memory (`pysidtracker.playspec.tv.validate`):

- `clock.reinit` against `$1d74` (default suite);
- `clock.cold_init` against `$1d65` (marked `oracle`);
- a spec with a wrong seed byte is refuted, and `tv.replay` reproduces the
  counterexample on the CPU (marked `oracle`).

- `voice[x].tv_note_row` against `$193a..$1d35` for each voice (default suite): the
  note-row loader, the pattern position step and the end-of-pattern test, proved as
  a stretch with `validate(..., stop=0x1d35)`. The routine reloads the voice index
  from `$FF`, so the proof assumes `$FF` holds the voice.

## Tunes that still diverge

Over the 150-tune corpus (`tests/fixtures/fc_corpus.txt`), 133 tunes match
`pysidtracker.oracle.EmuPlayer`, the tune's own 6502 run, for their whole song
(`pysidtracker.song_length`). The other 17 split in two.

Another player version (issue #17): 12 tunes whose play code shares little with
the reference routine, about 550 to 1600 instructions apart once addresses are
normalised. The spec does not describe them, and their layouts are mostly
undetected. They diverge at frame 0.

- `Christmas_1989_tune_2`, `Saturn_part_3`, `Spijkerhoek_Theme`,
  `Summernight_Surprise_tune_1`, `Farwell_Cult_part_2`, `Game_On_1989_11`,
  `Amiga_Theme`, `Shove`, `Zanshin`, `Chrome_Met1`, `Reggae_Example`,
  `Be_Original_part_8`.

The reference routine with local edits of the player code: 5 tunes, within 150
instructions of the reference, each differing at a site of its own. A layout
facet per edit would not generalise, so they are left as they are.

| Tune | First differing frame | Cause |
| --- | --- | --- |
| `Swiss_National_Hymn` | 1 | the hard-frequency low-byte write is `STA $D000,Y`, not `$D400,Y` |
| `For_FBR` | 1 | code equal to the reference except the filter pointer, yet Y is 0 at one hard-frequency write |
| `Your_Label` | 13 | `39` where the reference has `38` (SEC) at `$1B7D` |
| `Jungle_Gardenia` | 281 | the default-filter block jumps to `$1ADC`, skipping the `LDX $ff` at `$1ACE` |
| `Forever_Tonight` | 6576 | not traced |

To find where a tune diverges, run `scripts/fc_memdiff.py` on it: it plays
`FutureComposerPlayer` beside the tune's own code and names the first differing
register and work byte.
