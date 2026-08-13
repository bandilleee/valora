"""Thin S3 helper: client construction and the handful of operations
M3.3 (ingest) and M3.5 (retrieve) actually need.

The ONE place in this codebase that constructs a boto3 S3 client. Before
this module existed, services/pipeline/scripts/upload_documents.py (M2.3)
built its own client inline; that construction is now imported from here
instead (see that script's diff) specifically so a second copy never
reappears. Any future S3 consumer imports create_client from here, not
boto3.client("s3") directly.

Endpoint resolution matches M0.8's rule exactly, and is a DATA difference,
never a caller-visible branch: AWS_ENDPOINT_URL, region, and credentials
all come from valora_pipeline.config.get_settings(), never os.environ
directly. endpoint_url is passed straight through --
settings.aws_endpoint_url is already None for real AWS and a URL for
LocalStack (config.py's own uses_local_stack docstring: "callers building
an S3/SQS client just pass aws_endpoint_url straight through instead of
writing their own if/else"). No function in this module inspects
uses_local_stack or otherwise asks "am I local or real". The one
LocalStack-specific line -- forcing path-style addressing -- is not a
behavioural branch either: it is a constant request-signing detail
LocalStack requires and real AWS accepts equally, so it is applied
unconditionally rather than gated on environment (see create_client).

Deliberately out of scope for this milestone (M3.1), and why -- same
discipline as db.py's own "Deliberately out of scope" section:

- Listing/paginating a bucket's contents -- no consumer needs it yet.
  M3.5 (retrieve) fetches one known object by key; nothing here scans a
  prefix.
- Delete -- spec principle 3 and §5.2 ("Never modified, never deleted")
  make object deletion a thing this project should not casually have a
  one-line helper for. If a real deletion need appears (e.g. a takedown
  request), that is a deliberate decision made at the call site, not a
  convenience wrapper here.
- Presigned URLs -- no consumer needs one yet (the add-in and web app
  read facts through the API, per spec §7's "no privileged internal
  path"; nothing serves a raw S3 object straight to a browser today).
- Multipart upload management -- boto3's own upload_file/upload_fileobj
  already handle the multipart threshold transparently (confirmed during
  M2.3's work); this module does not need to expose multipart as a
  separate concept.
- Retry/backoff policy -- botocore already retries transient errors by
  default; no evidence yet that this project needs a policy beyond that
  default. Add one when a concrete failure mode shows it is needed.
- Connection pooling / a long-lived client cache -- M3.3 and M3.5 are
  batch/single-process pipeline jobs, not a concurrent server, the same
  reasoning db.py gives for skipping connection pooling. create_client()
  is cheap; call it once per script run, as upload_documents.py already
  does.

Object lock: ensure_bucket requests it at creation
(ObjectLockEnabledForBucket=True), matching M2.3's own upload_documents.py
behaviour and spec §5.2's "versioned storage with object lock". Per
CLAUDE.md and M2.3's own finding, LocalStack community accepts the
object-lock API calls and reports the configuration back correctly on
read, but does NOT enforce it (a delete against an actively-retained
object succeeds locally when real S3 would refuse it) -- confirmed live
during M2.3, not re-verified here since nothing about that finding
changes by moving the code into this module. Any assertion this module
made about retention actually blocking a delete would be untestable
against LocalStack for the same reason; none is made. Real enforcement
is verifiable only against real AWS, i.e. only from M10.2 onward -- see
this module's own test suite for exactly what is and is not proven here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from valora_pipeline.config import Settings, get_settings

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


def create_client(settings: Settings | None = None) -> S3Client:
    """Constructs an S3 client from config -- never os.environ directly.

    settings is an optional parameter (defaulting to get_settings()) so a
    caller -- chiefly this module's own test suite -- can construct a
    client against an explicit Settings object without relying on process
    environment variables or get_settings()'s lru_cache, the same reason
    valora_pipeline.db's functions take a cursor rather than opening their
    own connection: dependency injection at the boundary, not a global.

    Path-style addressing (Config(s3={"addressing_style": "path"})) is
    applied unconditionally, not gated on uses_local_stack: LocalStack
    requires it (virtual-hosted-style requests resolve to a hostname
    LocalStack does not serve), and real AWS accepts path-style requests
    equally -- SDK-level backward compatibility, not a special path S3
    itself treats differently. This keeps the branch a property of the
    endpoint being addressed, not a decision this module makes about which
    environment it thinks it is in.
    """
    if settings is None:
        settings = get_settings()
    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        endpoint_url=settings.aws_endpoint_url,
        config=Config(s3={"addressing_style": "path"}),
    )


def ensure_bucket(s3: S3Client, bucket: str, region: str) -> None:
    """Creates the bucket if absent; no-op if present. Enables versioning
    either way (spec §5.2's "versioned storage"). See the module docstring
    on object lock and LocalStack's lack of enforcement.

    Extracted verbatim (in behaviour) from M2.3's upload_documents.py
    _ensure_bucket -- the versioning-check-before-put_bucket_versioning
    logic below exists because a bucket created with
    ObjectLockEnabledForBucket=True is versioned implicitly, and S3
    REJECTS an explicit PutBucketVersioning call afterward
    (InvalidBucketState) -- confirmed live during M2.3.
    """
    try:
        s3.head_bucket(Bucket=bucket)
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

    current = s3.get_bucket_versioning(Bucket=bucket).get("Status")
    if current != "Enabled":
        s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})


def object_exists(s3: S3Client, bucket: str, key: str) -> bool:
    """True if key exists in bucket, False on a clean 404. Any other
    error (auth failure, network error, wrong region) propagates -- this
    function answers "does the object exist", not "did the check
    succeed", and conflating the two would let a real infrastructure
    failure masquerade as a false negative.
    """
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status == 404:
            return False
        raise


def put_object(s3: S3Client, bucket: str, key: str, data: bytes) -> None:
    """Uploads data to bucket/key. No conditional-write / conflict
    handling here -- that is M3.3's job (content-addressed keys mean a
    conflict implies a hash collision or a corrupted bucket, a decision
    already made once by M2.3's upload_documents.py and left to whichever
    caller cares to re-derive it, not duplicated here as a generic
    policy).
    """
    s3.put_object(Bucket=bucket, Key=key, Body=data)


def get_object(s3: S3Client, bucket: str, key: str) -> bytes:
    """Downloads bucket/key and returns its bytes. Raises the underlying
    ClientError (e.g. NoSuchKey) uncaught -- a caller asking for a
    specific key expects it to exist; a missing object is the caller's
    error to handle, not a None this function invents.
    """
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()
