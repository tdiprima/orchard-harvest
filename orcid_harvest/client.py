"""Read-only client for the ORCID public API (pub.orcid.org)."""

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from orcid_harvest.config import Config

logger = logging.getLogger(__name__)

ORCID_ID_PATTERN = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


class OrcidApiError(Exception):
    """Raised when the ORCID API returns an error or unusable response."""


def _shape_error(field_name: str, expected: str, value: object, url: str) -> OrcidApiError:
    return OrcidApiError(
        f"Unexpected ORCID API response shape for {url}: "
        f"{field_name} should be {expected}, got {type(value).__name__}"
    )


def _expect_list(value: object, field_name: str, url: str) -> list:
    """Return value as a list; None/absent means empty, anything else must be a list."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise _shape_error(field_name, "a list", value, url)
    return value


def _expect_dict(value: object, field_name: str, url: str) -> dict:
    """Return value as a dict; None/absent means empty, anything else must be a dict."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise _shape_error(field_name, "an object", value, url)
    return value


def _expect_str(value: object, field_name: str, url: str) -> str | None:
    """Return value as a str or None; anything else is a shape violation."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise _shape_error(field_name, "a string", value, url)
    return value


@dataclass(frozen=True)
class Author:
    """One researcher found by the affiliation search."""

    orcid_id: str
    name: str


@dataclass(frozen=True)
class AuthorWorks:
    """An author together with their publication titles."""

    author: Author
    work_titles: list[str] = field(default_factory=list)
    fetch_failed: bool = False


class OrcidClient:
    """Fetches authors and works from the ORCID public API."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def search_authors_by_affiliation(self) -> list[Author]:
        """Search ORCID for researchers affiliated with the configured institution."""
        query = f'affiliation-org-name:"{self._config.affiliation}"'
        params = urllib.parse.urlencode({"q": query, "rows": self._config.max_authors})
        url = f"{self._config.api_base_url}/expanded-search/?{params}"

        payload = self._get_json(url)
        results = _expect_list(payload.get("expanded-result"), "expanded-result", url)
        total_found = payload.get("num-found", 0)
        if not isinstance(total_found, int):
            total_found = 0
        logger.info(
            "event=author_search affiliation=%r returned=%d total_available=%d",
            self._config.affiliation,
            len(results),
            total_found,
        )
        return [self._parse_author(_expect_dict(entry, "expanded-result[]", url)) for entry in results]

    def fetch_work_titles(self, orcid_id: str) -> list[str]:
        """Fetch up to max_works publication titles for one ORCID iD."""
        if not ORCID_ID_PATTERN.match(orcid_id):
            raise OrcidApiError(f"Invalid ORCID iD format: {orcid_id!r}")

        url = f"{self._config.api_base_url}/{orcid_id}/works"
        payload = self._get_json(url)

        titles: list[str] = []
        for group in _expect_list(payload.get("group"), "group", url):
            title = self._extract_title(_expect_dict(group, "group[]", url), url)
            if title:
                titles.append(title)
            if len(titles) >= self._config.max_works:
                break
        return titles

    @staticmethod
    def _parse_author(entry: dict) -> Author:
        """Build an Author from one expanded-search result entry."""
        orcid_id = _expect_str(entry.get("orcid-id"), "orcid-id", "expanded-search") or ""
        given = _expect_str(entry.get("given-names"), "given-names", "expanded-search") or ""
        family = _expect_str(entry.get("family-names"), "family-names", "expanded-search") or ""
        credit = _expect_str(entry.get("credit-name"), "credit-name", "expanded-search") or ""
        name = credit or f"{given} {family}".strip() or "(name not public)"
        return Author(orcid_id=orcid_id, name=name)

    @staticmethod
    def _extract_title(group: dict, url: str = "works") -> str | None:
        """Pull the preferred title out of one works group, if present.

        Missing fields are a legitimate fallback (None); wrong types are an
        API contract violation and raise OrcidApiError.
        """
        summaries = _expect_list(group.get("work-summary"), "work-summary", url)
        if not summaries:
            return None
        summary = _expect_dict(summaries[0], "work-summary[0]", url)
        title_block = _expect_dict(summary.get("title"), "title", url)
        inner = _expect_dict(title_block.get("title"), "title.title", url)
        title = _expect_str(inner.get("value"), "title.title.value", url)
        return title.strip() or None if title else None

    def _get_json(self, url: str) -> dict:
        """GET a URL and decode the JSON body, with basic error handling."""
        headers = {"Accept": "application/json", "User-Agent": "orchard-harvest/0.1"}
        if self._config.access_token:
            headers["Authorization"] = f"Bearer {self._config.access_token}"

        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(
                request, timeout=self._config.request_timeout_seconds
            ) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            raise OrcidApiError(f"ORCID API returned HTTP {exc.code} for {url}") from exc
        except urllib.error.URLError as exc:
            raise OrcidApiError(f"Could not reach ORCID API at {url}: {exc.reason}") from exc
        except (TimeoutError, OSError, ValueError) as exc:
            raise OrcidApiError(f"Failed reading ORCID API response from {url}: {exc}") from exc

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise OrcidApiError(f"ORCID API returned non-JSON body for {url}") from exc
        if not isinstance(payload, dict):
            raise OrcidApiError(f"Unexpected ORCID API response shape for {url}")
        return payload

    def throttle(self) -> None:
        """Sleep briefly between requests to stay under public rate limits."""
        time.sleep(self._config.request_delay_seconds)
