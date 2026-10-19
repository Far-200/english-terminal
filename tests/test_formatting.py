import contextlib
import ctypes
import io
import os
import unittest
from unittest.mock import Mock, call, patch

from english_terminal.formatting import clear_screen


class ClearScreenTests(unittest.TestCase):
    def test_unsupported_output_has_no_control_codes(self):
        for is_terminal, term in ((False, "xterm"), (True, "dumb")):
            with (
                self.subTest(is_terminal=is_terminal, term=term),
                contextlib.redirect_stdout(io.StringIO()) as output,
                patch("sys.stdout.isatty", return_value=is_terminal),
                patch.dict(os.environ, {"TERM": term}),
            ):
                self.assertFalse(clear_screen())
                self.assertEqual(output.getvalue(), "")

    def test_windows_console_mode(self):
        for get_mode, set_mode in ((True, True), (False, True), (True, False)):
            kernel32 = Mock()

            def read_mode(handle, mode):
                mode._obj.value = 2
                return get_mode

            kernel32.GetConsoleMode.side_effect = read_mode
            kernel32.SetConsoleMode.return_value = set_mode
            runtime = Mock()
            runtime.get_osfhandle.return_value = 123
            with (
                self.subTest(get_mode=get_mode, set_mode=set_mode),
                contextlib.redirect_stdout(io.StringIO()) as output,
                patch("sys.stdout.isatty", return_value=True),
                patch("sys.stdout.fileno", return_value=1),
                patch("english_terminal.formatting.os.name", "nt"),
                patch.dict(os.environ, {"TERM": "xterm"}),
                patch.dict("sys.modules", {"msvcrt": runtime}),
                patch.object(ctypes, "WinDLL", return_value=kernel32, create=True),
            ):
                self.assertEqual(clear_screen(), get_mode and set_mode)
                if get_mode and set_mode:
                    self.assertEqual(output.getvalue(), "\033[2J\033[3J\033[H")
                    self.assertEqual(
                        kernel32.SetConsoleMode.call_args_list, [call(123, 7), call(123, 2)]
                    )
                else:
                    self.assertEqual(output.getvalue(), "")
                    self.assertEqual(kernel32.SetConsoleMode.call_count, int(get_mode))

    def test_windows_mode_restored_on_output_failure(self):
        kernel32 = Mock()
        with (
            patch("sys.stdout.isatty", return_value=True),
            patch("sys.stdout.fileno", return_value=1),
            patch("english_terminal.formatting.os.name", "nt"),
            patch.dict(os.environ, {"TERM": "xterm"}),
            patch.dict("sys.modules", {"msvcrt": Mock()}),
            patch.object(ctypes, "WinDLL", return_value=kernel32, create=True),
            patch("builtins.print", side_effect=OSError("output failed")),
            self.assertRaises(OSError),
        ):
            clear_screen()
        self.assertEqual(kernel32.SetConsoleMode.call_count, 2)
        self.assertEqual(kernel32.SetConsoleMode.call_args.args[1], 0)
