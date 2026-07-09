"""Exceptions raised by pyfuturecomposer."""

from pysidtracker import SidError


class FutureComposerError(SidError):
    """Base class for all pyfuturecomposer errors."""


class SidParseError(FutureComposerError):
    """A PSID/PRG image (or byte string) could not be parsed."""
