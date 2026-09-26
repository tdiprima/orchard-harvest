"""Pure formatting of harvested authors and works. No I/O here."""

from orcid_harvest.client import AuthorWorks


def format_author_list(results: list[AuthorWorks]) -> str:
    """Render authors and their works as a plain-text list.

    Format:
        Author Name (0000-0000-0000-0000)
        - Article title
        - Article title
    """
    if not results:
        return "No authors found."

    blocks: list[str] = []
    for result in results:
        lines = [f"{result.author.name} ({result.author.orcid_id})"]
        if result.fetch_failed:
            lines.append("- (works unavailable: request failed)")
        elif result.work_titles:
            lines.extend(f"- {title}" for title in result.work_titles)
        else:
            lines.append("- (no public works listed)")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
