"""Exceptions raised by pyfuturecomposer.

The hierarchy is built by the shared :func:`pysidtracker.make_package_errors`, so
:class:`FutureComposerError` roots at :class:`pysidtracker.SidError` and the parse
error subclasses BOTH it and the base :class:`pysidtracker.SidParseError` (a base
``except SidParseError`` still catches the package's own-named error).
"""

from pysidtracker import make_package_errors

FutureComposerError, SidParseError, SidFormatError = make_package_errors(
    "FutureComposer"
)
