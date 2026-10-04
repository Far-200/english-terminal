# Grammar and contributor guide

The language is a catalog of exact patterns, not natural-language understanding.

```text
command := literal* (path literal*)*
path    := unquoted-token | single-quoted-token | double-quoted-token
```

Whitespace outside quotes is ignored. Keywords are case-insensitive; quoted
keywords do not match literals. Placeholders consume exactly one token. Quote
paths with spaces. Backslashes are always literal, including before a closing
quote. Quotes must surround the whole token; empty quoted tokens are rejected.
Use double quotes around an apostrophe, or single quotes around a double quote.
Names containing both quote kinds cannot currently be expressed.

```text
make folder "My Project"          → CREATE_FOLDER, ("My Project",)
move to C:\Projects               → ENTER, ("C:\Projects",)
copy "road to home" to backup     → COPY, ("road to home", "backup")
move a to b                      → MOVE, ("a", "b")
move into a                      → ENTER, ("a",)
```

`help` is the single meta-command: the remaining tokens form a registry prefix,
so `help make folder` filters the normal catalog. Aliases are explicit registry
entries. No trailing prose, optional inference, or fallback shell execution exists.

## Add a command

1. Add an `Action` enum member to `models.py` if this is a new operation.
2. Add a `Definition` in `registry.py`: pattern, action, help group, description.
   Use placeholders such as `<path>`; use `alias=True` for spelling aliases.
3. Add a handler to the executor's dispatch table. Consume structured arguments,
   resolve paths through `Session.path`, and use filesystem APIs. Keep parser
   tests independent of filesystem state. Return a `Result`; set `teach=False`
   when no operation completed (for example, cancellation).
4. Add educational translations to `native.py`. Quote every user argument.
   Never execute the resulting string.
5. For destructive operations, extend the safety policy and confirmation workflow
   before exposing the new grammar. Do not introduce a force bypass.
6. Add parser cases, malformed/ambiguous cases, and temporary-directory integration
   tests. Update the README and help description together.

Patterns are tried in registry order. Avoid overlapping patterns that have the same
token count and literal positions. Tests iterate every registered definition; add
an explicit disambiguation test whenever verbs are shared. Suggestions compare
input with known literal prefixes and return at most three complete patterns.
Their output is informational and never passed back into the executor.

## GitHub commands (v0.2)

The four GitHub patterns live in the same registry and become `GITHUB_REPOS`,
`GITHUB_ISSUES`, `GITHUB_RELEASE`, or `GITHUB_MY_REPOS` actions. They use the existing
typed `Command` rather than a parallel parser. `github/identifiers.py` validates
usernames and `owner/repository` identifiers after an exact pattern match. URLs,
query strings, fragments, path traversal, and extra path components are rejected
before any network call. Keywords ignore case; identifier casing is preserved.

Usernames accept 1–39 ASCII letters/digits/hyphens, beginning and ending with a
letter/digit. Repository names accept 1–100 ASCII letters/digits, `_`, `-`, and `.`,
excluding `.` and `..`. This deliberately restricted grammar is not URL parsing.

The GitHub service dispatches only these registered actions to four client methods.
API hints belong in `Result.api_hints`, not in shell translation. Unsupported inputs
such as `fix my github repo` use the same unknown-command flow and never call HTTP.
New GitHub grammar requires offline HTTP-boundary tests as well as parser tests;
v0.2 is explicitly read-only, so do not add mutation commands.
