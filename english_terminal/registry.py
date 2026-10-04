"""The language catalog. Placeholders each consume exactly one path token."""

from dataclasses import dataclass

from .models import Action


@dataclass(frozen=True)
class Definition:
    pattern: str
    action: Action
    group: str
    description: str
    alias: bool = False


DEFINITIONS = (
    Definition("where am i", Action.LOCATION, "Navigation", "Show the current directory."),
    Definition("move into <path>", Action.ENTER, "Navigation", "Enter an existing directory."),
    Definition("move to <path>", Action.ENTER, "Navigation", "Go to an existing directory."),
    Definition("move out", Action.UP, "Navigation", "Go to the parent directory."),
    Definition("make folder <path>", Action.CREATE_FOLDER, "Creating", "Create one new directory."),
    Definition("make file <path>", Action.CREATE_FILE, "Creating", "Create a new, empty file."),
    Definition("show files", Action.FILES, "Viewing", "List files and links in this directory."),
    Definition("show folders", Action.FOLDERS, "Viewing", "List directories, excluding links."),
    Definition("show contents of <file>", Action.READ, "Viewing", "Read UTF-8 text (up to 1 MiB)."),
    Definition("copy <source> to <destination>", Action.COPY, "Managing", "Copy a regular file."),
    Definition("move <source> to <destination>", Action.MOVE, "Managing", "Move a regular file."),
    Definition(
        "rename <source> to <destination>",
        Action.RENAME,
        "Managing",
        "Rename a file or folder in the same parent.",
    ),
    Definition(
        "remove file <path>",
        Action.REMOVE_FILE,
        "Removing",
        "Confirm, then permanently delete a regular file.",
    ),
    Definition(
        "remove folder <path>",
        Action.REMOVE_FOLDER,
        "Removing",
        "Preview and confirm recursive deletion.",
    ),
    Definition("clear screen", Action.CLEAR, "Session", "Clear an interactive terminal."),
    Definition("help", Action.HELP, "Session", "Show this command guide."),
    Definition("exit", Action.EXIT, "Session", "Leave the session."),
    Definition("quit", Action.EXIT, "Session", "Leave the session.", True),
    Definition("list files", Action.FILES, "Viewing", "Alias for show files.", True),
    Definition("list folders", Action.FOLDERS, "Viewing", "Alias for show folders.", True),
    Definition(
        "show github repos for <username>",
        Action.GITHUB_REPOS,
        "GitHub",
        "List up to 30 public repositories.",
    ),
    Definition(
        "show github issues in <owner>/<repository>",
        Action.GITHUB_ISSUES,
        "GitHub",
        "List up to 30 open issues, excluding pull requests.",
    ),
    Definition(
        "show latest github release of <owner>/<repository>",
        Action.GITHUB_RELEASE,
        "GitHub",
        "Show the latest published release.",
    ),
    Definition(
        "show my github repos",
        Action.GITHUB_MY_REPOS,
        "GitHub",
        "List up to 30 accessible repositories; requires GITHUB_TOKEN.",
    ),
)


def help_text(topic: str = "") -> str:
    definitions = [d for d in DEFINITIONS if not d.alias]
    if topic:
        definitions = [d for d in definitions if d.pattern.startswith(topic.casefold())]
        if not definitions:
            return f'No command help for "{topic}". Type "help" for the command guide.'
    lines = ["English Terminal · command guide", ""]
    groups = dict.fromkeys(d.group for d in definitions)
    for group in groups:
        lines.append(group)
        for d in definitions:
            if d.group == group:
                lines.append(f"  {d.pattern:<36} {d.description}")
        lines.append("")
    lines.append('Quote paths with spaces: make folder "my project"')
    lines.append("Keywords ignore case. Paths keep their case. Nothing runs through a shell.")
    return "\n".join(lines)
