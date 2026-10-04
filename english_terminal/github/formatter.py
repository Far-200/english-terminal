"""Compact output for validated GitHub models."""

from ..formatting import safe_text
from .models import Issue, Listing, Release, Repository


def _line(text: str) -> str:
    return safe_text(text).replace("\n", " ").replace("\t", " ")


def repositories(result: Listing[Repository]) -> str:
    lines = ["Repository  |  Stars  |  Language"] if result.items else ["No repositories found."]
    lines.extend(
        f"{_line(r.full_name)}  |  {r.stars}  |  {_line(r.language or '—')}" for r in result.items
    )
    if result.limited:
        lines.append("Showing the first 30 repositories; more are available on GitHub.")
    return "\n".join(lines)


def issues(result: Listing[Issue]) -> str:
    lines = [f"#{i.number}  {_line(i.title)}" for i in result.items]
    if not lines:
        lines = ["No open issues found" + (" in the scanned pages." if result.limited else ".")]
    if result.limited:
        lines.append("Limited to 30 issues / 3 API pages; more may be available on GitHub.")
    return "\n".join(lines)


def release(result: Release | None) -> str:
    if result is None:
        return "No published releases found for this repository (drafts and prereleases excluded)."
    lines = [_line(result.tag)]
    if result.title:
        lines.append(_line(result.title))
    lines.extend((f"Released: {_line(result.published_at[:10])}", _line(result.url)))
    return "\n".join(lines)
