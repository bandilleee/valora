"""Uploads data/pdfs/*.pdf to S3 and records the resulting keys (M2.3).

Repeatable, not one-off: LocalStack state does not survive `make reset` (no
PERSISTENCE flag — see CLAUDE.md's local-ports table), so this script exists
to be re-run, the same role scripts/seed-companies.sh plays for `companies`.
Invoked via `make upload-documents` (a separate, explicit step — see below),
never automatically by `make dev`.

Bucket name and all AWS/LocalStack connection details come from
valora_pipeline.config.get_settings() — the same validated, single-source-of-
truth config every other part of the pipeline uses. Nothing here reads
S3_BUCKET or AWS_ENDPOINT_URL from os.environ directly.

Key scheme: content-addressed, `documents/{sha256}.pdf`. M3.3 defines ingest
as bytes -> sha256 -> S3 -> documents row, which means M3.3 independently
computes the same sha256 from the same bytes and needs a key to put it under.
Using that hash as the key now means M3.3 derives the identical key this
script already used, with zero transformation and zero migration -- not
"compatible with" M3.3's scheme, but literally the same computation. No
filename is embedded in the key: documents.s3_key and documents.sha256 are
two independent, separately-unique columns in the schema (confirmed via
`\\d documents`), so the key does not need to carry human-readable identity --
that lives in the documents row once M3.3 writes it, not in this script.

This script does NOT write anything to the documents table and does NOT
touch pipeline ingest code -- that boundary belongs to M3.3.

Idempotent: re-running uploads every file again unconditionally (S3 PUT is
naturally idempotent for identical bytes at the same key -- a new version is
created under bucket versioning, but content and key are unchanged, so it is
a no-op in every way that matters). If a key already exists with DIFFERENT
content, this is treated as a hard error, not silently overwritten -- see
_check_key_conflicts below. This cannot happen through this script's own
normal operation, since the key is the content's own hash, but is checked
explicitly because the duplicate-rendering fixture (M2.2) makes an adjacent
case -- two different files under two different (correct) keys -- easy to
confuse with it.
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from mypy_boto3_s3 import S3Client

from valora_pipeline.config import get_settings

REPO_ROOT = Path(__file__).resolve().parents[3]
PDF_DIR = REPO_ROOT / "data" / "pdfs"


@dataclass(frozen=True)
class UploadResult:
    filename: str
    sha256: str
    s3_key: str
    size_bytes: int


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _s3_client() -> S3Client:
    settings = get_settings()
    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        endpoint_url=settings.aws_endpoint_url,
        config=Config(s3={"addressing_style": "path"}) if settings.uses_local_stack else None,
    )


def _ensure_bucket(s3: S3Client, bucket: str, region: str) -> None:
    """Creates the bucket if absent; no-op if present. Enables versioning
    either way (spec §5.2's "versioned storage"). Attempts object lock at
    creation time, but see the module docstring on LocalStack community's
    lack of enforcement -- this call succeeds and the bucket reports lock
    enabled, without LocalStack actually blocking a delete against an active
    retention. Real AWS (M10.2) enforces it for real; this is a documented
    local/prod behavioural gap, not a bug in this script.
    """
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"Bucket '{bucket}' already exists.")
    except ClientError as e:
        status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status != 404:
            raise
        if region != "us-east-1":
            s3.create_bucket(
                Bucket=bucket,
                ObjectLockEnabledForBucket=True,
                CreateBucketConfiguration={"LocationConstraint": region},  # type: ignore[typeddict-item]
            )
        else:
            s3.create_bucket(Bucket=bucket, ObjectLockEnabledForBucket=True)
        print(f"Created bucket '{bucket}' (object lock requested).")

    # A bucket created with ObjectLockEnabledForBucket=True is versioned
    # implicitly (object lock requires it) -- S3 then REJECTS an explicit
    # PutBucketVersioning call with InvalidBucketState ("Object Lock
    # configuration is present ... versioning state cannot be changed"),
    # confirmed live against LocalStack. So: check first, only call
    # put_bucket_versioning if a pre-existing bucket somehow lacks it
    # (e.g. one created by hand without object lock).
    current = s3.get_bucket_versioning(Bucket=bucket).get("Status")
    if current == "Enabled":
        print(f"Versioning already enabled on '{bucket}'.")
    else:
        s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
        print(f"Versioning enabled on '{bucket}'.")


def _check_key_conflicts(s3: S3Client, bucket: str, uploads: list[tuple[Path, str, str]]) -> None:
    """Hard-fails if a target key already exists in the bucket with an
    object size that does not match the local file. Since the key IS the
    sha256 of the intended content, a mismatch here can only mean the
    bucket holds different bytes under a key that should be unique to this
    content -- i.e. the content-addressing invariant this script relies on
    has been violated by something else. Silently overwriting would hide
    that.

    Deliberately a size check, not an ETag comparison: S3's ETag is only a
    plain MD5 for single-part uploads. boto3's upload_file() switches to
    multipart above its default threshold (8 MiB), and a multipart ETag is
    `md5-of-part-md5s-N`, not the whole object's MD5 -- confirmed live
    (uploading a 9 MB fixture through this same script produced an ETag
    like `61a60574...-2`, which a plain-MD5 comparison flagged as a false
    conflict on ordinary re-upload). Re-deriving the true multipart ETag
    locally is possible but not worth it here: size mismatch already
    catches the only real failure mode this check exists for (different
    content colliding on the same content-addressed key), and matching
    size plus a content-derived key is sufficient evidence for this
    script's purpose without downloading and rehashing every object.
    """
    for path, _sha256, key in uploads:
        try:
            head = s3.head_object(Bucket=bucket, Key=key)
        except ClientError as e:
            status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 404:
                continue
            raise
        existing_size = head["ContentLength"]
        expected_size = path.stat().st_size
        if existing_size != expected_size:
            print(
                f"ERROR: key '{key}' already exists in '{bucket}' with a "
                f"different size ({existing_size} bytes != expected "
                f"{expected_size} bytes) for {path.name}. This should be "
                "impossible under content-addressed keys -- refusing to "
                "overwrite.",
                file=sys.stderr,
            )
            sys.exit(1)


def main() -> None:
    settings = get_settings()
    bucket = settings.s3_bucket

    if not PDF_DIR.is_dir():
        print(f"ERROR: {PDF_DIR} does not exist.", file=sys.stderr)
        sys.exit(1)

    pdf_paths = sorted(PDF_DIR.glob("*.pdf"))
    if not pdf_paths:
        print(f"ERROR: no PDFs found in {PDF_DIR}.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(pdf_paths)} PDF(s) in {PDF_DIR}.")

    s3 = _s3_client()
    _ensure_bucket(s3, bucket, settings.aws_region)

    uploads: list[tuple[Path, str, str]] = []
    for path in pdf_paths:
        sha256 = _sha256_of(path)
        key = f"documents/{sha256}.pdf"
        uploads.append((path, sha256, key))

    _check_key_conflicts(s3, bucket, uploads)

    results: list[UploadResult] = []
    for path, sha256, key in uploads:
        size = path.stat().st_size
        s3.upload_file(str(path), bucket, key)
        print(f"  uploaded {path.name} -> s3://{bucket}/{key} ({size:,} bytes)")
        results.append(UploadResult(filename=path.name, sha256=sha256, s3_key=key, size_bytes=size))

    print(f"\nDone. {len(results)} object(s) in s3://{bucket}/documents/")
    print("\nfilename,sha256,s3_key,size_bytes")
    for r in results:
        print(f"{r.filename},{r.sha256},{r.s3_key},{r.size_bytes}")


if __name__ == "__main__":
    main()
