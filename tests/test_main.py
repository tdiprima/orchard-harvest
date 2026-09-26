"""Tests for the harvest orchestration and exit status."""

from orcid_harvest.client import Author, OrcidApiError

import main


class _Client:
    def search_authors_by_affiliation(self):
        return [Author(orcid_id="0000-0000-0000-0001", name="A")]

    def fetch_work_titles(self, orcid_id):
        raise OrcidApiError("HTTP 503")

    def throttle(self):
        pass


def test_failed_works_request_is_flagged_and_nonzero(monkeypatch, capsys):
    results = main.harvest(_Client())
    assert results[0].fetch_failed is True

    monkeypatch.setattr(main, "OrcidClient", lambda config: _Client())
    assert main.main() == 1
    out = capsys.readouterr().out
    assert "works unavailable" in out
    assert "no public works listed" not in out
