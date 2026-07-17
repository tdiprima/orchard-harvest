"""Tests for the pure formatting layer."""

from orcid_harvest.client import Author, AuthorWorks
from orcid_harvest.formatter import format_author_list


def _author_works(name, orcid_id, titles):
    return AuthorWorks(author=Author(orcid_id=orcid_id, name=name), work_titles=titles)


def test_empty_results():
    assert format_author_list([]) == "No authors found."


def test_author_with_works():
    results = [_author_works("Ada Lovelace", "0000-0000-0000-0001", ["Note G", "Analytical Engine"])]
    output = format_author_list(results)
    assert "Ada Lovelace (0000-0000-0000-0001)" in output
    assert "- Note G" in output
    assert "- Analytical Engine" in output


def test_author_without_works_gets_placeholder():
    results = [_author_works("No Works", "0000-0000-0000-0002", [])]
    assert "- (no public works listed)" in format_author_list(results)


def test_multiple_authors_separated_by_blank_line():
    results = [
        _author_works("First", "0000-0000-0000-0003", ["A"]),
        _author_works("Second", "0000-0000-0000-0004", ["B"]),
    ]
    assert "\n\n" in format_author_list(results)
