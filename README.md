# English Terminal

**Say what you want the terminal to do.**

English Terminal is a deterministic CLI that maps a small, explicit English grammar
to local filesystem operations and **read-only GitHub REST API queries**. It helps
people learn terminal and API concepts: perform an operation, then see the underlying
shell command or REST endpoint.

It does not use an LLM to interpret commands. Built with Python 3.11+ and zero runtime
dependencies, v0.2.0 includes a GitHub API integration under active development.

[GitHub integration](#github-integration) · [Install and run](#install-and-run) ·
[Tests](#testing) · [Support](SUPPORT.md)

## A short session

Illustrative Windows session; filenames and release details below are examples,
not a claim about the current GitHub CLI release.

```text
english [demo]> make file hello.txt
Created file "hello.txt".
  ↳ PowerShell: New-Item -ItemType File -Path 'hello.txt'

english [demo]> show files
hello.txt
  ↳ PowerShell: Get-ChildItem -File

english [demo]> show latest github release of cli/cli
vX.Y.Z
GitHub CLI X.Y.Z
Released: YYYY-MM-DD
https://github.com/cli/cli/releases/tag/vX.Y.Z
  ↳ GitHub REST API:
    GET /repos/cli/cli/releases/latest
```

English Terminal is a bridge to the underlying tools, not a permanent replacement
for learning them. Hints are educational equivalents; their overwrite, encoding,
and listing behavior may differ from this CLI's behavior. They are never executed.

## GitHub integration

The integration calls GitHub's REST API through a dedicated Python HTTP client.
These four exact grammar patterns are supported:

| English command | GitHub REST API | Authentication |
| --- | --- | --- |
| `show github repos for <username>` | `GET /users/{username}/repos` | Optional for public repositories |
| `show github issues in <owner>/<repository>` | `GET /repos/{owner}/{repository}/issues` | Optional for public repositories |
| `show latest github release of <owner>/<repository>` | `GET /repos/{owner}/{repository}/releases/latest` | Optional for public repositories |
| `show my github repos` | `GET /user/repos` | Requires `GITHUB_TOKEN` |

- **Repositories:** up to 30, sorted by full name, with stars and language. “My repos”
  means repositories accessible to the account/token, including collaborations and
  accessible private repositories; it is not limited to personal ownership.
- **Issues:** up to 30 open issues, newest first, scanning at most three API pages
  of 30 entries. Pull requests returned by the issues endpoint are excluded.
- **Latest release:** tag, optional title, publication date, and URL. Drafts and
  prereleases are excluded. “Latest” follows the endpoint's selection, not a local
  semantic-version comparison.
- **Release not found:** a release 404 triggers `GET /repos/{owner}/{repository}`.
  If that metadata lookup succeeds, the CLI reports no published releases; another
  404 reports a missing or inaccessible repository. Visibility depends on access
  and token permissions.

Lists show a notice when results are limited. GitHub.com is the only API host;
there are no automatic retries. Rate-limit responses ask you to wait or supply
authentication. See [GitHub's rate-limit documentation](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api).

Inspect [the API client](english_terminal/github/client.py),
[offline integration tests](tests/test_github.py), and
[docs/github-integration.md](docs/github-integration.md) for the implementation,
request parameters, headers, and verification instructions.

### Authentication

Public queries work without authentication where GitHub permits it.
`show my github repos` requires **`GITHUB_TOKEN`**. When the variable is present,
the client uses it for public queries too; an invalid token fails rather than
silently retrying anonymously.

Set it in the shell that launches English Terminal, or provide it through your
preferred credential workflow. The `...` below is a placeholder, not a usable token.

```powershell
# PowerShell
$env:GITHUB_TOKEN = "..."
```

```sh
# Unix-like shells
export GITHUB_TOKEN="..."
```

Avoid saving actual token values in shell history or shared transcripts. Never put
them in repository files or English commands. GitHub CLI is not a dependency.

English Terminal reads the token from the process environment for GitHub API
authentication. It does not store it, write it to project configuration, or print
it. Normal HTTP errors omit request headers and server error bodies; exact token
text is redacted from displayed API fields and hints. No OAuth, browser login,
GitHub App authentication, or credential storage is implemented.

For private repositories, select only the repositories and read permissions needed:
Metadata for listing, Issues for issues, and Contents for releases. No write
permissions are needed. See the official endpoint links in the
[integration guide](docs/github-integration.md#authentication-and-permissions).
Account-query output can contain private repository names; treat it accordingly.

### Read-only scope

The client constructs **GET-only requests to `https://api.github.com`**, refuses
redirects, and limits each response to 2 MiB with a 10-second socket timeout.
There are no commands or client methods for creating issues, commenting, merging,
starring, forking, creating/deleting repositories, modifying releases, uploading
content, or changing account settings.

These are implementation constraints, not a substitute for a least-privilege token.
API hints contain endpoint paths, never authentication headers or executed curl
commands. Local filesystem commands remain offline.

## Install and run

Requires **Python 3.11+**. Run these commands from a local checkout; they install
into a virtual environment, not globally. No PyPI release is assumed.

### Development setup

Windows PowerShell (activation is optional):

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

The development extra adds Ruff. For a local installation without developer tools,
use `python -m pip install .` with your virtual environment's Python.

### Running English Terminal

Windows, without activation:

```powershell
.\.venv\Scripts\english
.\.venv\Scripts\english "show github repos for octocat"
```

Linux/macOS, without activation:

```sh
.venv/bin/english
.venv/bin/english "show github repos for octocat"
```

Alternatively, activate with `.\.venv\Scripts\Activate.ps1` in PowerShell or
`source .venv/bin/activate` in bash/zsh. Then use:

```sh
english
english "show files"
english "show github issues in python/cpython"
english "show latest github release of cli/cli"
english "show my github repos"
english --version
english --help
```

The account query needs the environment variable described above. You can also
run from the checkout without installing the package:

```sh
python -m english_terminal
python -m english_terminal "show files"
```

Use `python3` if that is your Python 3 executable. Pass each one-shot English command
as **one argument**, preserving inner quotes for paths with spaces:

```sh
english 'make folder "my project"'
```

| Option | Behavior |
| --- | --- |
| `--cwd <directory>` | Start in an existing directory |
| `--native both` | Show both shell dialects; GitHub API hints appear once |
| `--native off` | Hide shell and API hints |
| `--dry-run "remove folder demo"` | Preview removal without deleting |
| `--safety-root <directory>` | Select an existing removal boundary |

The prompt shows the current directory name; `where am i` shows its full path.
Navigation changes only the session, never the parent shell's directory. EOF or
`exit` ends the session. Ctrl+C cancels a confirmation or exits at the prompt.
Exit codes are 0 for success, 1 for command errors, 2 for CLI usage errors, and 130
for interruption. A session retains a nonzero status if an earlier command failed.

## Local commands and safety

| Group | Commands |
| --- | --- |
| Navigation | `where am i`, `move into <path>`, `move to <path>`, `move out` |
| Creating | `make folder <path>`, `make file <path>` |
| Viewing | `show files`, `show folders`, `show contents of <file>` |
| Managing | `copy <source> to <destination>`, `move <source> to <destination>`, `rename <source> to <destination>` |
| Removing | `remove file <path>`, `remove folder <path>` |
| Session | `help`, `help make folder`, `clear screen`, `exit`, `quit` |
| Aliases | `list files`, `list folders` |

Creation requires an existing parent. Creation and transfers refuse existing
destinations. Copy/move handle regular files; destinations are exact new paths,
not folders to append a source name to. Rename stays in the same parent.

Listings include hidden entries. Links are labeled and listed with files;
`show folders` excludes them. Text viewing supports UTF-8 with an optional BOM,
up to 1 MiB. Terminal controls are escaped. Color is disabled for redirected
output, `NO_COLOR`, or `TERM=dumb`.

- **Removal requires confirmation:** both input and output must be terminals, and
  the response must be exactly `remove it`. Other responses cancel. No force/yes
  flag or piped-confirmation bypass exists. Removal is permanent, not recycle-bin use.
- **Removal has a boundary:** by default, only children of the starting directory
  can be removed. The safety root itself, filesystem/drive roots, the user's home,
  known system directories, and the current directory or its ancestors are protected.
- **Recursive removal is previewed:** the CLI counts files and nested folders,
  rejects links, junctions, reparse points, and special files, then rechecks the
  snapshot after confirmation. The target folder is excluded from the folder count.
- **Path handling is conservative:** operations reject link traversal; Windows
  device names, alternate data streams, and ambiguous drive-relative paths are refused.

This prevents common accidents; it is not an OS security sandbox. The removal
boundary does not constrain navigation, reading, creation, or file transfers.
Operations are not transactions: failures can leave partial results, and checks
cannot eliminate races with other processes. Do not remove trees being changed by
an untrusted process. Mount changes are outside the guarantees. See
[architecture notes](docs/architecture.md#filesystem-guarantees-and-boundaries).

## Why no AI?

```text
input → tokenizer → deterministic grammar → typed command → executor
```

An explicit grammar makes behavior predictable, easier to audit, and easier to
test before destructive operations. It also lets users connect each phrase to a
specific shell command or API endpoint. Unsupported commands fail instead of having
their intent guessed. Suggestions come from known patterns and never execute.

Keywords ignore case; paths and GitHub identifiers preserve it. Quote paths with
spaces. Backslashes are literal, supporting Windows paths. There is no variable or
wildcard expansion, pipe, redirection, arbitrary prose interpretation, or shell
escape. See [the grammar guide](docs/grammar.md) for exact rules and contribution steps.

## Architecture

```text
English input
    ↓
tokenizer / parser
    ↓
typed command
    ↓
executor
    ├── filesystem services + safety policy
    └── GitHub API client
    ↓
result
    ├── human-readable output
    └── educational shell command / REST API hint
```

Parsing, execution, filesystem operations, HTTP handling, formatting, and safety
policy are separate modules. Parsing has no network side effects; HTTP details stay
inside the GitHub client. See [docs/architecture.md](docs/architecture.md) for design
decisions and [docs/github-integration.md](docs/github-integration.md) for API details.

## Testing

The last verified v0.2.0 Windows run completed **127 tests: 126 passed, 1 skipped**.
The skip requires symlink-creation privileges. GitHub tests use synthetic HTTP
responses and credentials; the normal suite does not depend on GitHub.com or a
developer token. Filesystem tests use temporary directories.

From the checkout, with the development environment activated:

```sh
python -m unittest discover -v
python -m unittest tests.test_github -v
python -m ruff check .
python -m ruff format --check .
```

Without activation, use `.\.venv\Scripts\python` on Windows or `.venv/bin/python`
on Linux/macOS. Optional live smoke testing requires explicit opt-in:

```sh
python -m tools.smoke_github --live
```

The smoke tool removes `GITHUB_TOKEN` from its own process before exercising public
queries and the missing-token account error. It is excluded from test discovery.
Public API behavior has been manually validated; the maintainer also reports
manual validation of authenticated `GET /user/repos`. That authenticated check is
separate from the anonymous smoke tool and offline tests.

The [CI configuration](.github/workflows/ci.yml) defines Python 3.11/3.13 jobs on
Windows, Linux, and macOS. Configuration alone does not establish that those jobs
have run or passed; the local results above are from Windows.

## Current limitations

- Fixed grammar, not arbitrary English. Quoting is intentionally smaller than a
  shell's: there are no quote escapes or `~` expansion.
- GitHub.com only, read-only, bounded results, no automatic HTTP retries or persistent
  cache. No OAuth/browser login, GitHub App authentication, git operations, or cloning.
- Copy/move support regular files only. Folder rename is Windows-only and uses the
  removal boundary. File rename on Unix requires filesystem hard-link support.
- File copies preserve bytes, not ACLs, ownership, timestamps, alternate streams,
  or extended attributes. Moves are not atomic; an unlink failure can leave both files.
- No persistent history, completion, editor, undo, or arbitrary shell execution.
- Large deletion previews retain metadata in memory and can be slow.

## Possible next steps

Areas for future consideration include portable directory transfers, recycle-bin
integration, and completion generated from the grammar. These are not commitments;
the current scope remains small and deterministic.

## Support

See [SUPPORT.md](SUPPORT.md) for maintainer contact routing and what to include in a
report. Use the source repository's Issues tab when available. Do not include tokens,
authorization headers, or private repository listings in public reports.

## License

[MIT](LICENSE).
