"""Dispatch parsed commands, keeping session state separate from process cwd."""

import shutil
from collections.abc import Callable
from pathlib import Path

from . import filesystem as fs
from .github import service as github_service
from .github.identifiers import GITHUB_ACTIONS
from .models import Action, Command, Result, TerminalError
from .registry import help_text
from .safety import SafetyPolicy

Confirm = Callable[[str], str]


class Session:
    def __init__(self, cwd: Path, safety_root: Path | None = None):
        self.cwd = cwd.resolve(strict=True)
        if not self.cwd.is_dir():
            raise TerminalError("The starting path must be a directory.")
        self.safety = SafetyPolicy(safety_root or self.cwd)

    def execute(
        self, command: Command, confirm: Confirm | None = None, dry_run: bool = False
    ) -> Result:
        handlers = {
            Action.LOCATION: self.location,
            Action.FILES: self.listing,
            Action.FOLDERS: self.listing,
            Action.CREATE_FILE: self.create,
            Action.CREATE_FOLDER: self.create,
            Action.ENTER: self.navigate,
            Action.UP: self.navigate,
            Action.READ: self.read,
            Action.COPY: self.transfer,
            Action.MOVE: self.transfer,
            Action.RENAME: self.transfer,
        }
        if command.action == Action.HELP:
            return Result(help_text(command.args[0] if command.args else ""), False)
        if command.action in (Action.REMOVE_FILE, Action.REMOVE_FOLDER):
            return self.remove(command, confirm, dry_run)
        if command.action in (Action.EXIT, Action.CLEAR):
            return Result("", False)
        if dry_run:
            raise TerminalError("--dry-run is supported only for removal commands.")
        if command.action in GITHUB_ACTIONS:
            return github_service.execute(command)
        return handlers[command.action](command)

    def path(self, raw: str) -> Path:
        return fs.resolve_path(self.cwd, raw)

    def location(self, command: Command) -> Result:
        return Result(str(self.cwd))

    def listing(self, command: Command) -> Result:
        from .safety import is_link

        lines = []
        for path in sorted(self.cwd.iterdir(), key=lambda p: (p.name.casefold(), p.name)):
            link = is_link(path)
            folder = not link and path.is_dir()
            if folder == (command.action == Action.FOLDERS):
                lines.append(path.name + (" [link]" if link else "/" if folder else ""))
        return Result("\n".join(lines) or "(empty)")

    def create(self, command: Command) -> Result:
        path = self.path(command.args[0])
        if command.action == Action.CREATE_FOLDER:
            path.mkdir()
            kind = "folder"
        else:
            with path.open("xb"):
                pass
            kind = "file"
        return Result(f'Created {kind} "{path.name}".')

    def navigate(self, command: Command) -> Result:
        path = self.path(".." if command.action == Action.UP else command.args[0])
        if not path.exists():
            raise FileNotFoundError(str(path))
        if not path.is_dir():
            raise TerminalError("That path is not a directory.")
        self.cwd = path
        return Result(f"Now inside {path}")

    def read(self, command: Command) -> Result:
        path = self.path(command.args[0])
        fs.require_regular(path)
        with path.open("rb") as stream:
            data = stream.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise TerminalError("That file exceeds the 1 MiB display limit.")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeError as error:
            raise TerminalError("That file is not UTF-8 text.") from error
        if "\x00" in text:
            raise TerminalError("That file appears to be binary.")
        return Result(text or "(empty file)")

    def transfer(self, command: Command) -> Result:
        source, destination = (self.path(a) for a in command.args)
        if not source.exists():
            raise FileNotFoundError(str(source))
        fs.require_new(destination)
        if command.action == Action.RENAME:
            if source.parent != destination.parent:
                raise TerminalError("Rename keeps the same parent. Use move for moving a file.")
            if source.is_dir():
                self.safety.validate(source, self.cwd)
            fs.rename_no_replace(source, destination)
        else:
            fs.copy_file(source, destination)
            if command.action == Action.MOVE:
                source.unlink()
        verb = {Action.COPY: "Copied", Action.MOVE: "Moved", Action.RENAME: "Renamed"}[
            command.action
        ]
        return Result(f'{verb} "{source.name}" to "{destination.name}".')

    def remove(self, command: Command, confirm: Confirm | None, dry_run: bool) -> Result:
        path = self.path(command.args[0])
        if command.action == Action.REMOVE_FILE:
            fs.require_regular(path)
        elif not path.is_dir():
            raise TerminalError("That path is not an existing directory.")
        before = self.safety.snapshot(path, self.cwd)
        preview = (
            f"This will permanently remove:\n  {path}\n  {before.files} files\n"
            f"  {before.folders} folders (inside target)"
        )
        if dry_run:
            return Result(preview + "\nDry run: nothing removed.", False)
        if confirm is None:
            raise TerminalError(
                "Removal requires an interactive terminal. Use --dry-run to preview."
            )
        if confirm(preview + '\nType "remove it" to continue: ') != "remove it":
            return Result("Cancelled. Nothing removed.", False)
        if self.safety.snapshot(path, self.cwd) != before:
            raise TerminalError(
                "The target changed after the preview. Removal cancelled; try again."
            )
        if command.action == Action.REMOVE_FILE:
            path.unlink()
        else:
            shutil.rmtree(path)
        return Result(f'Removed "{path.name}".')
