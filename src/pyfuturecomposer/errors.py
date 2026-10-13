"""Exceptions for pyfuturecomposer, built by :func:`pysidtracker.make_package_errors`.

``FutureComposerParseError`` subclasses both ``FutureComposerError`` and
:class:`pysidtracker.SidParseError` ("not a decodable Future Composer tune");
``SidParseError`` is kept as its backward-compatible alias.
"""

from pysidtracker import make_package_errors

FutureComposerError, FutureComposerParseError, SidFormatError = make_package_errors(
    "FutureComposer"
)
SidParseError = FutureComposerParseError

__all__ = [
    "FutureComposerError",
    "FutureComposerParseError",
    "SidFormatError",
    "SidParseError",
]
