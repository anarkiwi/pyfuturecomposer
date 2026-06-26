#!/bin/sh
set -e
black --check src/pyfuturecomposer tests scripts
pylint src/pyfuturecomposer tests scripts
pytest --cov=pyfuturecomposer --cov-report=term-missing --cov-fail-under=85
