"""Typed, validated application configuration.

Reads from the repository-root ``.env`` (if present) and process environment
variables. Required fields have no defaults, so constructing ``Settings()``
raises ``pydantic.ValidationError`` — loudly, at startup — if anything is
missing, rather than returning ``None`` for a caller to trip over later.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root_env_file() -> Path | None:
    """Locate the repo-root .env regardless of the process's cwd."""
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists():
            return parent / ".env"
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_repo_root_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    aws_region: str
    aws_access_key_id: str
    aws_secret_access_key: str
    s3_bucket: str
    aws_endpoint_url: str | None = None

    @field_validator("aws_endpoint_url", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: str | None) -> str | None:
        """An empty AWS_ENDPOINT_URL means the same thing as unset."""
        return value or None

    @property
    def uses_local_stack(self) -> bool:
        """True when pointed at LocalStack; False means real AWS.

        This is the one place that branches on environment — callers building
        an S3/SQS client just pass ``aws_endpoint_url`` straight through
        (``None`` for real AWS, a URL for LocalStack) instead of writing
        their own if/else.
        """
        return self.aws_endpoint_url is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
