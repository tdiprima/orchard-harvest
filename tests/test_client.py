"""Tests for parsing and validation logic in the ORCID client."""

import dataclasses
import urllib.parse

import pytest

from orcid_harvest.client import Author, OrcidApiError, OrcidClient
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


def test_get_json_wraps_read_timeout(monkeypatch):
    import urllib.request

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Response())
    with pytest.raises(OrcidApiError):
        OrcidClient(CONFIG)._get_json("https://pub.orcid.org/v3.0/x")


def _client_with_payload(monkeypatch, payload):
    client = OrcidClient(CONFIG)
    monkeypatch.setattr(client, "_get_json", lambda url: payload)
    return client


@pytest.mark.parametrize(
    "payload",
    [
        {"group": "not-a-list"},
        {"group": ["not-a-dict"]},
        {"group": [{"work-summary": {"title": {}}}]},
        {"group": [{"work-summary": ["not-a-dict"]}]},
        {"group": [{"work-summary": [{"title": "flat"}]}]},
        {"group": [{"work-summary": [{"title": {"title": ["x"]}}]}]},
        {"group": [{"work-summary": [{"title": {"title": {"value": 42}}}]}]},
    ],
)
def test_fetch_work_titles_rejects_malformed_shapes(monkeypatch, payload):
    client = _client_with_payload(monkeypatch, payload)
    with pytest.raises(OrcidApiError):
        client.fetch_work_titles("0000-0000-0000-0001")


def test_fetch_work_titles_tolerates_missing_fields(monkeypatch):
    payload = {
        "group": [
            {},
            {"work-summary": []},
            {"work-summary": [{}]},
            {"work-summary": [{"title": None}]},
            {"work-summary": [{"title": {"title": {"value": "  "}}}]},
            {"work-summary": [{"title": {"title": {"value": "Real"}}}]},
        ]
    }
    client = _client_with_payload(monkeypatch, payload)
    assert client.fetch_work_titles("0000-0000-0000-0001") == ["Real"]


@pytest.mark.parametrize(
    "payload",
    [
        {"expanded-result": {}},
        {"expanded-result": ["x"]},
        {"expanded-result": [{"orcid-id": 123}]},
        {"expanded-result": [{"orcid-id": "0000-0000-0000-0001", "credit-name": ["a"]}]},
    ],
)
def test_search_rejects_malformed_shapes(monkeypatch, payload):
    client = _client_with_payload(monkeypatch, payload)
    with pytest.raises(OrcidApiError):
        client.search_authors_by_affiliation()


def test_search_tolerates_missing_results(monkeypatch):
    client = _client_with_payload(monkeypatch, {"num-found": 0})
    assert client.search_authors_by_affiliation() == []


# --- HTTP layer -----------------------------------------------------------


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body


def _capture_urlopen(monkeypatch, body=b"{}", error=None):
    import urllib.request

    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append((request, timeout))
        if error is not None:
            raise error
        return _FakeResponse(body)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


def test_get_json_sends_headers_and_timeout(monkeypatch):
    calls = _capture_urlopen(monkeypatch, body=b'{"ok": true}')
    config = dataclasses.replace(CONFIG, request_timeout_seconds=7)
    payload = OrcidClient(config)._get_json("https://pub.orcid.org/v3.0/x")

    assert payload == {"ok": True}
    request, timeout = calls[0]
    assert request.full_url == "https://pub.orcid.org/v3.0/x"
    assert timeout == 7
    assert request.get_header("Accept") == "application/json"
    assert request.get_header("User-agent") == "orchard-harvest/0.1"
    assert request.get_header("Authorization") is None


def test_get_json_sends_bearer_token_when_configured(monkeypatch):
    calls = _capture_urlopen(monkeypatch)
    config = dataclasses.replace(CONFIG, access_token="secret")
    OrcidClient(config)._get_json("https://pub.orcid.org/v3.0/x")
    assert calls[0][0].get_header("Authorization") == "Bearer secret"


