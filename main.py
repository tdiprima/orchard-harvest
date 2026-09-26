"""Entry point: list authors affiliated with the configured institution and their publications."""

import logging
import sys

from orcid_harvest.client import AuthorWorks, OrcidApiError, OrcidClient
from orcid_harvest.config import ConfigError, configure_logging, load_config
from orcid_harvest.formatter import format_author_list

logger = logging.getLogger(__name__)


def harvest(client: OrcidClient) -> list[AuthorWorks]:
    """Search for authors, then fetch each author's works."""
    authors = client.search_authors_by_affiliation()
    results: list[AuthorWorks] = []
    for author in authors:
        try:
            titles = client.fetch_work_titles(author.orcid_id)
            failed = False
        except OrcidApiError:
            logger.exception("event=fetch_works_failed orcid_id=%s", author.orcid_id)
            titles = []
            failed = True
        results.append(AuthorWorks(author=author, work_titles=titles, fetch_failed=failed))
        client.throttle()
    return results


def main() -> int:
    """Load config, harvest, print the formatted result."""
    try:
        configure_logging()
        config = load_config()
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    client = OrcidClient(config)
    try:
        results = harvest(client)
    except OrcidApiError as exc:
        logger.error("event=harvest_failed error=%s", exc)
        return 1

    print(format_author_list(results))
    failed_count = sum(1 for result in results if result.fetch_failed)
    if failed_count:
        logger.error("event=harvest_incomplete failed_authors=%d", failed_count)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
