"""REPL and one-shot entry point."""

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .executor import Session
from .formatting import emit, error_message, safe_text
from .models import Action, TerminalError
from .native import equivalent
from .parser import parse


def arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="English Terminal — Say what you want the terminal to do."
    )
    parser.add_argument("command", nargs="?", help='one English command, e.g. "show files"')
    parser.add_argument("--version", action="version", version=f"English Terminal {__version__}")
    parser.add_argument("--cwd", type=Path, default=Path.cwd(), help="starting directory")
    parser.add_argument(
        "--safety-root", type=Path, help="removal boundary (default: starting directory)"
    )
    parser.add_argument(
        "--native", choices=("auto", "both", "off"), default="auto", help="educational equivalents"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="preview a one-shot removal without deleting"
    )
    args = parser.parse_args(argv)
    if args.dry_run and args.command is None:
        parser.error("--dry-run requires a one-shot removal command")
    return args


def run_line(
    text: str, session: Session, args: argparse.Namespace, *, interactive: bool
) -> tuple[bool, int]:
    try:
        command = parse(text)
        if command.action == Action.EXIT:
            return False, 0
        if command.action == Action.CLEAR:
            if sys.stdout.isatty():
                print("\033[2J\033[H", end="", flush=True)
            else:
                emit("Screen clearing is available in a terminal.")
        else:

            def confirm(prompt: str) -> str:
                emit(prompt)
                return input("> ")

            result = session.execute(command, confirm if interactive else None, args.dry_run)
            emit(result.text)
            if not result.teach:
                return True, 0
            if result.api_hints:
                if args.native != "off":
                    emit("  ↳ GitHub REST API:", accent=True)
                    for hint in result.api_hints:
                        emit(f"    {hint}", accent=True)
                return True, 0
        if args.native != "off":
            platforms = (
                ["PowerShell", "Unix"]
                if args.native == "both"
                else ["PowerShell" if os.name == "nt" else "Unix"]
            )
            for platform in platforms:
                native = equivalent(command, platform)
                if native:
                    emit(f"  ↳ {platform}: {native}", accent=True)
        return True, 0
    except (TerminalError, OSError, ValueError) as error:
        emit(f"Error: {error_message(error)}")
        return True, 1
    except (EOFError, KeyboardInterrupt):
        emit("\nCancelled. Nothing further executed.")
        return True, 130


def main(argv: list[str] | None = None) -> int:
    args = arguments(argv)
    try:
        session = Session(args.cwd, args.safety_root)
    except (TerminalError, OSError, ValueError) as error:
        emit(f"Error: {error_message(error)}")
        return 1
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if args.command is not None:
        return run_line(args.command, session, args, interactive=interactive)[1]
    emit("English Terminal", accent=True)
    emit(
        "Say what you want the terminal to do.\n\n"
        "Try: show files · make folder demo · move into demo\n"
        'Type "help" for all commands.'
    )
    emit(f"Removal safety root: {session.safety.root}\n")
    status = 0
    while True:
        try:
            prompt = (
                f"english [{safe_text(session.cwd.name or str(session.cwd))}]> "
                if interactive
                else ""
            )
            line = input(prompt)
        except EOFError:
            return status
        except KeyboardInterrupt:
            emit("\nGoodbye.")
            return 130
        if not line.strip():
            continue
        keep_running, code = run_line(line, session, args, interactive=interactive)
        status = max(status, code)
        if not keep_running:
            return status