def test_get_json_http_error(monkeypatch):
    import urllib.error

    err = urllib.error.HTTPError("https://x", 503, "Unavailable", {}, None)
    _capture_urlopen(monkeypatch, error=err)
    with pytest.raises(OrcidApiError, match="HTTP 503"):
        OrcidClient(CONFIG)._get_json("https://pub.orcid.org/v3.0/x")


def test_get_json_network_error(monkeypatch):
    import urllib.error

    _capture_urlopen(monkeypatch, error=urllib.error.URLError("dns failed"))
    with pytest.raises(OrcidApiError, match="Could not reach"):
        OrcidClient(CONFIG)._get_json("https://pub.orcid.org/v3.0/x")


def test_get_json_os_error(monkeypatch):
    _capture_urlopen(monkeypatch, error=ConnectionResetError("reset"))
    with pytest.raises(OrcidApiError, match="Failed reading"):
        OrcidClient(CONFIG)._get_json("https://pub.orcid.org/v3.0/x")


def test_get_json_malformed_json(monkeypatch):
    _capture_urlopen(monkeypatch, body=b"<html>oops</html>")
    with pytest.raises(OrcidApiError, match="non-JSON"):
        OrcidClient(CONFIG)._get_json("https://pub.orcid.org/v3.0/x")


@pytest.mark.parametrize("body", [b"[]", b'"str"', b"42", b"null"])
def test_get_json_non_object_rejected(monkeypatch, body):
    _capture_urlopen(monkeypatch, body=body)
    with pytest.raises(OrcidApiError, match="response shape"):
        OrcidClient(CONFIG)._get_json("https://pub.orcid.org/v3.0/x")


# --- Search and works ------------------------------------------------------


def test_search_builds_query_and_parses_authors(monkeypatch):
    seen = []

    def fake_get_json(url):
        seen.append(url)
        return {
            "num-found": 2,
            "expanded-result": [
                {"orcid-id": "0000-0000-0000-0001", "given-names": "Ada", "family-names": "Lovelace"},
                {"orcid-id": "0000-0000-0000-0002", "credit-name": "C. Babbage"},
            ],
        }

    client = OrcidClient(CONFIG)
    monkeypatch.setattr(client, "_get_json", fake_get_json)
    authors = client.search_authors_by_affiliation()

    assert authors == [
        Author(orcid_id="0000-0000-0000-0001", name="Ada Lovelace"),
        Author(orcid_id="0000-0000-0000-0002", name="C. Babbage"),
    ]
    url = seen[0]
    assert url.startswith("https://pub.orcid.org/v3.0/expanded-search/?")
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    assert query["q"] == ['affiliation-org-name:"Example University"']
    assert query["rows"] == ["5"]


def test_search_tolerates_non_int_num_found(monkeypatch):
    client = _client_with_payload(monkeypatch, {"num-found": "many", "expanded-result": []})
    assert client.search_authors_by_affiliation() == []


def test_fetch_work_titles_requests_correct_url(monkeypatch):
    seen = []
    client = OrcidClient(CONFIG)
    monkeypatch.setattr(client, "_get_json", lambda url: seen.append(url) or {"group": []})
    assert client.fetch_work_titles("0000-0000-0000-0001") == []
    assert seen == ["https://pub.orcid.org/v3.0/0000-0000-0000-0001/works"]


def test_fetch_work_titles_bounded_by_max_works(monkeypatch):
    def group(title):
        return {"work-summary": [{"title": {"title": {"value": title}}}]}

    payload = {
        "group": [
            group("T1"),
            {"work-summary": []},
            group("T2"),
            {},
            group("T3"),
            group("T4"),
            group("T5"),
        ]
    }
    client = _client_with_payload(monkeypatch, payload)
    assert client.fetch_work_titles("0000-0000-0000-0001") == ["T1", "T2", "T3"]


def test_throttle_sleeps_for_configured_delay(monkeypatch):
    slept = []
    monkeypatch.setattr("orcid_harvest.client.time.sleep", slept.append)
    OrcidClient(dataclasses.replace(CONFIG, request_delay_seconds=0.25)).throttle()
    assert slept == [0.25]
