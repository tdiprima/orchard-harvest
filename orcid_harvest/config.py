"""Configuration loaded from environment variables, with sane defaults."""

import logging
import os
from dataclasses import dataclass

DEFAULT_API_BASE_URL = "https://pub.orcid.org/v3.0"
DEFAULT_AFFILIATION = "Example University"
DEFAULT_MAX_AUTHORS = 10
DEFAULT_MAX_WORKS = 5
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_REQUEST_DELAY_SECONDS = 0.5

# ORCID caps a single search page at 1000 rows; works lists are uncapped
# but we bound them to keep output readable.
MAX_AUTHORS_LIMIT = 1000
MAX_WORKS_LIMIT = 100


class ConfigError(Exception):
    """Raised when configuration values are missing or invalid."""


@dataclass(frozen=True)
class Config:
    """Validated runtime configuration."""

    api_base_url: str
    affiliation: str
    max_authors: int
    max_works: int
    request_timeout_seconds: int
    request_delay_seconds: float
    access_token: str | None


def _read_positive_int(name: str, default: int, upper_bound: int) -> int:
    """Read an integer env var and require it to be in [1, upper_bound]."""
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw_value!r}") from exc
    if not 1 <= value <= upper_bound:
        raise ConfigError(f"{name} must be between 1 and {upper_bound}, got {value}")
    return value


def load_config() -> Config:
    """Build a Config from the environment, failing fast on bad values."""
    affiliation = os.environ.get("ORCID_AFFILIATION", DEFAULT_AFFILIATION).strip()
    if not affiliation:
        raise ConfigError("ORCID_AFFILIATION must not be empty")

    # The public API works anonymously; a token only raises rate limits.
    access_token = os.environ.get("ORCID_ACCESS_TOKEN") or None

    return Config(
        api_base_url=os.environ.get("ORCID_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/"),
        affiliation=affiliation,
        max_authors=_read_positive_int("ORCID_MAX_AUTHORS", DEFAULT_MAX_AUTHORS, MAX_AUTHORS_LIMIT),
        max_works=_read_positive_int("ORCID_MAX_WORKS", DEFAULT_MAX_WORKS, MAX_WORKS_LIMIT),
        request_timeout_seconds=_read_positive_int(
            "ORCID_REQUEST_TIMEOUT", DEFAULT_REQUEST_TIMEOUT_SECONDS, 300
        ),
        request_delay_seconds=DEFAULT_REQUEST_DELAY_SECONDS,
        access_token=access_token,
    )


def configure_logging() -> None:
    """Configure root logging; level comes from LOG_LEVEL (default INFO)."""
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        raise ConfigError(f"LOG_LEVEL must be a standard logging level, got {level_name!r}")
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
