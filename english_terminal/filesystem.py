"""Filesystem primitives; never invoke a shell."""

import os
import shutil
from pathlib import Path

from .models import TerminalError
from .safety import reject_link_chain


def resolve_path(cwd: Path, raw: str) -> Path:
    if "\x00" in raw or any(ord(c) < 32 for c in raw):
        raise TerminalError("Paths cannot contain control characters.")
    path = Path(raw)
    if os.name == "nt":
        if ":" in raw[2:] or (":" in raw and not path.drive):
            raise TerminalError("Alternate data streams are not supported.")
        if raw.startswith(("\\\\?\\", "\\\\.\\")):
            raise TerminalError("Windows device paths are not supported.")
        if path.drive and not path.root:
            raise TerminalError("Use an absolute drive path, such as C:\\Projects.")
        reserved = getattr(os.path, "isreserved", None)
        if reserved(raw) if reserved else path.is_reserved():
            raise TerminalError("Windows device names are not valid paths.")
        if any(part.endswith((".", " ")) and part not in (".", "..") for part in path.parts):
            raise TerminalError("Windows path components cannot end with a dot or space.")
    # Check before normalization so a link/../path cannot conceal a link traversal.
    candidate = path if path.is_absolute() else cwd / path
    reject_link_chain(candidate)
    return candidate.resolve(strict=False)


def require_regular(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(str(path))
    if not path.is_file():
        raise TerminalError("This command needs a regular file.")


def require_new(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(str(path))


def copy_file(source: Path, destination: Path) -> None:
    require_regular(source)
    # Exclusive creation: existing destination contents are never overwritten.
    with source.open("rb") as incoming, destination.open("xb") as outgoing:
        try:
            shutil.copyfileobj(incoming, outgoing)
        except BaseException:
            outgoing.close()
            destination.unlink()
            raise


def rename_no_replace(source: Path, destination: Path) -> None:
    require_new(destination)
    if os.name == "nt":
        source.rename(destination)  # Windows rename refuses an existing destination.
    elif source.is_file():
        os.link(source, destination)  # Atomic no-clobber destination creation.
        source.unlink()
    else:
        raise TerminalError("Folder rename is currently supported only on Windows.")
