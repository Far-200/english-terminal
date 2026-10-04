import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from english_terminal.cli import arguments, run_line
from english_terminal.executor import Session
from english_terminal.formatting import error_message, safe_text
from english_terminal.native import equivalent
from english_terminal.parser import parse


class CliTests(unittest.TestCase):
    def call(self, *args, input=None):
        return subprocess.run(
            [sys.executable, "-m", "english_terminal", *args],
            input=input,
            text=True,
            capture_output=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )

    def test_version(self):
        result = self.call("--version")
        self.assertEqual(result.returncode, 0)
        self.assertIn("0.2.0", result.stdout)

    def test_cli_help(self):
        self.assertIn("--safety-root", self.call("--help").stdout)

    def test_one_shot(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.call("--cwd", directory, "where am i", "--native", "both")
            self.assertEqual(result.returncode, 0)
            self.assertIn("PowerShell: Get-Location", result.stdout)
            self.assertIn("Unix: pwd", result.stdout)

    def test_error_status(self):
        result = self.call("make folder")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr + result.stdout)

    def test_piped_confirmation_cannot_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "a"
            path.touch()
            result = self.call("--cwd", directory, "remove file a", input="remove it\n")
            self.assertEqual(result.returncode, 1)
            self.assertTrue(path.exists())

    def test_scripted_repl(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.call(
                "--cwd",
                directory,
                "--native",
                "off",
                input=(
                    "make folder demo\nmove into demo\nmake file hello.txt\n"
                    "show files\nshow contents of hello.txt\nmove out\nquit\n"
                ),
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("hello.txt", result.stdout)
            self.assertIn("(empty file)", result.stdout)

    def test_interactive_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(Path(directory))
            (Path(directory) / "a").touch()
            output = io.StringIO()
            with (
                patch("builtins.input", return_value="remove it"),
                contextlib.redirect_stdout(output),
            ):
                _, status = run_line("remove file a", session, arguments([]), interactive=True)
            self.assertEqual(status, 0)
            self.assertFalse((Path(directory) / "a").exists())
            self.assertIn("permanently remove", output.getvalue())

    def test_confirmation_eof_cancels(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(Path(directory))
            (Path(directory) / "a").touch()
            with (
                patch("builtins.input", side_effect=EOFError),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                _, status = run_line("remove file a", session, arguments([]), interactive=True)
            self.assertEqual(status, 130)
            self.assertTrue((Path(directory) / "a").exists())

    def test_native_quote_safety(self):
        command = parse('make file "a\'b;$(whoami).txt"')
        self.assertIn("'a''b;$(whoami).txt'", equivalent(command, "PowerShell"))
        self.assertIn("'\"'\"'", equivalent(command, "Unix"))

    def test_terminal_escape_neutralized(self):
        self.assertEqual(safe_text("\x1b[31mred"), "\\u001b[31mred")

    def test_friendly_errors(self):
        for error in (
            PermissionError(),
            FileExistsError(),
            FileNotFoundError(),
            IsADirectoryError(),
            NotADirectoryError(),
            OSError("failure"),
        ):
            self.assertTrue(error_message(error))
