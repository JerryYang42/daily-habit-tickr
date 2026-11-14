"""Fractional (lexicographic) sort keys.

A key is a non-empty string over ``DIGITS`` that never ends in the zero digit.
Between any two keys another key can always be generated, so reordering a row
only ever rewrites that one row.
"""

from __future__ import annotations

import string

DIGITS = string.digits + string.ascii_uppercase + string.ascii_lowercase  # ASCII-sorted
_ZERO = DIGITS[0]


def _midpoint(a: str, b: str | None) -> str:
    """A string strictly between a and b (b=None means +infinity). a may be ''."""
    if b is not None:
        # Copy the shared prefix (treating a as zero-padded).
        n = 0
        while n < len(b) and (a[n] if n < len(a) else _ZERO) == b[n]:
            n += 1
        if n > 0:
            return b[:n] + _midpoint(a[n:], b[n:])
    da = DIGITS.index(a[0]) if a else 0
    if b is None:
        # Appending is the common case: step by one digit so keys stay short.
        if not a:
            return DIGITS[len(DIGITS) // 2]
        if da + 1 < len(DIGITS):
            return DIGITS[da + 1]
        return DIGITS[da] + _midpoint(a[1:], None)
    db = DIGITS.index(b[0])
    if db - da > 1:
        return DIGITS[(da + db) // 2]
    if len(b) > 1:
        return b[0]
    return DIGITS[da] + _midpoint(a[1:], None)


def key_between(before: str | None, after: str | None) -> str:
    """A key that sorts strictly after `before` and strictly before `after`.

    Either side may be None (open-ended).
    """
    if before is not None and after is not None and before >= after:
        raise ValueError(f"{before!r} must sort before {after!r}")
    for k in (before, after):
        if k is not None and (not k or k.endswith(_ZERO) or any(c not in DIGITS for c in k)):
            raise ValueError(f"invalid sort key {k!r}")
    return _midpoint(before or "", after)
