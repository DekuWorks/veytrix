"""Pure-Python Keccak-256 (the Ethereum variant, not NIST SHA3-256).

Used for function selectors and EIP-55 checksums so the core package works
without web3 installed. Slow, but only ever hashes short inputs.
"""

from __future__ import annotations

_MASK = (1 << 64) - 1
_RATE = 136


def _rol(value: int, shift: int) -> int:
    shift %= 64
    return ((value << shift) | (value >> (64 - shift))) & _MASK


def _round_constants() -> list[int]:
    constants: list[int] = []
    register = 1
    for _ in range(24):
        constant = 0
        for j in range(7):
            register = ((register << 1) ^ ((register >> 7) * 0x71)) & 0xFF
            if register & 2:
                constant |= 1 << ((1 << j) - 1)
        constants.append(constant)
    return constants


_RC = _round_constants()


def _permute(lanes: list[list[int]]) -> None:
    for constant in _RC:
        c = [lanes[x][0] ^ lanes[x][1] ^ lanes[x][2] ^ lanes[x][3] ^ lanes[x][4] for x in range(5)]
        d = [c[(x + 4) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                lanes[x][y] ^= d[x]
        x, y = 1, 0
        current = lanes[x][y]
        for t in range(24):
            x, y = y, (2 * x + 3 * y) % 5
            current, lanes[x][y] = lanes[x][y], _rol(current, (t + 1) * (t + 2) // 2)
        for y in range(5):
            row = [lanes[x][y] for x in range(5)]
            for x in range(5):
                lanes[x][y] = row[x] ^ ((~row[(x + 1) % 5]) & row[(x + 2) % 5])
        lanes[0][0] ^= constant


def keccak256(data: bytes) -> bytes:
    padded = bytearray(data)
    padded.append(0x01)
    while len(padded) % _RATE:
        padded.append(0)
    padded[-1] |= 0x80

    lanes = [[0] * 5 for _ in range(5)]
    for offset in range(0, len(padded), _RATE):
        block = padded[offset : offset + _RATE]
        for i in range(_RATE // 8):
            x, y = i % 5, i // 5
            lanes[x][y] ^= int.from_bytes(block[8 * i : 8 * i + 8], "little")
        _permute(lanes)

    out = bytearray()
    for i in range(4):
        x, y = i % 5, i // 5
        out += lanes[x][y].to_bytes(8, "little")
    return bytes(out)
