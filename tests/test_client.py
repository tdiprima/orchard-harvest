"""Tests for parsing and validation logic in the ORCID client."""

import pytest

from orcid_harvest.client import OrcidApiError, OrcidClient
from orcid_harvest.config import Config

CONFIG = Config(
    api_base_url="https://pub.orcid.org/v3.0",
    affiliation="Example University",
    max_authors=5,
    max_works=3,
    request_timeout_seconds=30,
    request_delay_seconds=0.0,
    access_token=None,
)


def test_parse_author_prefers_credit_name():
    entry = {
        "orcid-id": "0000-0000-0000-0001",
        "given-names": "Jane",
        "family-names": "Doe",
        "credit-name": "J. Q. Doe",
    }
    author = OrcidClient._parse_author(entry)
    assert author.name == "J. Q. Doe"


def test_parse_author_falls_back_to_given_family():
    entry = {"orcid-id": "0000-0000-0000-0002", "given-names": "Jane", "family-names": "Doe"}
    assert OrcidClient._parse_author(entry).name == "Jane Doe"


def test_parse_author_handles_missing_name():
    entry = {"orcid-id": "0000-0000-0000-0003"}
    assert OrcidClient._parse_author(entry).name == "(name not public)"


def test_extract_title_reads_nested_value():
    group = {"work-summary": [{"title": {"title": {"value": "  Deep Learning  "}}}]}
    assert OrcidClient._extract_title(group) == "Deep Learning"


def test_extract_title_missing_returns_none():
    assert OrcidClient._extract_title({"work-summary": []}) is None


def test_fetch_work_titles_rejects_bad_orcid_id():
    client = OrcidClient(CONFIG)
    with pytest.raises(OrcidApiError):
        client.fetch_work_titles("not-an-orcid")
