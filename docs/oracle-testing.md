# Oracle testing

`tests/test_oracle_hvsc.py` renders a tune with `FutureComposerPlayer` and asserts
the per-frame SID register grid matches [`sidtrace`](https://github.com/anarkiwi/sidtrace)
— a patched `sidplayfp` run in the `anarkiwi/sidtrace` Docker image — frame for
frame. It reuses `pysidtracker.make_oracle_fixtures`, so the resolve/render/frame/
compare machinery is the shared base (see the base package's
[oracle-testing docs](https://github.com/anarkiwi/pysidtracker/blob/main/docs/oracle-testing.md)).

```python
tune_id, oracle_match = make_oracle_fixtures(
    TUNES, player=FutureComposerPlayer, frames=250
)
```

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

This player is a faithful transcription of **one** MoN/FutureComposer build (the
`We R Da Best (tune 2)` reference), so byte-exact playback is confirmed for that
build. Other FC builds place their inline tables at different offsets; recognition
of the broader family is covered by `tests/test_corpus.py`, not this oracle.

## HVSC oracle survey

[`scripts/oracle_hvsc.py`](../scripts/oracle_hvsc.py) plugs `FutureComposerPlayer`
into the
[`pysidtracker.survey`](https://github.com/anarkiwi/pysidtracker/blob/main/docs/survey.md)
whole-song comparison against the `sidtrace` oracle (Docker), over every subtune
of every HVSC tune SIDId names `MoN/FutureComposer` (`PLAYER`). Its `info`
reports the decoded build: `layout` (offset of the recognised player signature
from where the transcribed build has it, `constants.OFF_SIGNATURE`; nonzero means
the inline tables sit elsewhere), the `init` and `play` entry offsets from the
load address, and `pysidtracker.cadence.cadence_info`'s `rsid`, play `trigger`,
`speed` (calls per PAL frame) and `dynamic`. A
tune without the FC player signature raises `FutureComposerParseError` (a
`pysidtracker.SidParseError`), which the survey records as `not_decompiled`.

```bash
pip install "pysidtracker[survey]>=0.30.0"
python -m pysidtracker.survey find $HVSC --player '^mon/futurecomposer$' --out .hvsc-survey/tunes.csv
PYTHONPATH=scripts python -m pysidtracker.survey run $HVSC .hvsc-survey/tunes.csv \
    --work .hvsc-survey --render oracle_hvsc:render --jobs 32
python -m pysidtracker.survey report .hvsc-survey/results.csv
python -m pysidtracker.survey triage .hvsc-survey
PYTHONPATH=scripts python -m pysidtracker.survey diff $HVSC .hvsc-survey/tunes.csv <md5>_<song> \
    --work .hvsc-survey --render oracle_hvsc:render
```

`.hvsc-survey/` holds copyright-derived traces and is gitignored.
