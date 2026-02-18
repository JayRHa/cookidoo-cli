"""Constants and mappings for the CLI."""

from __future__ import annotations

from typing import Final

SUBSCRIPTION_TYPES: Final[dict[str, str]] = {
    "NONE": "free",
    "TRIAL": "trial",
    "REGULAR": "premium",
}

DEFAULT_COUNTRY: Final = "ch"
DEFAULT_LANGUAGE: Final = "de-CH"
