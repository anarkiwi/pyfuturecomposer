"""Exceptions raised by pyfuturecomposer."""


class FutureComposerError(Exception):
    """Base class for all pyfuturecomposer errors."""


class SidParseError(FutureComposerError):
    """A PSID/PRG image (or byte string) could not be parsed."""
