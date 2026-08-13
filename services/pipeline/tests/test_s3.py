"""Unit tests for valora_pipeline.s3 (M3.1).

No skip logic anywhere in this file: LocalStack being unreachable must
fail these tests, not silently skip them -- same discipline as
test_db.py's own database-dependent suite.

Round-trip tests use a fixture-scoped key prefix
(tests/valora-s3-tests/<uuid>/...) and delete every object they create at
teardown, so re-running never accumulates objects in the shared LocalStack
bucket the way scripts/upload_documents.py's own real documents do.

What this file proves, and what it deliberately does NOT: it proves
endpoint resolution differs correctly between LocalStack-configured and
real-AWS-configured Settings (construction only, no network call for the
real-AWS case -- there is no real bucket to call), and it proves the
LocalStack round-trip path works end to end. It does NOT and cannot prove
"works against real S3" -- there is no AWS account/bucket in this
environment. See valora_pipeline.s3's own module docstring and
PROGRESS.md's M3.1 entry for the explicit split between what is proven
here and what remains unproven until M10.2 creates a real bucket.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest

from valora_pipeline.config import Settings
from valora_pipeline.s3 import create_client, ensure_bucket, get_object, object_exists, put_object

REQUIRED_ENV = {
    "DATABASE_URL": "postgres://valora:valora@localhost:5432/valora",
    "AWS_REGION": "af-south-1",
    "AWS_ACCESS_KEY_ID": "test",
    "AWS_SECRET_ACCESS_KEY": "test",
    "S3_BUCKET": "valora-documents-dev",
}


def _settings(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> Settings:
    for key, value in {**REQUIRED_ENV, **overrides}.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)  # type: ignore[call-arg]


@pytest.fixture
def local_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    return _settings(monkeypatch, AWS_ENDPOINT_URL="http://localhost:4566")


@pytest.fixture
def key_prefix() -> str:
    """A fresh prefix per test, so parallel or repeated runs never collide
    on the same key -- confirmed necessary since the bucket is shared with
    scripts/upload_documents.py's own real documents (M2.3), which this
    suite must never touch or delete.
    """
    return f"tests/valora-s3-tests/{uuid.uuid4()}"


@pytest.fixture
def s3_client(local_settings: Settings, key_prefix: str) -> Iterator[object]:
    client = create_client(local_settings)
    ensure_bucket(client, local_settings.s3_bucket, local_settings.aws_region)
    try:
        yield client
    finally:
        # Clean up every object this test created under its own prefix --
        # never a bucket-wide delete, never touching real documents.
        response = client.list_objects_v2(Bucket=local_settings.s3_bucket, Prefix=key_prefix)
        for obj in response.get("Contents", []):
            client.delete_object(Bucket=local_settings.s3_bucket, Key=obj["Key"])


def test_round_trip_put_exists_get_returns_identical_bytes(
    s3_client: object, local_settings: Settings, key_prefix: str
) -> None:
    key = f"{key_prefix}/round-trip.bin"
    payload = b"valora M3.1 round-trip test payload \x00\x01\xff"

    assert object_exists(s3_client, local_settings.s3_bucket, key) is False  # type: ignore[arg-type]

    put_object(s3_client, local_settings.s3_bucket, key, payload)  # type: ignore[arg-type]

    assert object_exists(s3_client, local_settings.s3_bucket, key) is True  # type: ignore[arg-type]
    retrieved = get_object(s3_client, local_settings.s3_bucket, key)  # type: ignore[arg-type]
    assert retrieved == payload


def test_object_exists_false_for_key_that_was_never_written(
    s3_client: object, local_settings: Settings, key_prefix: str
) -> None:
    key = f"{key_prefix}/never-written.bin"
    assert object_exists(s3_client, local_settings.s3_bucket, key) is False  # type: ignore[arg-type]


def test_ensure_bucket_is_idempotent(local_settings: Settings) -> None:
    client = create_client(local_settings)
    # Calling twice must not raise -- the second call hits the "bucket
    # already exists" / "versioning already enabled" branches, not the
    # create-bucket / enable-versioning branches.
    ensure_bucket(client, local_settings.s3_bucket, local_settings.aws_region)
    ensure_bucket(client, local_settings.s3_bucket, local_settings.aws_region)

    status = client.get_bucket_versioning(Bucket=local_settings.s3_bucket).get("Status")
    assert status == "Enabled"


def test_create_client_with_endpoint_url_set_targets_local_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch, AWS_ENDPOINT_URL="http://localhost:4566")
    client = create_client(settings)
    assert client.meta.endpoint_url == "http://localhost:4566"


def test_create_client_with_endpoint_url_unset_targets_real_aws(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
    settings = _settings(monkeypatch)
    # Construction only -- no network call. There is no real AWS account
    # in this environment, so this test can prove endpoint RESOLUTION
    # (the client is built pointing at the real regional endpoint, not
    # LocalStack), not that a real S3 call succeeds. See the module
    # docstring for the honest split.
    client = create_client(settings)
    assert client.meta.endpoint_url == f"https://s3.{settings.aws_region}.amazonaws.com"


def test_create_client_with_endpoint_url_blank_targets_real_aws(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch, AWS_ENDPOINT_URL="")
    client = create_client(settings)
    assert client.meta.endpoint_url == f"https://s3.{settings.aws_region}.amazonaws.com"
