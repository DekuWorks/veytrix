"""Local body budgets for the paper recorders.

TradersPost documents a 16,384-byte body, 32 levels of nesting, 1,024 structural
characters, and 64 formula values. Those figures are applied here as a local
cap. This module does not send the body anywhere.
"""

from __future__ import annotations

MAX_BODY_BYTES = 16_384
MAX_NESTING = 32
MAX_STRUCTURAL = 1_024
MAX_FORMULAS = 64
TIMEOUT_SECONDS = 3.0
ID_PATTERN = r"^[a-z0-9][a-z0-9-]{0,31}$"
KEY_PATTERN = r"^[A-Za-z0-9_.:-]{1,128}$"
