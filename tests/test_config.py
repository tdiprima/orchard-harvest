"""Tests for environment-driven configuration."""

import logging
import os
from unittest.mock import patch

import pytest

from orcid_harvest.config import (
    DEFAULT_AFFILIATION,
    DEFAULT_API_BASE_URL,
    DEFAULT_MAX_AUTHORS,
    DEFAULT_MAX_WORKS,
    DEFAULT_REQUEST_DELAY_SECONDS,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    MAX_AUTHORS_LIMIT,
    MAX_WORKS_LIMIT,
    ConfigError,
    configure_logging,
    load_config,
    load_dotenv,
)


@pytest.mark.parametrize("value", ["", "   ", "pub.orcid.org/v3.0", "ftp://x", "https://"])
def test_invalid_api_base_url_rejected(monkeypatch, value):
    monkeypatch.setenv("ORCID_API_BASE_URL", value)
    with pytest.raises(ConfigError):
        load_config()


def test_valid_api_base_url_trailing_slash_stripped(monkeypatch):
    monkeypatch.setenv("ORCID_API_BASE_URL", "https://example.org/v3.0/")
    assert load_config().api_base_url == "https://example.org/v3.0"


def test_defaults(monkeypatch):
    config = load_config()
    assert config.api_base_url == DEFAULT_API_BASE_URL
    assert config.affiliation == DEFAULT_AFFILIATION
    assert config.max_authors == DEFAULT_MAX_AUTHORS
    assert config.max_works == DEFAULT_MAX_WORKS
    assert config.request_timeout_seconds == DEFAULT_REQUEST_TIMEOUT_SECONDS
    assert config.request_delay_seconds == DEFAULT_REQUEST_DELAY_SECONDS
    assert config.access_token is None


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_affiliation_rejected(monkeypatch, value):
    monkeypatch.setenv("ORCID_AFFILIATION", value)
    with pytest.raises(ConfigError):
        load_config()


def test_affiliation_stripped(monkeypatch):
    monkeypatch.setenv("ORCID_AFFILIATION", "  MIT  ")
    assert load_config().affiliation == "MIT"


def test_empty_access_token_is_none(monkeypatch):
    monkeypatch.setenv("ORCID_ACCESS_TOKEN", "")
    assert load_config().access_token is None


def test_access_token_read(monkeypatch):
    monkeypatch.setenv("ORCID_ACCESS_TOKEN", "tok")
    assert load_config().access_token == "tok"


NUMERIC = [
    ("ORCID_MAX_AUTHORS", "max_authors", MAX_AUTHORS_LIMIT),
    ("ORCID_MAX_WORKS", "max_works", MAX_WORKS_LIMIT),
    ("ORCID_REQUEST_TIMEOUT", "request_timeout_seconds", 300),
]


@pytest.mark.parametrize("env_name,attr,upper", NUMERIC)
def test_numeric_bounds_accepted(monkeypatch, env_name, attr, upper):
    monkeypatch.setenv(env_name, "1")
    assert getattr(load_config(), attr) == 1
    monkeypatch.setenv(env_name, str(upper))
    assert getattr(load_config(), attr) == upper


@pytest.mark.parametrize("env_name,attr,upper", NUMERIC)
@pytest.mark.parametrize("bad", ["0", "-1", "OVER", "abc", "1.5", ""])
def test_numeric_out_of_range_rejected(monkeypatch, env_name, attr, upper, bad):
    monkeypatch.setenv(env_name, str(upper + 1) if bad == "OVER" else bad)
    with pytest.raises(ConfigError):
        load_config()


@pytest.mark.parametrize("level,expected", [("DEBUG", logging.DEBUG), ("warning", logging.WARNING)])
def test_configure_logging_accepts_levels(monkeypatch, level, expected):
    monkeypatch.setenv("LOG_LEVEL", level)
    with patch("orcid_harvest.config.logging.basicConfig") as basic:
        configure_logging()
    assert basic.call_args.kwargs["level"] == expected


def test_configure_logging_defaults_to_info():
    with patch("orcid_harvest.config.logging.basicConfig") as basic:
        configure_logging()
    assert basic.call_args.kwargs["level"] == logging.INFO


@pytest.mark.parametrize("level", ["VERBOSE", "", "Logger"])
def test_configure_logging_rejects_invalid_level(monkeypatch, level):
    monkeypatch.setenv("LOG_LEVEL", level)
    with pytest.raises(ConfigError):
        configure_logging()


def test_load_dotenv_sets_missing_vars_only(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "ORCID_AFFILIATION=\"Example University\"\n"
        "export ORCID_MAX_WORKS=7\n"
        "ORCID_MAX_AUTHORS=99\n"
        "garbage line\n"
    )
    monkeypatch.setenv("ORCID_MAX_AUTHORS", "3")
    load_dotenv(env_file)
    assert os.environ["ORCID_AFFILIATION"] == "Example University"
    assert os.environ["ORCID_MAX_WORKS"] == "7"
    assert os.environ["ORCID_MAX_AUTHORS"] == "3"


def test_load_dotenv_missing_file_is_noop(tmp_path):
    load_dotenv(tmp_path / "nope")
