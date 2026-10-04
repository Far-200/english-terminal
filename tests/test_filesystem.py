import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from english_terminal.executor import Session
from english_terminal.models import TerminalError
from english_terminal.parser import parse


class FilesystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.work = self.root / "workspace"
        self.work.mkdir()
        self.session = Session(self.work)

    def run_command(self, text, confirm=None, dry_run=False):
        return self.session.execute(parse(text), confirm, dry_run)

    def test_create_file(self):
        self.run_command('make file "Hello World.txt"')
        self.assertEqual((self.work / "Hello World.txt").read_bytes(), b"")

    def test_create_folder(self):
        self.run_command('make folder "My Project"')
        self.assertTrue((self.work / "My Project").is_dir())

    def test_no_overwrite_create(self):
        (self.work / "a").write_text("important")
        with self.assertRaises(FileExistsError):
            self.run_command("make file a")
        self.assertEqual((self.work / "a").read_text(), "important")

    def test_missing_parent(self):
        with self.assertRaises(FileNotFoundError):
            self.run_command("make file missing/a")

    def test_navigation_keeps_process_cwd(self):
        before = Path.cwd()
        self.run_command("make folder demo")
        self.run_command("move into demo")
        self.assertEqual(self.session.cwd, self.work / "demo")
        self.assertEqual(Path.cwd(), before)
        self.run_command("move out")
        self.run_command("move to .")
        self.assertEqual(self.session.cwd, self.work)

    def test_absolute_navigation(self):
        self.run_command(f'move to "{self.root}"')
        self.assertEqual(self.session.cwd, self.root)

    def test_missing_navigation(self):
        with self.assertRaises(FileNotFoundError):
            self.run_command("move into missing")

    def test_navigate_file(self):
        self.run_command("make file a")
        with self.assertRaises(TerminalError):
            self.run_command("move into a")

    def test_location(self):
        self.assertEqual(self.run_command("where am i").text, str(self.work))

    def test_listing(self):
        self.run_command("make file z.txt")
        self.run_command("make file a.txt")
        self.run_command("make folder demo")
        self.assertEqual(self.run_command("show files").text, "a.txt\nz.txt")
        self.assertEqual(self.run_command("show folders").text, "demo/")

    def test_empty_listing(self):
        self.assertEqual(self.run_command("show files").text, "(empty)")

    def test_read_utf8(self):
        (self.work / "a").write_text("Hello, café!", encoding="utf-8")
        self.assertEqual(self.run_command("show contents of a").text, "Hello, café!")

    def test_read_empty(self):
        self.run_command("make file a")
        self.assertEqual(self.run_command("show contents of a").text, "(empty file)")

    def test_read_binary(self):
        (self.work / "a").write_bytes(b"\xff\x00")
        with self.assertRaises(TerminalError):
            self.run_command("show contents of a")

    def test_read_too_large(self):
        (self.work / "a").write_bytes(b"x" * (1024 * 1024 + 1))
        with self.assertRaisesRegex(TerminalError, "1 MiB"):
            self.run_command("show contents of a")

    def test_read_directory(self):
        with self.assertRaises(TerminalError):
            self.run_command("show contents of .")

    def test_copy(self):
        (self.work / "a").write_bytes(b"payload")
        self.run_command("copy a to b")
        self.assertEqual((self.work / "b").read_bytes(), b"payload")
        self.assertTrue((self.work / "a").exists())

    def test_move(self):
        (self.work / "a").write_text("payload")
        self.run_command("make folder demo")
        self.run_command("move a to demo/b")
        self.assertFalse((self.work / "a").exists())
        self.assertEqual((self.work / "demo/b").read_text(), "payload")

    def test_rename(self):
        self.run_command("make file a")
        self.run_command("rename a to b")
        self.assertFalse((self.work / "a").exists())
        self.assertTrue((self.work / "b").exists())

    @unittest.skipUnless(os.name == "nt", "Windows directory rename")
    def test_rename_folder(self):
        self.run_command("make folder a")
        self.run_command("rename a to b")
        self.assertTrue((self.work / "b").is_dir())

    def test_rename_different_parent(self):
        self.run_command("make file a")
        self.run_command("make folder demo")
        with self.assertRaises(TerminalError):
            self.run_command("rename a to demo/b")

    def test_transfers_never_overwrite(self):
        (self.work / "a").write_text("source")
        (self.work / "b").write_text("destination")
        for verb in ("copy", "move", "rename"):
            with self.subTest(verb=verb), self.assertRaises(FileExistsError):
                self.run_command(f"{verb} a to b")
        self.assertEqual((self.work / "a").read_text(), "source")
        self.assertEqual((self.work / "b").read_text(), "destination")

    def test_copy_directory_refused(self):
        self.run_command("make folder a")
        with self.assertRaises(TerminalError):
            self.run_command("copy a to b")

    def test_permission_error(self):
        with (
            patch("pathlib.Path.mkdir", side_effect=PermissionError),
            self.assertRaises(PermissionError),
        ):
            self.run_command("make folder blocked")

    def test_control_character_path(self):
        with self.assertRaises(TerminalError):
            self.run_command('make file "bad\x00name"')

    @unittest.skipUnless(os.name == "nt", "Windows-specific paths")
    def test_windows_separators(self):
        self.run_command("make folder demo")
        self.run_command(r"make file demo\a")
        self.assertTrue((self.work / "demo/a").is_file())
        self.run_command("move into demo/.")
        self.run_command(r"move to ..\demo")
        self.assertEqual(self.session.cwd, self.work / "demo")

    @unittest.skipUnless(os.name == "nt", "Windows-specific paths")
    def test_windows_unsafe_paths(self):
        for raw in ("NUL", "CON.txt", "a:stream", "C:relative", "file.", "file ", r"\\?\C:\test"):
            with self.subTest(raw=raw), self.assertRaises(TerminalError):
                self.run_command(f'make file "{raw}"')
