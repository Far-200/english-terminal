"""Only the response fields this product displays; no headers or credentials."""

from dataclasses import dataclass
from typing import Generic, TypeVar

from ..models import TerminalError

T = TypeVar("T")


class GitHubError(TerminalError):
    """A sanitized error safe for normal CLI output."""


@dataclass(frozen=True)
class Repository:
    full_name: str
    stars: int
    language: str | None


@dataclass(frozen=True)
class Issue:
    number: int
    title: str


@dataclass(frozen=True)
class Release:
    tag: str
    title: str | None
    published_at: str
    url: str


@dataclass(frozen=True)
class Listing(Generic[T]):
    items: tuple[T, ...]
    limited: bool = False
