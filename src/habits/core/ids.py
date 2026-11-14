"""Time-ordered UUIDv7 identifiers."""

from __future__ import annotations

import sys

if sys.version_info >= (3, 14):
    import uuid

    def new_id() -> str:
        return str(uuid.uuid7())

else:
    import uuid_utils

    def new_id() -> str:
        return str(uuid_utils.uuid7())
