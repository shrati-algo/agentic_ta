"""Parse chassis number and camera side from an image filename.

The filename convention is a CONTRACT with Plant Engineering (TRD Section 4.2).
The regex below is the single source of truth.  Do not change it without
coordinating with Plant Engineering and adding an ADR.

Valid examples::

    MALBB51BLPM123456_L.jpg
    M3456789012345678_R.png
    MALBB51BLPM123456_L_001.jpeg
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from tad.api.errors import BadFilename

FILENAME_RE = re.compile(
    r"^(?P<chassis_no>[A-HJ-NPR-Z0-9]{17})"
    r"_(?P<camera>[LR])"
    r"(?:_\d+)?"
    r"\.(?:jpg|jpeg|png)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedName:
    """Result of parsing a valid image filename."""

    chassis_no: str
    camera_side: Literal["L", "R"]


def parse_filename(name: str) -> ParsedName:
    """Extract ``chassis_no`` and ``camera_side`` from *name*.

    Parameters
    ----------
    name:
        The bare filename (no directory component), e.g. ``"ABC12_L.jpg"``.

    Returns
    -------
    ParsedName
        A frozen dataclass with the parsed fields.

    Raises
    ------
    BadFilename
        If *name* does not match :data:`FILENAME_RE`.
    """
    m = FILENAME_RE.match(name)
    if not m:
        raise BadFilename(f"filename does not match convention: {name}")
    return ParsedName(
        chassis_no=m["chassis_no"].upper(),
        camera_side=m["camera"].upper(),  # type: ignore[arg-type]
    )
