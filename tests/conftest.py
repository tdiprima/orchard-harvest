"""Shared fixtures: isolate tests from the developer's environment."""

import pytest

ENV_VARS = (
    "ORCID_API_BASE_URL",
    "ORCID_AFFILIATION",
    "ORCID_MAX_AUTHORS",
    "ORCID_MAX_WORKS",
    "ORCID_REQUEST_TIMEOUT",
    "ORCID_ACCESS_TOKEN",
    "LOG_LEVEL",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
