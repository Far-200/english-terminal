import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from english_terminal.cli import arguments, main, run_line
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

    def test_easter_egg(self):
        for phrase in ("fuck off", "FuCk OfF", "  \tfuck off\t  "):
            with self.subTest(phrase=phrase), tempfile.TemporaryDirectory() as directory:
                result = self.call(
                    "--cwd", directory, input=f"{phrase}\nmake file unexpected.txt\n"
                )
                self.assertEqual(result.returncode, 0)
                self.assertTrue(result.stdout.endswith("You too, weirdo.\n"))
                self.assertEqual(result.stdout.count("You too, weirdo.\n"), 1)
                self.assertEqual(result.stderr, "")
                self.assertFalse((Path(directory) / "unexpected.txt").exists())

    def test_easter_egg_bypasses_command_processing_after_error(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch(
                "builtins.input", side_effect=["invalid command", "fuck off", "show files"]
            ) as read,
            patch("english_terminal.cli.run_line", return_value=(True, 1)) as process,
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(main(["--cwd", directory]), 0)
            process.assert_called_once()
            self.assertEqual(process.call_args.args[0], "invalid command")
            self.assertEqual(read.call_count, 2)
            self.assertTrue(output.getvalue().endswith("You too, weirdo.\n"))

    def test_easter_egg_similar_phrases_use_normal_processing(self):
        for phrase in (
            "fuck",
            "fuck off!",
            "please fuck off",
            "fuck off now",
            "fuck  off",
            "fuck\toff",
        ):
            with (
                self.subTest(phrase=phrase),
                tempfile.TemporaryDirectory() as directory,
                patch("builtins.input", return_value=phrase),
                patch("english_terminal.cli.run_line", return_value=(False, 0)) as process,
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(main(["--cwd", directory]), 0)
                process.assert_called_once()
                self.assertEqual(process.call_args.args[0], phrase)
                self.assertNotIn("You too, weirdo.", output.getvalue())

    def test_cls_reuses_clear_screen_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(Path(directory))
            args = arguments(["--native", "both"])
            for is_terminal in (True, False):
                outputs = []
                for text in ("clear screen", "cls", "CLS", " cls "):
                    with (
                        self.subTest(text=text, is_terminal=is_terminal),
                        contextlib.redirect_stdout(io.StringIO()) as output,
                        patch("sys.stdout.isatty", return_value=is_terminal),
                        patch("english_terminal.formatting.os.name", "posix"),
                        patch.dict(os.environ, {"TERM": "xterm", "NO_COLOR": "1"}),
                        patch.object(session, "execute") as execute,
                    ):
                        self.assertEqual(
                            run_line(text, session, args, interactive=is_terminal), (True, 0)
                        )
                        execute.assert_not_called()
                        outputs.append(output.getvalue())
                for output in outputs:
                    self.assertEqual(output, outputs[0])
                    self.assertIn("PowerShell: Clear-Host", output)
                if is_terminal:
                    self.assertTrue(outputs[0].startswith("\033[2J\033[3J\033[H"))
                else:
                    self.assertNotIn("\033", outputs[0])

    def test_clear_returns_to_repl_prompt(self):
        for command in ("cls", "clear screen"):
            with (
                self.subTest(command=command),
                tempfile.TemporaryDirectory() as directory,
                patch("sys.stdin.isatty", return_value=True),
                contextlib.redirect_stdout(io.StringIO()) as output,
                patch("sys.stdout.isatty", return_value=True),
                patch("builtins.input", side_effect=[command, "quit"]) as read,
                patch("english_terminal.cli.clear_screen", return_value=True) as clear,
            ):
                self.assertEqual(main(["--cwd", directory, "--native", "both"]), 0)
                clear.assert_called_once_with()
                self.assertEqual(read.call_count, 2)
                self.assertTrue(read.call_args.args[0].startswith("english ["))
                self.assertIn("PowerShell: Clear-Host", output.getvalue())

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
