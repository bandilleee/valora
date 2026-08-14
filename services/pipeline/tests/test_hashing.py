"""Unit tests for valora_pipeline.hashing (M3.2).

No skip logic: the one test that reads a real file
(test_known_file_matches_manifest_recorded_hash) fails loudly if
data/pdfs/ has been moved or the file is missing, rather than skipping.

Known-vector tests assert against literal SHA-256 test vectors (the empty
string and "abc"), not against a value this module itself produced --
this proves sha256_of_stream computes an actual, correct SHA-256, not
merely a value that is internally self-consistent.
"""

from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

from valora_pipeline.hashing import sha256_of_path, sha256_of_stream

REPO_ROOT = Path(__file__).resolve().parents[3]

# Known SHA-256 test vectors (NIST / widely published). Not produced by
# this module -- if sha256_of_stream ever computed the wrong digest,
# these literals would not move to match it.
_SHA256_EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
_SHA256_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

# The FY2022 AFS's hash as recorded in docs/shoprite_pdf_manifest.md
# (produced by the pre-M3.2 implementation in scripts/upload_documents.py
# -- M2.3). Matching it here is a regression check: if the refactor
# changed the hash, every existing S3 key and documents row keyed on it
# would be silently orphaned.
_MANIFEST_KNOWN_FILE = REPO_ROOT / "data" / "pdfs" / "SHP_AFS_FY2022_20220930.pdf"
_MANIFEST_KNOWN_HASH = "4a5f924dcb3f44d59e5f2fa7af1ae8fabd0f02edbb06abf84e373a79b0fbc124"


def test_sha256_of_stream_empty_input_matches_known_vector() -> None:
    assert sha256_of_stream(io.BytesIO(b"")) == _SHA256_EMPTY


def test_sha256_of_stream_abc_matches_known_vector() -> None:
    assert sha256_of_stream(io.BytesIO(b"abc")) == _SHA256_ABC


def test_sha256_of_stream_handles_input_larger_than_one_chunk() -> None:
    # _CHUNK_SIZE is 1 MiB; this input spans several chunks, proving the
    # streaming read loop accumulates across chunk boundaries rather than
    # only hashing the first read().
    payload = b"x" * (3 * 1024 * 1024 + 12345)
    expected = hashlib.sha256(payload).hexdigest()
    assert sha256_of_stream(io.BytesIO(payload)) == expected


def test_output_format_is_lowercase_hex_64_chars() -> None:
    digest = sha256_of_stream(io.BytesIO(b"format check"))
    assert re.fullmatch(r"[0-9a-f]{64}", digest), digest


def test_sha256_of_path_matches_sha256_of_stream_for_the_same_bytes(
    tmp_path: Path,
) -> None:
    payload = b"path and stream must agree"
    f = tmp_path / "sample.bin"
    f.write_bytes(payload)
    assert sha256_of_path(f) == sha256_of_stream(io.BytesIO(payload))


def test_known_file_matches_manifest_recorded_hash() -> None:
    assert _MANIFEST_KNOWN_FILE.is_file(), (
        f"{_MANIFEST_KNOWN_FILE} is missing -- this test needs the real "
        "downloaded PDF, not a fixture, to prove the refactor did not "
        "change the hash recorded in docs/shoprite_pdf_manifest.md."
    )
    assert sha256_of_path(_MANIFEST_KNOWN_FILE) == _MANIFEST_KNOWN_HASH
