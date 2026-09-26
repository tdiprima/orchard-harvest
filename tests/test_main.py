"""Tests for the harvest orchestration and exit status."""

import pytest

from orcid_harvest.client import Author, OrcidApiError
from orcid_harvest.config import ConfigError

import main

A1 = Author(orcid_id="0000-0000-0000-0001", name="A")
A2 = Author(orcid_id="0000-0000-0000-0002", name="B")


class _Client:
    """Scriptable fake: works maps orcid_id -> titles or an exception to raise."""

    def __init__(self, authors=(), works=None, search_error=None):
        self._authors = list(authors)
        self._works = works or {}
        self._search_error = search_error
        self.throttled = 0

    def search_authors_by_affiliation(self):
        if self._search_error:
            raise self._search_error
        return self._authors

    def fetch_work_titles(self, orcid_id):
        result = self._works.get(orcid_id, [])
        if isinstance(result, Exception):
            raise result
        return result

    def throttle(self):
        self.throttled += 1


def _install(monkeypatch, client):
    monkeypatch.setattr(main, "OrcidClient", lambda config: client)


def test_failed_works_request_is_flagged_and_nonzero(monkeypatch, capsys):
    client = _Client([A1], {A1.orcid_id: OrcidApiError("HTTP 503")})
    results = main.harvest(client)
    assert results[0].fetch_failed is True

    _install(monkeypatch, client)
    assert main.main() == 1
    out = capsys.readouterr().out
    assert "works unavailable" in out
    assert "no public works listed" not in out


def test_harvest_continues_after_failed_author(monkeypatch, capsys):
    client = _Client(
        [A1, A2],
        {A1.orcid_id: OrcidApiError("HTTP 503"), A2.orcid_id: ["Paper One"]},
    )
    results = main.harvest(client)
    assert [r.fetch_failed for r in results] == [True, False]
    assert results[1].work_titles == ["Paper One"]
    assert client.throttled == 2

    _install(monkeypatch, client)
    assert main.main() == 1
    out = capsys.readouterr().out
    assert "A (0000-0000-0000-0001)" in out
    assert "works unavailable" in out
    assert "B (0000-0000-0000-0002)" in out
    assert "- Paper One" in out


def test_success_exits_zero(monkeypatch, capsys):
    _install(monkeypatch, _Client([A1, A2], {A1.orcid_id: ["X"], A2.orcid_id: ["Y", "Z"]}))
    assert main.main() == 0
    out = capsys.readouterr().out
    assert "- X" in out and "- Y" in out and "- Z" in out


def test_empty_results_exit_zero(monkeypatch, capsys):
    _install(monkeypatch, _Client())
    assert main.main() == 0
    assert "No authors found." in capsys.readouterr().out


def test_search_failure_exits_one(monkeypatch, capsys):
    _install(monkeypatch, _Client(search_error=OrcidApiError("HTTP 500")))
    assert main.main() == 1
    assert capsys.readouterr().out == ""


def test_invalid_config_exits_two(monkeypatch, capsys):
    monkeypatch.setenv("ORCID_MAX_WORKS", "0")
    calls = []
    monkeypatch.setattr(main, "OrcidClient", lambda config: calls.append(config))
    assert main.main() == 2
    err = capsys.readouterr().err
    assert err.startswith("ERROR:")
    assert "ORCID_MAX_WORKS" in err
    assert calls == []


def test_invalid_log_level_exits_two(monkeypatch, capsys):
    monkeypatch.setenv("LOG_LEVEL", "LOUD")
    assert main.main() == 2
    assert "LOG_LEVEL" in capsys.readouterr().err


def test_config_error_from_load_config_is_reported(monkeypatch, capsys):
    monkeypatch.setattr(main, "load_config", lambda: (_ for _ in ()).throw(ConfigError("boom")))
    assert main.main() == 2
    assert "ERROR: boom" in capsys.readouterr().err
