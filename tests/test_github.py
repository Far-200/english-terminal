"""Offline contract tests. Every HTTP call is intercepted; credentials are synthetic."""

import contextlib
import io
import json
import os
import tempfile
import traceback
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

from english_terminal.cli import arguments, run_line
from english_terminal.executor import Session
from english_terminal.github import formatter
from english_terminal.github.client import API_VERSION, MAX_BYTES, GitHubClient, _NoRedirects
from english_terminal.github.models import GitHubError, Issue, Listing, Release, Repository
from english_terminal.models import Action, ParseError, TerminalError
from english_terminal.parser import parse, suggestions
from english_terminal.registry import help_text


def repo(name="octocat/hello-world", stars=42, language="Python"):
    return {"full_name": name, "stargazers_count": stars, "language": language}


def issue(number=42, title="Improve parser errors", **extra):
    return {"number": number, "title": title, "state": "open", **extra}


def release():
    return {
        "tag_name": "v1.4.0",
        "name": "A small release",
        "published_at": "2026-09-18T12:00:00Z",
        "html_url": "https://github.com/owner/repo/releases/tag/v1.4.0",
    }


class Response(io.BytesIO):
    def __init__(self, data=None, *, raw=None, headers=None, status=200):
        super().__init__(json.dumps(data).encode() if raw is None else raw)
        self.headers = headers or {}
        self.status = status


def http_error(status, headers=None, body=b"untrusted server message"):
    return HTTPError(
        "https://api.github.com/test", status, "untrusted reason", headers or {}, io.BytesIO(body)
    )


class OfflineCase:
    def setUp(self):
        # Never read or transmit the developer's real environment credential.
        self.environment = patch.dict(os.environ, {"GITHUB_TOKEN": ""})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.boundary = patch("english_terminal.github.client._open")
        self.open = self.boundary.start()
        self.addCleanup(self.boundary.stop)
        self.open.side_effect = AssertionError("Unexpected HTTP call in offline test")
        self.client = GitHubClient()

    def respond(self, *responses):
        self.open.side_effect = list(responses)


class GitHubParserTests(OfflineCase, unittest.TestCase):
    def test_all_four_commands(self):
        cases = {
            "show github repos for octocat": (Action.GITHUB_REPOS, ("octocat",)),
            "show github issues in Far-200/think-before-code": (
                Action.GITHUB_ISSUES,
                ("Far-200/think-before-code",),
            ),
            "show latest github release of Owner/Repo": (Action.GITHUB_RELEASE, ("Owner/Repo",)),
            "show my github repos": (Action.GITHUB_MY_REPOS, ()),
        }
        for text, (action, args) in cases.items():
            with self.subTest(text=text):
                command = parse(text)
                self.assertEqual((command.action, command.args), (action, args))
        self.open.assert_not_called()

    def test_case_and_quotes(self):
        command = parse(' SHOW latest GITHUB release of "Owner/My.Repo" ')
        self.assertEqual(command.args, ("Owner/My.Repo",))

    def test_malformed_repositories(self):
        for identifier in (
            "repo",
            "owner/",
            "/repo",
            "a/b/c",
            "https://github.com/a/b",
            "owner/..",
            "owner/.",
            "owner/a?x=1",
            "owner/a#frag",
            "owner/a%2fb",
            "-owner/repo",
            r"owner\repo",
            "owner/my repo",
        ):
            with self.subTest(identifier=identifier), self.assertRaises(ParseError):
                parse(f'show github issues in "{identifier}"')
        self.open.assert_not_called()

    def test_malformed_users(self):
        for user in ("@octocat", "user/repo", "foo?bar", "foo#bar", "-foo", "foo-", "a" * 40):
            with self.subTest(user=user), self.assertRaises(ParseError):
                parse(f"show github repos for {user}")

    def test_unsupported_input(self):
        for text in (
            "github do something",
            "fix my github repo",
            "github whatever",
            "delete github issue 4",
            "show github repos",
            "show my github repos now",
        ):
            with self.subTest(text=text), self.assertRaises(ParseError):
                parse(text)
        self.open.assert_not_called()

    def test_suggestions_and_contextual_help(self):
        self.assertIn("show github repos for <username>", suggestions("shwo github repos for"))
        self.assertIn("show files", suggestions("shwo files"))
        self.assertIn("GitHub", help_text())
        self.assertIn("requires GITHUB_TOKEN", help_text("show my github"))


