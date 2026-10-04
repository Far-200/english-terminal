# Architecture and decisions

## Why Python

Python offers readable explicit command models, first-class Windows paths,
cross-platform filesystem operations, installable console entry points, and a
standard-library test runner. Node would also fit, but requires more care around
cross-platform path and terminal details; Go offers a standalone binary but adds
a compilation workflow. For this small educational CLI, Python keeps the runtime
dependency count at zero. Python 3.11 is the minimum supported version.

## Flow

`CLI → tokenizer → parser → Command → Session → filesystem/safety or GitHub client → Result`

The registry owns the language and help descriptions. The parser has no filesystem
dependencies. The session owns an absolute current directory and a fixed removal
root; it never calls `os.chdir`. Results contain user-facing text and an explicit
decision about whether a native hint is appropriate. Translation is downstream of
successful execution, with platform-specific argument quoting.

The CLI owns terminal detection and confirmation input. Tests inject a callback
into the session to validate confirmation without touching a real terminal.
Production CLI deletion supplies that callback only when both stdin and stdout
are terminals. One-shot removal can therefore be confirmed from a terminal but
cannot be automated by piping `remove it`.

## Filesystem guarantees and boundaries

All paths are checked for link/reparse traversal before normalization. Windows
device namespaces and alternate data streams are refused. Ordinary operations use
`pathlib`, exclusive file opens, and `shutil.copyfileobj`. Destinations are exact
paths; existing files are never deliberately truncated or merged.

Windows rename has no-replace semantics. Unix file rename uses hard-link creation
followed by unlinking the source to avoid a check-then-overwrite race; unsupported
filesystems return a friendly error. Unix directory rename is refused because the
portable standard-library operation can replace a concurrently created empty
directory. Copy/move deliberately support only regular files in this version.

Removal validates the boundary, protected locations, and current-directory ancestry.
An iterative scan rejects links and special files and records identity, type, size,
and modification time. The preview counts regular files and descendant directories.
The same snapshot must match after exact confirmation. Recursive removal uses
Python's `shutil.rmtree`, which does not deliberately traverse directory symlinks
or junction targets. Errors remain visible; cancellation produces no native hint.

These checks do not form a security boundary against concurrent mutation. Scanning
and deleting are separate steps, and platform behavior differs. Adversarial races,
mount changes, and transaction/rollback support are outside the MVP's guarantees.
The removal boundary does not constrain non-removal operations. Future stronger
guarantees need platform-specific handle-relative APIs, not more string checks.

## Testing strategy

- Tokenizer/parser tests cover the catalog, quoting, casing, malformed input,
  shared verbs, Windows paths, and suggestions without filesystem access.
- Filesystem tests create isolated temporary workspaces and assert actual bytes,
  navigation state, exact destinations, and failure behavior.
- Safety tests cover confirmation, cancellation, dry runs, boundaries, roots,
  home/system locations, current-directory protection, changed snapshots, links,
  and real Windows junctions.
- CLI subprocess tests cover installation-independent module execution, help,
  version, exit status, piped REPLs, and refusal of piped removal confirmation.

Ruff handles formatting and static linting. GitHub Actions defines a Windows,
Linux, and macOS matrix. No model service is part of the application. GitHub tests
stub the HTTP boundary; local commands and the normal test suite remain offline.

## v0.2 GitHub path

`registry → parser → Command(Action.GITHUB_*) → Session → github.service → GitHubClient`

Four explicit actions use the existing frozen `Command` representation. Pure
identifier validation happens before execution and is repeated at the public client
boundary. `github/models.py` defines repository, issue, release, and bounded-list
dataclasses. `github/formatter.py` formats only validated fields. The result type
has an optional `api_hints` tuple, so the CLI can render successful API endpoint
hints without understanding HTTP or interfering with filesystem native hints.

`github/client.py` owns fixed GitHub.com HTTPS endpoints, GET requests, headers,
bounded pagination, schema checks, and sanitized errors. It reads credentials only
from the environment for each request, retains none on the client, rejects redirects,
and never exposes HTTP error bodies. There are no mutation methods or arbitrary
endpoint commands. See [the integration guide](github-integration.md) for the
endpoint contract, privacy behavior, and live verification instructions.
