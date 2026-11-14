"""Shared wire-safe primitives. Money is integer paise, never a coerced float/string."""

from typing import Annotated

from pydantic import AfterValidator, Field, StringConstraints

MAX_SAFE_INTEGER = 9_007_199_254_740_991  # Exact in both Python and a JS number.
Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


def require_message_content(value: str) -> str:
    if not value.strip():
        raise ValueError("Message content cannot be blank")
    return value


MessageText = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=False, min_length=1, max_length=4000),
    AfterValidator(require_message_content),
]
InputHash = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Paise = Annotated[int, Field(strict=True, ge=-MAX_SAFE_INTEGER, le=MAX_SAFE_INTEGER)]
Money = Annotated[int, Field(strict=True, ge=0, le=MAX_SAFE_INTEGER)]
Count = Annotated[int, Field(strict=True, ge=0, le=MAX_SAFE_INTEGER)]
