"""Educational translations only. These strings are never executed."""

import shlex
from pathlib import PureWindowsPath

from .models import Action, Command


def equivalent(command: Command, platform: str) -> str | None:
    ps = platform == "PowerShell"
    quote = (lambda s: "'" + s.replace("'", "''") + "'") if ps else shlex.quote
    args = [quote(a) for a in command.args]
    a = args[0] if args else ""
    b = args[1] if len(args) > 1 else ""
    pairs = {
        Action.LOCATION: ("Get-Location", "pwd"),
        Action.FILES: ("Get-ChildItem -File", "find . ! -name . -prune -type f"),
        Action.FOLDERS: ("Get-ChildItem -Directory", "find . ! -name . -prune -type d"),
        Action.CREATE_FOLDER: (f"New-Item -ItemType Directory -Path {a}", f"mkdir -- {a}"),
        Action.CREATE_FILE: (f"New-Item -ItemType File -Path {a}", f"touch -- {a}"),
        Action.ENTER: (f"Set-Location -LiteralPath {a}", f"cd -- {a}"),
        Action.UP: ("Set-Location ..", "cd .."),
        Action.READ: (f"Get-Content -LiteralPath {a}", f"cat -- {a}"),
        Action.COPY: (f"Copy-Item -LiteralPath {a} -Destination {b}", f"cp -i -- {a} {b}"),
        Action.MOVE: (f"Move-Item -LiteralPath {a} -Destination {b}", f"mv -i -- {a} {b}"),
        Action.RENAME: (
            f"Rename-Item -LiteralPath {a} -NewName "
            + (quote(PureWindowsPath(command.args[1]).name) if len(args) > 1 else ""),
            f"mv -i -- {a} {b}",
        ),
        Action.REMOVE_FILE: (f"Remove-Item -LiteralPath {a} -Confirm", f"rm -i -- {a}"),
        Action.REMOVE_FOLDER: (f"Remove-Item -LiteralPath {a} -Recurse -Confirm", f"rm -ri -- {a}"),
        Action.CLEAR: ("Clear-Host", "clear"),
    }
    pair = pairs.get(command.action)
    return pair[0 if ps else 1] if pair else None
