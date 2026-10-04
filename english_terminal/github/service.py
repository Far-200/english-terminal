"""Typed command dispatch; HTTP details stay inside the client."""

from ..models import Action, Command, Result
from . import formatter
from .client import GitHubClient, redact_token
from .identifiers import repository


def _result(text: str, *, api_hints: tuple[str, ...]) -> Result:
    # Also cover a credential accidentally supplied as a syntactically valid identifier.
    return Result(redact_token(text), api_hints=tuple(redact_token(h) for h in api_hints))


def execute(command: Command) -> Result:
    client = GitHubClient()
    if command.action == Action.GITHUB_REPOS:
        user = command.args[0]
        return _result(
            formatter.repositories(client.list_user_repositories(user)),
            api_hints=(f"GET /users/{user}/repos",),
        )
    if command.action == Action.GITHUB_MY_REPOS:
        return _result(
            formatter.repositories(client.list_authenticated_repositories()),
            api_hints=("GET /user/repos",),
        )
    owner, repo = repository(command.args[0])
    endpoint = f"/repos/{owner}/{repo}"
    if command.action == Action.GITHUB_ISSUES:
        return _result(
            formatter.issues(client.list_repository_issues(owner, repo)),
            api_hints=(f"GET {endpoint}/issues",),
        )
    release = client.get_latest_release(owner, repo)
    hints = (f"GET {endpoint}/releases/latest",)
    if release is None:
        hints += (f"GET {endpoint}",)
    return _result(formatter.release(release), api_hints=hints)
