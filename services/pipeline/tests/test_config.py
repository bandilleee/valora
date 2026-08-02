import pytest
from pydantic import ValidationError

from valora_pipeline.config import Settings

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


def test_resolves_to_localstack_when_endpoint_url_set(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, AWS_ENDPOINT_URL="http://localhost:4566")
    assert settings.uses_local_stack is True
    assert settings.aws_endpoint_url == "http://localhost:4566"


def test_resolves_to_real_aws_when_endpoint_url_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
    settings = _settings(monkeypatch)
    assert settings.uses_local_stack is False
    assert settings.aws_endpoint_url is None


def test_resolves_to_real_aws_when_endpoint_url_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, AWS_ENDPOINT_URL="")
    assert settings.uses_local_stack is False
    assert settings.aws_endpoint_url is None


def test_missing_required_value_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for key, value in REQUIRED_ENV.items():
        if key != "DATABASE_URL":
            monkeypatch.setenv(key, value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
