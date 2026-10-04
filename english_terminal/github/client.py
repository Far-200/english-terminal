"""Bounded GET-only client for api.github.com, using the standard library."""

import json
import os
from contextlib import suppress
from datetime import datetime
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .. import __version__
from .identifiers import repository, username
from .models import GitHubError, Issue, Listing, Release, Repository

API_VERSION = "2026-03-10"
LIMIT = 30
MAX_ISSUE_PAGES = 3
MAX_BYTES = 2 * 1024 * 1024
TIMEOUT = 10
_MISSING = object()


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open(request: Request, *, timeout: int):
    return build_opener(_NoRedirects()).open(request, timeout=timeout)


def redact_token(text: str) -> str:
    secret = os.environ.get("GITHUB_TOKEN", "")
    return text.replace(secret, "[redacted]") if secret else text


def _invalid() -> GitHubError:
    return GitHubError("GitHub returned a malformed API response. Try again later.")


def _string(data: dict, key: str, *, optional: bool = False) -> str | None:
    value = data.get(key)
    if optional and value is None:
        return None
    if not isinstance(value, str) or (not optional and not value):
        raise _invalid()
    return redact_token(value)


def _integer(data: dict, key: str) -> int:
    value = data.get(key)
    if type(value) is not int or value < 0:
        raise _invalid()
    return value


class GitHubClient:
    """No stored credentials, cache, generic public request method, or write methods."""

    def _get(
        self,
        endpoint: str,
        *,
        missing: str,
        query: dict | None = None,
        authenticated: bool = False,
        allow_missing: bool = False,
    ):
        token = os.environ.get("GITHUB_TOKEN", "")
        if authenticated and not token:
            raise GitHubError(
                "This command requires GitHub authentication.\n\n"
                "Set the GITHUB_TOKEN environment variable and try again."
            )
        if token and (
            not token.isascii() or any(c.isspace() or ord(c) < 33 or ord(c) == 127 for c in token)
        ):
            raise GitHubError("GITHUB_TOKEN has an invalid format. Check the environment variable.")
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": f"English-Terminal/{__version__}",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        url = "https://api.github.com" + endpoint
        if query:
            url += "?" + urlencode(query)
        try:
            request = Request(url, headers=headers, method="GET")
            with _open(request, timeout=TIMEOUT) as response:
                if response.status != 200:
                    raise GitHubError("GitHub returned an unexpected HTTP response.")
                body = response.read(MAX_BYTES + 1)
                more = 'rel="next"' in response.headers.get("Link", "")
        except HTTPError as error:
            # Never surface server bodies, exception text, request headers, or URLs.
            status = error.code
            rate_limited = (
                status == 429
                or error.headers.get("X-RateLimit-Remaining") == "0"
                or error.headers.get("Retry-After") is not None
            )
            if status == 403 and not rate_limited:
                with suppress(OSError, HTTPException):
                    rate_limited = b"rate limit" in error.read(8192).lower()
            error.close()
            if status in (403, 429) and rate_limited:
                raise GitHubError(
                    "GitHub API rate limit reached. Try again later or set GITHUB_TOKEN."
                ) from None
            if status == 401:
                raise GitHubError("GitHub authentication failed. Check GITHUB_TOKEN.") from None
            if status == 403:
                raise GitHubError(
                    "GitHub denied access. Check repository access and token permissions."
                ) from None
            if status == 404:
                if allow_missing:
                    return _MISSING, False
                raise GitHubError(redact_token(missing)) from None
            if 300 <= status < 400:
                raise GitHubError(
                    "GitHub redirected this request. Check the current owner/repository name."
                ) from None
            raise GitHubError(
                f"GitHub returned an unexpected HTTP response ({status}). Try again later."
            ) from None
        except (URLError, OSError, HTTPException, ValueError):
            raise GitHubError("Could not reach GitHub. Check your internet connection.") from None
        if len(body) > MAX_BYTES:
            raise GitHubError("GitHub returned a response larger than the 2 MiB safety limit.")
        try:
            data = json.loads(body)
        except (ValueError, UnicodeError, RecursionError):
            raise _invalid() from None
        return data, more

    def _repositories(self, endpoint: str, *, missing: str, authenticated: bool = False):
        data, more = self._get(
            endpoint,
            missing=missing,
            authenticated=authenticated,
            query={"per_page": LIMIT, "page": 1, "sort": "full_name", "direction": "asc"},
        )
        if not isinstance(data, list) or len(data) > LIMIT:
            raise _invalid()
        items = []
        for row in data:
            if not isinstance(row, dict):
                raise _invalid()
            items.append(
                Repository(
                    _string(row, "full_name"),
                    _integer(row, "stargazers_count"),
                    _string(row, "language", optional=True),
                )
            )
        return Listing(tuple(items), more)

    def list_user_repositories(self, user: str) -> Listing[Repository]:
        username(user)
        return self._repositories(
            f"/users/{user}/repos", missing=f'GitHub user "{user}" was not found.'
        )

    def list_authenticated_repositories(self) -> Listing[Repository]:
        return self._repositories(
            "/user/repos", missing="GitHub account repositories were not found.", authenticated=True
        )

    def list_repository_issues(self, owner: str, repo: str) -> Listing[Issue]:
        repository(f"{owner}/{repo}")
        items = []
        seen = set()
        for page in range(1, MAX_ISSUE_PAGES + 1):
            data, more = self._get(
                f"/repos/{owner}/{repo}/issues",
                missing=f'Repository "{owner}/{repo}" was not found or is not accessible.',
                query={
                    "state": "open",
                    "per_page": LIMIT,
                    "page": page,
                    "sort": "created",
                    "direction": "desc",
                },
            )
            if not isinstance(data, list) or len(data) > LIMIT:
                raise _invalid()
            for row in data:
                if not isinstance(row, dict):
                    raise _invalid()
                if "pull_request" in row:
                    continue
                if row.get("state") not in ("open", "closed"):
                    raise _invalid()
                if row["state"] != "open":
                    continue
                number = _integer(row, "number")
                title = _string(row, "title")
                if number not in seen:
                    seen.add(number)
                    items.append(Issue(number, title))
            if len(items) >= LIMIT or not more:
                return Listing(tuple(items[:LIMIT]), more or len(items) > LIMIT)
        return Listing(tuple(items[:LIMIT]), True)

    def get_latest_release(self, owner: str, repo: str) -> Release | None:
        repository(f"{owner}/{repo}")
        missing = f'Repository "{owner}/{repo}" was not found or is not accessible.'
        data, _ = self._get(
            f"/repos/{owner}/{repo}/releases/latest", missing=missing, allow_missing=True
        )
        if data is _MISSING:
            # A release 404 alone cannot distinguish a missing repo from no releases.
            metadata, _ = self._get(f"/repos/{owner}/{repo}", missing=missing)
            if not isinstance(metadata, dict):
                raise _invalid()
            _string(metadata, "full_name")
            return None
        if not isinstance(data, dict):
            raise _invalid()
        date = _string(data, "published_at")
        url = _string(data, "html_url")
        try:
            datetime.fromisoformat(date.replace("Z", "+00:00"))
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.netloc != "github.com":
                raise ValueError
        except ValueError:
            raise _invalid() from None
        return Release(_string(data, "tag_name"), _string(data, "name", optional=True), date, url)
