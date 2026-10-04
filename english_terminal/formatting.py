"""Safe plain-text rendering, with optional restrained ANSI styling."""

import os
import sys


def safe_text(text: str) -> str:
    return "".join(c if (c in "\n\t" or c.isprintable()) else f"\\u{ord(c):04x}" for c in text)


def emit(text: str = "", *, accent: bool = False) -> None:
    text = safe_text(text)
    if (
        accent
        and sys.stdout.isatty()
        and "NO_COLOR" not in os.environ
        and os.environ.get("TERM") != "dumb"
    ):
        text = f"\033[36m{text}\033[0m"
    encoding = sys.stdout.encoding or "utf-8"
    print(text.encode(encoding, errors="backslashreplace").decode(encoding))


def error_message(error: Exception) -> str:
    if isinstance(error, FileExistsError):
        return "The destination already exists. Choose a new name; nothing is overwritten."
    if isinstance(error, FileNotFoundError):
        return "That path does not exist. Check its name and parent directory."
    if isinstance(error, PermissionError):
        return "Permission denied. Choose a location you can access."
    if isinstance(error, NotADirectoryError):
        return "A path component is not a directory."
    if isinstance(error, IsADirectoryError):
        return "That path is a directory; this operation needs a file."
    if isinstance(error, OSError):
        return f"Filesystem operation failed: {error.strerror or str(error)}"
    return str(error)
