"""pyfuturecomposer's renderer for the ``pysidtracker.survey`` whole-song HVSC oracle survey.

    PYTHONPATH=scripts python -m pysidtracker.survey run $HVSC tunes.csv \
        --work .hvsc-survey --render oracle_hvsc:render
"""

import numpy as np

from pysidtracker.cadence import cadence_info

from pyfuturecomposer import FutureComposerPlayer, parse
from pyfuturecomposer.errors import FutureComposerParseError

PLAYER = "^mon/futurecomposer$"


def render(data, song, nframes):
    """Render 1-based ``song`` of a Future Composer ``.sid`` and the variant it decoded."""
    player = FutureComposerPlayer(parse(data), subtune=song - 1)
    if player.variant["signature"] is None:
        raise FutureComposerParseError("no Future Composer player signature")
    info = {**player.variant.as_info(), **cadence_info(data, song)}
    grid = player.render_grid(nframes)
    return np.asarray(grid, np.int16), info
