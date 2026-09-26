"""Tests for environment-driven configuration."""

import pytest

from orcid_harvest.config import ConfigError, load_config


@pytest.mark.parametrize("value", ["", "   ", "pub.orcid.org/v3.0", "ftp://x", "https://"])
def test_invalid_api_base_url_rejected(monkeypatch, value):
    monkeypatch.setenv("ORCID_API_BASE_URL", value)
    with pytest.raises(ConfigError):
        load_config()


def test_valid_api_base_url_trailing_slash_stripped(monkeypatch):
    monkeypatch.setenv("ORCID_API_BASE_URL", "https://example.org/v3.0/")
    assert load_config().api_base_url == "https://example.org/v3.0"