class GitHubClientTests(OfflineCase, unittest.TestCase):
    def test_public_repositories(self):
        self.respond(Response([repo(), repo("owner/other", language=None)]))
        result = self.client.list_user_repositories("octocat")
        self.assertEqual(result.items[0], Repository("octocat/hello-world", 42, "Python"))
        self.assertIsNone(result.items[1].language)
        self.assertFalse(result.limited)

    def test_request_headers_and_get_only(self):
        self.respond(Response([]))
        self.client.list_user_repositories("octocat")
        request = self.open.call_args.args[0]
        headers = {k.lower(): v for k, v in request.header_items()}
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)
        self.assertEqual(urlsplit(request.full_url).netloc, "api.github.com")
        self.assertEqual(headers["accept"], "application/vnd.github+json")
        self.assertEqual(headers["x-github-api-version"], API_VERSION)
        self.assertIn("English-Terminal/0.2.0", headers["user-agent"])
        self.assertNotIn("authorization", headers)
        self.assertEqual(self.open.call_args.kwargs["timeout"], 10)

    def test_repository_page_is_bounded(self):
        self.respond(Response([repo()], headers={"Link": '<https://evil.invalid>; rel="next"'}))
        result = self.client.list_user_repositories("octocat")
        self.assertTrue(result.limited)
        self.assertEqual(self.open.call_count, 1)
        query = parse_qs(urlsplit(self.open.call_args.args[0].full_url).query)
        self.assertEqual(query["per_page"], ["30"])
        self.assertEqual(query["page"], ["1"])

    def test_empty_repositories(self):
        self.respond(Response([]))
        self.assertEqual(self.client.list_user_repositories("octocat").items, ())

    def test_authenticated_repositories(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "synthetic-test-credential"}):
            self.respond(Response([repo("me/private")]))
            result = self.client.list_authenticated_repositories()
            request = self.open.call_args.args[0]
            self.assertEqual(urlsplit(request.full_url).path, "/user/repos")
            self.assertEqual(
                request.get_header("Authorization"), "Bearer synthetic-test-credential"
            )
            self.assertEqual(result.items[0].full_name, "me/private")
            self.assertNotIn("synthetic-test-credential", repr(self.client))

    def test_optional_auth_for_public_request(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "synthetic-test-credential"}):
            self.respond(Response([]))
            self.client.list_user_repositories("octocat")
            self.assertTrue(self.open.call_args.args[0].has_header("Authorization"))

    def test_missing_auth(self):
        with self.assertRaisesRegex(GitHubError, "requires GitHub authentication"):
            self.client.list_authenticated_repositories()
        self.open.assert_not_called()

    def test_invalid_token_is_not_echoed(self):
        for secret in (
            "synthetic\r\ncredential",
            "synthetic é credential",
            " synthetic-credential",
        ):
            with patch.dict(os.environ, {"GITHUB_TOKEN": secret}), self.subTest():
                with self.assertRaises(GitHubError) as caught:
                    self.client.list_authenticated_repositories()
                self.assertNotIn(secret, repr(caught.exception))
        self.open.assert_not_called()

    def test_issues_exclude_pull_requests_and_closed(self):
        self.respond(Response([issue(), issue(43, pull_request={}), issue(44, state="closed")]))
        result = self.client.list_repository_issues("owner", "repo")
        self.assertEqual(result.items, (Issue(42, "Improve parser errors"),))
        self.assertEqual(
            parse_qs(urlsplit(self.open.call_args.args[0].full_url).query)["state"], ["open"]
        )

    def test_issue_pagination_builds_own_urls(self):
        self.respond(
            Response(
                [issue(1, pull_request={})], headers={"Link": '<https://evil.invalid>; rel="next"'}
            ),
            Response([issue(2)]),
        )
        result = self.client.list_repository_issues("owner", "repo")
        self.assertEqual([i.number for i in result.items], [2])
        self.assertEqual(self.open.call_count, 2)
        for call in self.open.call_args_list:
            self.assertEqual(urlsplit(call.args[0].full_url).netloc, "api.github.com")

    def test_issue_page_cap(self):
        self.respond(
            *(
                Response([issue(p, pull_request={})], headers={"Link": 'ignored; rel="next"'})
                for p in range(3)
            )
        )
        result = self.client.list_repository_issues("owner", "repo")
        self.assertEqual(self.open.call_count, 3)
        self.assertTrue(result.limited)
        self.assertEqual(result.items, ())
        self.assertIn("scanned pages", formatter.issues(result))

    def test_issue_result_cap(self):
        self.respond(
            Response([issue(i) for i in range(30)], headers={"Link": 'ignored; rel="next"'})
        )
        result = self.client.list_repository_issues("owner", "repo")
        self.assertEqual(len(result.items), 30)
        self.assertTrue(result.limited)
        self.assertEqual(self.open.call_count, 1)

    def test_issue_deduplication(self):
        self.respond(
            Response([issue(1)], headers={"Link": 'ignored; rel="next"'}),
            Response([issue(1), issue(2)]),
        )
        self.assertEqual(len(self.client.list_repository_issues("owner", "repo").items), 2)

    def test_latest_release(self):
        self.respond(Response(release()))
        result = self.client.get_latest_release("owner", "repo")
        self.assertEqual(result.tag, "v1.4.0")
        self.assertEqual(result.title, "A small release")
        self.assertIn("Released: 2026-09-18", formatter.release(result))
        self.assertIn(
            "https://github.com/owner/repo/releases/tag/v1.4.0", formatter.release(result)
        )

    def test_untitled_release(self):
        self.respond(Response({**release(), "name": None}))
        self.assertIsNone(self.client.get_latest_release("owner", "repo").title)

    def test_no_releases(self):
        self.respond(http_error(404), Response({"full_name": "owner/repo"}))
        self.assertIsNone(self.client.get_latest_release("owner", "repo"))
        self.assertEqual(urlsplit(self.open.call_args.args[0].full_url).path, "/repos/owner/repo")

    def test_missing_release_repository(self):
        self.respond(http_error(404), http_error(404))
        with self.assertRaisesRegex(GitHubError, 'Repository "owner/repo" was not found'):
            self.client.get_latest_release("owner", "repo")

    def test_401(self):
        self.respond(http_error(401))
        with self.assertRaisesRegex(GitHubError, "authentication failed"):
            self.client.list_user_repositories("octocat")

    def test_403_permission(self):
        self.respond(http_error(403))
        with self.assertRaisesRegex(GitHubError, "denied access"):
            self.client.list_user_repositories("octocat")

    def test_primary_rate_limit(self):
        self.respond(http_error(403, {"X-RateLimit-Remaining": "0"}))
        with self.assertRaisesRegex(GitHubError, "rate limit reached"):
            self.client.list_user_repositories("octocat")

    def test_secondary_rate_limit(self):
        self.respond(http_error(403, body=b'{"message":"secondary rate limit exceeded"}'))
        with self.assertRaisesRegex(GitHubError, "rate limit reached"):
            self.client.list_user_repositories("octocat")

    def test_retry_after(self):
        self.respond(http_error(403, {"Retry-After": "60"}))
        with self.assertRaisesRegex(GitHubError, "rate limit reached"):
            self.client.list_user_repositories("octocat")

    def test_429(self):
        self.respond(http_error(429))
        with self.assertRaisesRegex(GitHubError, "rate limit reached"):
            self.client.list_user_repositories("octocat")

    def test_missing_user(self):
        self.respond(http_error(404))
        with self.assertRaisesRegex(GitHubError, 'GitHub user "octocat" was not found'):
            self.client.list_user_repositories("octocat")

    def test_missing_issue_repository(self):
        self.respond(http_error(404))
        with self.assertRaisesRegex(GitHubError, "Repository"):
            self.client.list_repository_issues("owner", "repo")

    def test_network_failure(self):
        for error in (
            URLError("untrusted detail"),
            TimeoutError("untrusted detail"),
            OSError("untrusted detail"),
        ):
            self.respond(error)
            with (
                self.subTest(error=type(error)),
                self.assertRaisesRegex(GitHubError, "Could not reach GitHub"),
            ):
                self.client.list_user_repositories("octocat")

    def test_malformed_json(self):
        for body in (b"not json", b"\xff", b"{broken", b"[" * 2000):
            self.respond(Response(raw=body))
            with self.subTest(body=body[:10]), self.assertRaisesRegex(GitHubError, "malformed"):
                self.client.list_user_repositories("octocat")

    def test_invalid_repository_schema(self):
        for data in (
            {},
            None,
            [None],
            [repo(stars=True)],
            [repo(stars=-1)],
            [repo(language=3)],
            [{}],
        ):
            self.respond(Response(data))
            with self.subTest(data=data), self.assertRaisesRegex(GitHubError, "malformed"):
                self.client.list_user_repositories("octocat")

    def test_invalid_issue_schema(self):
        for data in (
            {},
            [None],
            [issue(number="42")],
            [issue(title=None)],
            [issue(state="unknown")],
        ):
            self.respond(Response(data))
            with self.subTest(data=data), self.assertRaisesRegex(GitHubError, "malformed"):
                self.client.list_repository_issues("owner", "repo")

    def test_invalid_release_schema(self):
        for data in (
            [],
            None,
            {},
            {**release(), "published_at": "not a date"},
            {**release(), "html_url": "https://evil.invalid/"},
            {**release(), "tag_name": 2},
        ):
            self.respond(Response(data))
            with self.subTest(data=data), self.assertRaisesRegex(GitHubError, "malformed"):
                self.client.get_latest_release("owner", "repo")

    def test_unexpected_http_status(self):
        for response in (http_error(500), http_error(422), Response([], status=204)):
            self.respond(response)
            with self.subTest(), self.assertRaisesRegex(GitHubError, "unexpected HTTP"):
                self.client.list_user_repositories("octocat")

    def test_redirect_refused(self):
        request = Request(
            "https://api.github.com/user/repos", headers={"Authorization": "synthetic"}
        )
        self.assertIsNone(
            _NoRedirects().redirect_request(request, None, 302, "", {}, "https://evil.invalid")
        )
        self.respond(http_error(301, {"Location": "https://evil.invalid"}))
        with self.assertRaisesRegex(GitHubError, "redirected"):
            self.client.list_user_repositories("octocat")
        self.assertEqual(self.open.call_count, 1)

    def test_response_size_limit(self):
        self.respond(Response(raw=b" " * (MAX_BYTES + 1)))
        with self.assertRaisesRegex(GitHubError, "2 MiB"):
            self.client.list_user_repositories("octocat")

    def test_oversized_page_rejected(self):
        self.respond(Response([repo()] * 31))
        with self.assertRaisesRegex(GitHubError, "malformed"):
            self.client.list_user_repositories("octocat")

    def test_direct_client_identifier_validation(self):
        with self.assertRaises(ParseError):
            self.client.list_repository_issues("https://evil.invalid", "repo")
        self.open.assert_not_called()

    def test_token_never_in_models_or_errors(self):
        secret = "synthetic-test-credential"
        with patch.dict(os.environ, {"GITHUB_TOKEN": secret}):
            self.respond(Response([repo(name=secret, language=secret)]))
            result = self.client.list_authenticated_repositories()
            self.assertNotIn(secret, repr(result))
            self.assertNotIn(secret, formatter.repositories(result))
            for error in (
                http_error(401, body=secret.encode()),
                URLError(secret),
                ValueError(secret),
            ):
                self.respond(error)
                try:
                    self.client.list_authenticated_repositories()
                except GitHubError as caught:
                    self.assertNotIn(secret, str(caught))
                    self.assertNotIn(secret, repr(caught))
                    self.assertNotIn(secret, "".join(traceback.format_exception(caught)))
                else:
                    self.fail("Expected sanitized failure")


