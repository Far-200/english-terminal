import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from english_terminal.models import TerminalError
from english_terminal.safety import SafetyPolicy

from . import test_filesystem


class SafetyTests(unittest.TestCase):
    setUp = test_filesystem.FilesystemTests.setUp
    run_command = test_filesystem.FilesystemTests.run_command

    def test_remove_file_confirmed(self):
        self.run_command("make file a")
        result = self.run_command("remove file a", lambda _: "remove it")
        self.assertTrue(result.teach)
        self.assertFalse((self.work / "a").exists())

    def test_exact_confirmation(self):
        self.run_command("make file a")
        for response in ("yes", "y", "", "REMOVE IT", "remove it "):
            with self.subTest(response=response):
                result = self.run_command("remove file a", lambda _, r=response: r)
                self.assertFalse(result.teach)
                self.assertTrue((self.work / "a").exists())

    def test_no_confirmation_provider(self):
        self.run_command("make file a")
        with self.assertRaisesRegex(TerminalError, "interactive"):
            self.run_command("remove file a")
        self.assertTrue((self.work / "a").exists())

    def test_recursive_preview(self):
        self.run_command("make folder demo")
        self.run_command("make folder demo/nested")
        self.run_command("make file demo/a")
        self.run_command("make file demo/nested/b")
        prompts = []

        def confirm(prompt):
            prompts.append(prompt)
            return "remove it"

        self.run_command("remove folder demo", confirm)
        self.assertIn("2 files", prompts[0])
        self.assertIn("1 folders", prompts[0])
        self.assertFalse((self.work / "demo").exists())

    def test_dry_run(self):
        self.run_command("make folder demo")
        result = self.run_command("remove folder demo", dry_run=True)
        self.assertIn("Dry run", result.text)
        self.assertTrue((self.work / "demo").exists())

    def test_non_removal_dry_run_refused(self):
        with self.assertRaises(TerminalError):
            self.run_command("make file a", dry_run=True)
        self.assertFalse((self.work / "a").exists())

    def test_safety_root_protected(self):
        with self.assertRaisesRegex(TerminalError, "safety root"):
            self.run_command("remove folder .", lambda _: "remove it")

    def test_outside_safety_root(self):
        (self.root / "outside").write_text("keep")
        with self.assertRaises(TerminalError):
            self.run_command("remove file ../outside", lambda _: "remove it")
        self.assertEqual((self.root / "outside").read_text(), "keep")

    def test_drive_root_protected(self):
        with self.assertRaises(TerminalError):
            self.session.safety.validate(Path(self.work.anchor), self.work)

    def test_home_protected(self):
        with patch("pathlib.Path.home", return_value=self.work):
            policy = SafetyPolicy(self.root)
            with self.assertRaises(TerminalError):
                policy.validate(self.work, self.root)

    def test_system_directory_protected(self):
        if os.name == "nt":
            with patch.dict(os.environ, {"SystemRoot": str(self.work)}):
                policy = SafetyPolicy(self.root)
                with self.assertRaises(TerminalError):
                    policy.validate(self.work, self.root)
        else:
            policy = SafetyPolicy(Path("/"))
            with self.assertRaises(TerminalError):
                policy.validate(Path("/etc"), self.work)

    def test_current_directory_protected(self):
        self.run_command("make folder demo")
        self.run_command("move into demo")
        with self.assertRaisesRegex(TerminalError, "Move out"):
            self.run_command("remove folder .", lambda _: "remove it")

    def test_changed_after_preview(self):
        self.run_command("make file a")

        def confirm(_):
            (self.work / "a").write_text("changed")
            return "remove it"

        with self.assertRaisesRegex(TerminalError, "changed"):
            self.run_command("remove file a", confirm)
        self.assertTrue((self.work / "a").exists())

    def test_type_mismatch(self):
        self.run_command("make folder demo")
        self.run_command("make file a")
        for text in ("remove file demo", "remove folder a"):
            with self.subTest(text=text), self.assertRaises(TerminalError):
                self.run_command(text, lambda _: "remove it")

    def test_symlink_refused(self):
        outside = self.root / "outside"
        outside.write_text("keep")
        link = self.work / "link"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("Creating symlinks requires OS privileges")
        for text in ("remove file link", "show contents of link", "copy link to other"):
            with self.subTest(text=text), self.assertRaises(TerminalError):
                self.run_command(text, lambda _: "remove it")
        self.assertEqual(outside.read_text(), "keep")

    @unittest.skipUnless(os.name == "nt", "Windows junction safeguard")
    def test_junction_tree_refused(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "keep").write_text("keep")
        self.run_command("make folder demo")
        link = self.work / "demo/link"
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True
        )
        self.addCleanup(lambda: link.rmdir() if link.exists() else None)
        with self.assertRaisesRegex(TerminalError, "link or junction"):
            self.run_command("remove folder demo", lambda _: "remove it")
        with self.assertRaises(TerminalError):
            self.run_command("move into demo/link")
        self.assertEqual((outside / "keep").read_text(), "keep")
