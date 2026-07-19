from __future__ import annotations


def validate_source_chunks(
    file_bytes: int, chunk_size_bytes: int, chunk_sha256: tuple[str, ...]
) -> None:
    expected_count = (file_bytes + chunk_size_bytes - 1) // chunk_size_bytes
    if len(chunk_sha256) != expected_count:
        raise ValueError("full-corpus chunk count does not reconcile")
    if any(
        len(value) != 64 or any(char not in "0123456789abcdef" for char in value)
        for value in chunk_sha256
    ):
        raise ValueError("full-corpus chunk digest is invalid")
