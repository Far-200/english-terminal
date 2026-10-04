"""Pure validation shared by the parser and public client methods."""

import re

from ..models import Action, ParseError

GITHUB_ACTIONS = frozenset(
    {Action.GITHUB_REPOS, Action.GITHUB_ISSUES, Action.GITHUB_RELEASE, Action.GITHUB_MY_REPOS}
)


def username(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", value):
        raise ParseError("Use a GitHub username, not a URL or path.")
    return value


def repository(value: str) -> tuple[str, str]:
    parts = value.split("/")
    if len(parts) != 2 or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", parts[-1]):
        raise ParseError("Use a repository identifier in owner/repository form.")
    username(parts[0])
    if parts[1] in (".", ".."):
        raise ParseError("Use a repository identifier in owner/repository form.")
    return parts[0], parts[1]


def validate(action: Action, args: tuple[str, ...]) -> None:
    if action == Action.GITHUB_REPOS:
        username(args[0])
    elif action in (Action.GITHUB_ISSUES, Action.GITHUB_RELEASE):
        repository(args[0])
