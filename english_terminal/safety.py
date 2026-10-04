"""Conservative removal policy. No links, protected ancestors, or boundary escapes."""

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .models import TerminalError


def is_link(path: Path) -> bool:
    info = path.lstat()
    # All Windows reparse points are refused, including junctions and cloud placeholders.
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def reject_link_chain(path: Path) -> None:
    for part in (path, *path.parents):
        if (part.exists() or part.is_symlink()) and is_link(part):
            raise TerminalError(f'Links and junctions are not supported here: "{part}".')


@dataclass(frozen=True)
class Snapshot:
    entries: tuple[tuple[str, int, int, int, int], ...]
    files: int
    folders: int


class SafetyPolicy:
    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise TerminalError("The safety root must be a directory.")
        self.home = Path.home().resolve()

    def validate(self, path: Path, cwd: Path) -> None:
        reject_link_chain(path)
        target = path.resolve(strict=True)
        if target == self.root or not target.is_relative_to(self.root):
            raise TerminalError("Removal is limited to children of the safety root.")
        protected = [self.home, Path(target.anchor)]
        if os.name == "nt":
            for key in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
                if os.environ.get(key):
                    protected.append(Path(os.environ[key]).resolve())
            protected.extend(
                Path(target.anchor) / name
                for name in (
                    "Windows",
                    "Program Files",
                    "Program Files (x86)",
                    "ProgramData",
                    "$Recycle.Bin",
                    "System Volume Information",
                )
            )
        else:
            protected.extend(
                Path(p)
                for p in (
                    "/bin",
                    "/sbin",
                    "/etc",
                    "/usr",
                    "/var",
                    "/boot",
                    "/dev",
                    "/proc",
                    "/sys",
                    "/lib",
                    "/lib64",
                    "/opt",
                    "/System",
                    "/Library",
                    "/Applications",
                )
            )
        for item in protected:
            if target == item or item.is_relative_to(target):
                raise TerminalError("That directory is protected from removal.")
            if item != self.home and item != Path(target.anchor) and target.is_relative_to(item):
                raise TerminalError("System directories are protected from removal.")
        if os.name == "nt" and target == Path(target.anchor) / "Users":
            raise TerminalError("The users directory is protected from removal.")
        if cwd == target or cwd.is_relative_to(target):
            raise TerminalError("Move out of that directory before removing it.")

    def snapshot(self, path: Path, cwd: Path) -> Snapshot:
        self.validate(path, cwd)
        entries = []
        files = folders = 0
        pending = [path]
        while pending:
            current = pending.pop()
            if is_link(current):
                raise TerminalError("Removal refused: the tree contains a link or junction.")
            info = current.lstat()
            if stat.S_ISDIR(info.st_mode):
                if current != path:
                    folders += 1
                pending.extend(current.iterdir())
            elif stat.S_ISREG(info.st_mode):
                files += 1
            else:
                raise TerminalError("Removal refused: the tree contains a special file.")
            entries.append(
                (str(current), info.st_ino, info.st_size, info.st_mtime_ns, info.st_mode)
            )
        return Snapshot(tuple(sorted(entries)), files, folders)
