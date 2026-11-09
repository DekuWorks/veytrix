"""ABI encoding for a read-only QuoterV2 eth_call. No transaction builders."""

from __future__ import annotations

import re

from veytrix_ai._keccak import keccak256

UINT24_MAX = (1 << 24) - 1

_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
QUOTE_SINGLE_SIG = "quoteExactInputSingle((address,address,uint256,uint24,uint160))"


class AbiError(ValueError):
    pass


def selector(signature: str) -> bytes:
    return keccak256(signature.encode("ascii"))[:4]


def to_checksum_address(address: str) -> str:
    if not isinstance(address, str) or not _ADDRESS.match(address):
        raise AbiError("not a 20-byte hex address")
    lower = address[2:].lower()
    digest = keccak256(lower.encode("ascii")).hex()
    return "0x" + "".join(
        ch.upper() if ch.isalpha() and int(digest[i], 16) >= 8 else ch for i, ch in enumerate(lower)
    )


def require_checksummed(address: str, field: str) -> str:
    try:
        expected = to_checksum_address(address)
    except AbiError as exc:
        raise AbiError(f"{field}: {exc}") from None
    if address != expected:
        raise AbiError(f"{field}: address is not EIP-55 checksummed")
    return address


def _word_uint(value: int, bits: int = 256) -> bytes:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AbiError("integer expected")
    if value < 0 or value >= (1 << bits):
        raise AbiError(f"value out of range for uint{bits}")
    return value.to_bytes(32, "big")


def _word_address(address: str) -> bytes:
    to_checksum_address(address)
    return bytes(12) + bytes.fromhex(address[2:])


def encode_quote_single(token_in: str, token_out: str, amount_in: int, fee: int) -> bytes:
    if not 1 <= fee <= UINT24_MAX:
        raise AbiError("fee tier is out of range")
    return (
        selector(QUOTE_SINGLE_SIG)
        + _word_address(token_in)
        + _word_address(token_out)
        + _word_uint(amount_in)
        + _word_uint(fee, 24)
        + _word_uint(0, 160)
    )


def decode_uint(data: bytes, index: int = 0) -> int:
    word = data[32 * index : 32 * (index + 1)]
    if len(word) != 32:
        raise AbiError("return data too short")
    return int.from_bytes(word, "big")
