# GitHub integration — English Terminal v0.2

English Terminal is a deterministic developer terminal for beginners. It maps a
small English grammar to safe filesystem operations and, in v0.2, read-only GitHub
REST queries. It teaches the underlying shell commands or REST endpoints. There is
no LLM, arbitrary natural-language interpretation, or English-to-curl execution.

The GitHub feature is **under active development**. This document describes an
implemented integration, not GitHub approval or Developer Program membership.
No application is submitted by the project or its tooling.

## Endpoint-to-feature mapping

All requests use `https://api.github.com`, method `GET`,
`Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2026-03-10`, and
`User-Agent: English-Terminal/0.2.0`.

| Product command/behavior | Endpoint | Parameters / bounds |
| --- | --- | --- |
| `show github repos for <username>` | `/users/{username}/repos` | `per_page=30&page=1&sort=full_name&direction=asc` |
| `show github issues in <owner>/<repository>` | `/repos/{owner}/{repository}/issues` | `state=open&per_page=30&page=1..3&sort=created&direction=desc`; filter entries containing `pull_request`, deduplicate issue numbers, return at most 30 issues |
| `show latest github release of <owner>/<repository>` | `/repos/{owner}/{repository}/releases/latest` | Single request for GitHub's latest published non-prerelease |
| Release-404 disambiguation | `/repos/{owner}/{repository}` | One additional metadata lookup; on success the CLI reports no published releases, another 404 means missing/inaccessible repo; visibility depends on access and token permissions |
| `show my github repos` | `/user/repos` | `per_page=30&page=1&sort=full_name&direction=asc`; accessible repositories, not restricted to personal ownership |

The UI shows the endpoint paths after successful commands. Query parameters are
fixed implementation policy, documented here rather than repeated in each hint.
For a missing release on an accessible repository, both endpoints are shown.
`--native off` suppresses hints and `--native both` does not duplicate API hints.

## Authentication and permissions

The sole authentication source is the `GITHUB_TOKEN` process environment variable.
Public commands can run anonymously; a supplied token is used as a Bearer header.
The account-listing command refuses to call HTTP when the variable is missing.
An invalid token fails clearly; there is no anonymous retry of an authenticated
failure, interactive login, OAuth, GitHub App, credential manager, or stored token.

For shell environment examples, see [README authentication](../README.md#authentication).
Users may supply the variable through their preferred credential workflow; GitHub
CLI is not required. Do not put token values in project configuration or source files.

Use no token for public-only testing. Where private data is needed, select only the
repositories required and use fine-grained read permissions: Metadata for repository
listing, Issues for issue reads, Contents for release reads. The tool never requests
write access; the token/account still determines which resources GitHub returns.

Official contracts:

- [Repository listing and metadata](https://docs.github.com/en/rest/repos/repos)
- [Repository issues](https://docs.github.com/en/rest/issues/issues)
- [Latest release](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)
- [API versioning](https://docs.github.com/en/rest/about-the-rest-api/api-versions)
- [Rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)

## Privacy, security, and read-only scope

- All transport requests are GET, to a fixed HTTPS host. There are no write endpoints,
  arbitrary API paths, request bodies, git commands, uploads, or shell execution.
- Validated identifiers cannot supply hosts, query parameters, or traversal segments.
  A server `Link` header only indicates whether another page exists; URLs from it
  are never followed. Each next issue page is constructed from the validated path.
- Redirects are disabled, including same-host redirects. A renamed repository may
  therefore require its current identifier. Credentials cannot follow a redirect.
- Tokens are used in memory only, never retained on client instances, cached, logged,
  persisted, or included in educational hints. Invalid token format errors do not
  echo the value. HTTP/network errors are converted to fixed human-readable messages
  without original exception details or server error bodies. Exact credential text
  echoed in displayed API fields is redacted before creating public result models.
- No filesystem content is sent. GitHub receives the requested identifiers, normal
  HTTP metadata, and optional authentication. Private repository names can appear
  in account-query output. The application does not persist API results or telemetry.
- Standard urllib TLS verification remains enabled. Standard environment proxy
  behavior is retained; users should trust their configured HTTPS proxy and CA store.
- Each request has a 10-second socket timeout and a 2 MiB response limit. This is
  not a global command deadline. Listings have strict page/result bounds and no
  automatic retries. Primary/secondary rate-limit errors ask the user to wait.
- Response fields and shapes are validated. Terminal escapes are sanitized and
  embedded line breaks are flattened in displayed fields. Response links are not opened.

## Run and test

From an installed/activated environment:

```sh
english --version
english "show github repos for octocat"
english "show github issues in python/cpython"
english "show latest github release of cli/cli"
english "show my github repos"
python -m unittest tests.test_github -v
python -m unittest discover -v
python -m ruff check .
python -m ruff format --check .
```

The account command needs `GITHUB_TOKEN`; without it, it demonstrates the friendly
authentication-required error. Windows without activation can use
`.\.venv\Scripts\english` and `.\.venv\Scripts\python`. Module execution through
`python -m english_terminal` also works.

Normal tests are offline and intercept `_open`, the sole HTTP transport boundary.
They substitute synthetic credentials before testing authentication; they do not
use the developer's token. Cases cover grammar, response models, bounded pagination,
PR filtering, missing releases, status/errors, redirection, token leakage, and hints.
Existing filesystem and safety tests remain in the full suite.

Optional public live check (explicit opt-in, excluded from test discovery):

```sh
python -m tools.smoke_github --live
```

The smoke tool removes `GITHUB_TOKEN` only from its own process before calling the
actual CLI functions. It exercises all three public commands and the missing-token
account error. It performs no authenticated requests or GitHub mutations.

### Validation status

The last verified v0.2.0 Windows suite ran 127 tests: 126 passed and one was skipped
because symlink creation requires OS privileges. Public queries and no-release
handling were also manually validated. The maintainer reports a separate successful
manual validation of authenticated `GET /user/repos`; it is not part of the anonymous
smoke tool. The CI matrix is configured for Windows, Linux, and macOS, but those
configured jobs are not evidence of completed runs on every platform.

## Support and current limits

Support/contact routing is maintained in [SUPPORT.md](../SUPPORT.md) at the repository
root. Do not include tokens, authorization headers, or private repository output in
reports. General installation instructions are in [README.md](../README.md).

GitHub.com only; no enterprise server URLs, write operations, search, cloning,
GraphQL, login workflows, release assets, issue bodies, or complete account exports.
Lists may be truncated and may change between pages. “My repos” means repositories
visible to the account/token, including collaborations and accessible organizations.
The latest-release endpoint excludes drafts and prereleases. Network availability,
token access, and GitHub rate limits remain external dependencies for these commands.