class GitHubCliTests(OfflineCase, unittest.TestCase):
    def run_command(self, text, native="auto", dry_run=False):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                args = arguments(["--native", native])
                args.dry_run = dry_run
                status = run_line(text, Session(Path(directory)), args, interactive=False)[1]
            return output.getvalue(), status

    def test_repository_api_hint(self):
        self.respond(Response([repo()]))
        text, status = self.run_command("show github repos for octocat")
        self.assertEqual(status, 0)
        self.assertIn("GET /users/octocat/repos", text)
        self.assertIn("GitHub REST API", text)
        self.assertNotIn("PowerShell", text)

    def test_issue_api_hint(self):
        self.respond(Response([issue()]))
        text, status = self.run_command("show github issues in owner/repo")
        self.assertEqual(status, 0)
        self.assertIn("#42  Improve parser errors", text)
        self.assertIn("GET /repos/owner/repo/issues", text)

    def test_release_api_hint(self):
        self.respond(Response(release()))
        text, status = self.run_command("show latest github release of owner/repo")
        self.assertEqual(status, 0)
        self.assertIn("GET /repos/owner/repo/releases/latest", text)

    def test_no_release_has_both_hints(self):
        self.respond(http_error(404), Response({"full_name": "owner/repo"}))
        text, status = self.run_command("show latest github release of owner/repo")
        self.assertEqual(status, 0)
        self.assertIn("No published releases", text)
        self.assertIn("GET /repos/owner/repo\n", text)

    def test_missing_token_cli(self):
        text, status = self.run_command("show my github repos")
        self.assertEqual(status, 1)
        self.assertIn("Set the GITHUB_TOKEN environment variable", text)
        self.assertNotIn("Traceback", text)
        self.open.assert_not_called()

    def test_authenticated_hint_and_no_token_output(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "synthetic-test-credential"}):
            self.respond(Response([repo(name="synthetic-test-credential")]))
            text, status = self.run_command("show my github repos")
        self.assertEqual(status, 0)
        self.assertIn("GET /user/repos", text)
        self.assertNotIn("synthetic-test-credential", text)
        self.assertNotIn("Authorization", text)

    def test_hint_toggle_and_both(self):
        for native in ("off", "both"):
            self.respond(Response([]))
            text, status = self.run_command("show github repos for octocat", native=native)
            self.assertEqual(status, 0)
            self.assertEqual(text.count("GitHub REST API"), 0 if native == "off" else 1)

    def test_api_hint_redacts_accidental_credential_identifier(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "synthetic-test-credential"}):
            self.respond(Response([]))
            text, status = self.run_command("show github repos for synthetic-test-credential")
        self.assertEqual(status, 0)
        self.assertNotIn("synthetic-test-credential", text)
        self.assertIn("GET /users/[redacted]/repos", text)

    def test_dry_run_no_network(self):
        text, status = self.run_command("show github repos for octocat", dry_run=True)
        self.assertEqual(status, 1)
        self.assertIn("only for removal", text)
        self.open.assert_not_called()

    def test_unknown_does_not_call_api(self):
        for command in ("github whatever", "delete github issue 4", "fix my github repo"):
            text, status = self.run_command(command)
            self.assertEqual(status, 1)
            self.assertIn("don't understand", text)
        self.open.assert_not_called()

    def test_remote_terminal_controls_are_escaped(self):
        self.respond(Response([issue(title="hello\x1b[31m\nforged line")]))
        text, _ = self.run_command("show github issues in owner/repo")
        self.assertNotIn("\x1b", text)
        self.assertIn("hello\\u001b[31m forged line", text)

    def test_filesystem_still_offline(self):
        text, status = self.run_command("show files")
        self.assertEqual(status, 0)
        self.assertIn("(empty)", text)
        self.open.assert_not_called()

    def test_formatting_empty_and_limited(self):
        self.assertIn("No repositories", formatter.repositories(Listing(())))
        self.assertIn("No open issues", formatter.issues(Listing(())))
        self.assertIn("first 30", formatter.repositories(Listing((), True)))
        self.assertIn(
            "v1", formatter.release(Release("v1", None, "2026-01-01", "https://github.com/o/r"))
        )

    def test_error_is_terminal_error(self):
        self.assertIsInstance(GitHubError("safe"), TerminalError)
