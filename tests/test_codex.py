import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.codex import ascii_bytes, bytes_to_ascii_text, decode_from_codex, encode_to_codex


def test_hello_world_base5_matches_brief_example():
    text = "Hello world"
    b = ascii_bytes(text)
    assert b == [72, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100]

    base5 = encode_to_codex(b, 5)
    assert base5 == ["242", "401", "413", "413", "421", "112", "434", "421", "424", "413", "400"]


def test_hello_world_base14_matches_brief_example():
    text = "Hello world"
    b = ascii_bytes(text)
    base14 = encode_to_codex(b, 14)
    assert base14 == ["52", "73", "7A", "7A", "7D", "24", "87", "7D", "82", "7A", "72"]


def test_round_trip_through_multiple_bases():
    text = "The quick brown fox JUMPS over 42 lazy dogs!"
    b = ascii_bytes(text)
    for base in (2, 3, 5, 8, 10, 14, 16, 20, 36):
        encoded = encode_to_codex(b, base)
        decoded = decode_from_codex(encoded, base)
        assert decoded == b
        assert bytes_to_ascii_text(decoded) == text


if __name__ == "__main__":
    test_hello_world_base5_matches_brief_example()
    test_hello_world_base14_matches_brief_example()
    test_round_trip_through_multiple_bases()
    print("All codex tests passed.")
