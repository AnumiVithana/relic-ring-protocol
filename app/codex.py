"""
Numeric base ("codex") conversion between ASCII byte values and arbitrary
integer bases, matching the worked example in the brief.

    'H' (ASCII 72) -> Base 5  -> "242"   (72 = 2*25 + 4*5 + 2*1)
    'H' (ASCII 72) -> Base 14 -> "52"    (72 = 5*14 + 2*1)

"""
from __future__ import annotations

DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def int_to_base(value: int, base: int) -> str:
    """Convert a non-negative integer to a string in the given base (2-36)."""
    if base < 2 or base > len(DIGITS):
        raise ValueError(f"Unsupported base: {base}")
    if value < 0:
        raise ValueError("int_to_base only supports non-negative integers (ASCII byte values).")
    if value == 0:
        return "0"

    digits = []
    n = value
    while n > 0:
        digits.append(DIGITS[n % base])
        n //= base
    return "".join(reversed(digits))


def base_to_int(token: str, base: int) -> int:
    """Convert a string in the given base back to an integer."""
    if base < 2 or base > 36:
        raise ValueError(f"Unsupported base: {base}")
    return int(token, base)


def ascii_bytes(text: str) -> list[int]:
    """Raw payload -> ASCII byte values """
    return [ord(c) for c in text]


def bytes_to_ascii_text(byte_values: list[int]) -> str:
    return "".join(chr(b) for b in byte_values)


def encode_to_codex(byte_values: list[int], codex_base: int) -> list[str]:
    """
    ASCII byte values -> list of per-character tokens in the destination
    planet's codex (numeric base). Each byte is encoded independently.
    """
    return [int_to_base(b, codex_base) for b in byte_values]


def decode_from_codex(tokens: list[str], codex_base: int) -> list[int]:
    """Codex tokens -> ASCII byte values (inverse of encode_to_codex)."""
    return [base_to_int(t, codex_base) for t in tokens]


def bit_width_for_base(codex_base: int) -> int:
    """
    Fixed bit-width needed to represent the largest possible ASCII byte (255)
    in the given codex base, so a flattened binary stream can be split back
    into individual tokens unambiguously on arrival.
    """
    max_value = 255
    return max_value.bit_length()  
    


def serialize_to_binary_stream(tokens: list[str], codex_base: int) -> tuple[str, int]:
    """
    Simulate the "Void Transmission Stream" step - flatten the per-character
    codex tokens into a single binary string for transmission across the
    vacuum. Returns (bitstream, bit_width_per_token).
    """
    bit_width = bit_width_for_base(codex_base)
    chunks = []
    for tok in tokens:
        value = base_to_int(tok, codex_base)
        chunks.append(format(value, f"0{bit_width}b"))
    return "".join(chunks), bit_width


def deserialize_binary_stream(stream: str, bit_width: int, codex_base: int) -> list[str]:
    """Inverse of serialize_to_binary_stream: binary stream -> codex tokens."""
    tokens = []
    for i in range(0, len(stream), bit_width):
        chunk = stream[i : i + bit_width]
        value = int(chunk, 2)
        tokens.append(int_to_base(value, codex_base))
    return tokens
