"""SHA-256 hashing (M3.2) -- the one place this codebase computes a
document's content hash.

Extracted from scripts/upload_documents.py's own `_sha256_of` (M2.3),
which had this logic first; not rewritten, formalised. Same discipline as
M3.1's S3 client: before this module existed, upload_documents.py
computed its own hash inline. That is now the only implementation this
module wraps -- ingest (M3.3), dedupe (M3.4), and the upload script all
call through here, so a change to how a document's identity is computed
happens in one place.

WHY ITS OWN MODULE, not folded into db.py or s3.py: neither is a natural
home. db.py is Postgres-specific (a psycopg.Cursor is threaded through
every function); s3.py is AWS-specific (every function takes a boto3
S3Client). Hashing is a pure, dependency-free computation over bytes with
no service behind it at all -- closer in kind to config.py (a single-
purpose utility nothing else depends on) than to either service wrapper.
Three consumers (ingest, dedupe, upload) span both of those modules'
concerns, which is itself a reason not to nest this inside either one.

ONE FUNCTION, not two: sha256_of_stream(stream) takes anything with a
.read(n) method -- a `Path.open("rb")` file handle or an io.BytesIO
wrapping in-memory bytes both satisfy that interface identically. M3.3
ingests bytes (spec: bytes -> hash -> S3 -> documents row); its caller
wraps them in io.BytesIO(data) and calls sha256_of_stream, rather than
this module providing a separate sha256_of_bytes that would just do that
same wrapping internally -- one real implementation, not two, matching
the task's own instruction. sha256_of_path(path) is a thin convenience
wrapper (`return sha256_of_stream(path.open("rb"))`, with the file
handle closed for the caller) for the two path-based callers
(scripts/upload_documents.py today; M3.4's dedupe will also have a path
when re-hashing a local file, if it ever needs to) -- not a second
implementation, just ergonomics over the one real one.

LARGE FILES: reads in fixed-size chunks (1 MiB), never `.read()`ing the
whole stream at once -- the FY2022 AFS is 9 MB today (confirmed via
services/pipeline's own docs/shoprite_pdf_manifest.md), and interims and
other companies' integrated reports are expected larger. Memory use is
bounded by the chunk size regardless of document size.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

_CHUNK_SIZE = 1024 * 1024  # 1 MiB


class _ReadableStream(Protocol):
    def read(self, size: int = ..., /) -> bytes: ...


def sha256_of_stream(stream: _ReadableStream) -> str:
    """Lowercase hex SHA-256 digest (64 chars) of everything readable
    from `stream`, read in bounded chunks rather than all at once. Does
    NOT close the stream -- the caller opened it and owns its lifecycle
    (matching db.py's own convention of not managing resources it did
    not create).
    """
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(_CHUNK_SIZE), b""):
        digest.update(chunk)
    return digest.hexdigest()


def sha256_of_path(path: Path) -> str:
    """Lowercase hex SHA-256 digest of the file at `path`. Convenience
    wrapper over sha256_of_stream -- opens the file, hashes it, closes
    it. Not a second implementation.
    """
    with path.open("rb") as f:
        return sha256_of_stream(f)
