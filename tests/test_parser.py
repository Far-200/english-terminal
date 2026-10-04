import unittest

from english_terminal.models import Action, ParseError, Token
from english_terminal.parser import parse, suggestions
from english_terminal.registry import DEFINITIONS, help_text
from english_terminal.tokenizer import tokenize


class TokenizerTests(unittest.TestCase):
    def test_whitespace(self):
        self.assertEqual(tokenize("  show\tfiles  "), (Token("show"), Token("files")))

    def test_double_quotes(self):
        self.assertEqual(tokenize('make folder "My Project"')[-1], Token("My Project", True))

    def test_single_quotes(self):
        self.assertEqual(tokenize("make file 'hello world.txt'")[-1].value, "hello world.txt")

    def test_windows_backslashes(self):
        self.assertEqual(tokenize(r'move to "C:\Users\My Name\"')[-1].value, "C:\\Users\\My Name\\")

    def test_apostrophe_inside_double_quotes(self):
        self.assertEqual(tokenize('"Farhaan\'s work"')[0].value, "Farhaan's work")

    def test_errors(self):
        for text in ('"unfinished', "'unfinished", '""', '"foo"bar', 'foo"bar"'):
            with self.subTest(text=text), self.assertRaises(ParseError):
                tokenize(text)

    def test_empty(self):
        self.assertEqual(tokenize(" \t"), ())


class ParserTests(unittest.TestCase):
    def test_every_registered_pattern(self):
        for definition in DEFINITIONS:
            text = definition.pattern
            for placeholder in ("<path>", "<file>", "<source>", "<destination>"):
                text = text.replace(placeholder, '"Mixed Case"')
            text = text.replace("<username>", "octocat")
            text = text.replace("<owner>/<repository>", "octocat/Hello-World")
            with self.subTest(text=text):
                self.assertEqual(parse(text).action, definition.action)

    def test_case_preservation(self):
        command = parse('MAKE Folder "My Project"')
        self.assertEqual(command.args, ("My Project",))

    def test_to_inside_path(self):
        self.assertEqual(parse('copy "road to home" to "to"').args, ("road to home", "to"))

    def test_move_disambiguation(self):
        self.assertEqual(parse("move into demo").action, Action.ENTER)
        self.assertEqual(parse("move a to b").action, Action.MOVE)
        self.assertEqual(parse("move out").action, Action.UP)

    def test_invalid_syntax(self):
        for text in (
            "",
            "make folder",
            "make folder a b",
            "copy a b",
            "move out now",
            '"where am i"',
            "show files | rm",
            "remove everything",
            'move a "to" b',
        ):
            with self.subTest(text=text), self.assertRaises(ParseError):
                parse(text)

    def test_typo_suggests_grammar(self):
        self.assertIn("show files", suggestions("shwo files"))
        known = {d.pattern for d in DEFINITIONS}
        self.assertTrue(set(suggestions("yeet folder homework")) <= known)

    def test_unknown_is_not_executed(self):
        with self.assertRaisesRegex(ParseError, "I don't understand"):
            parse("shwo files")

    def test_help_topic(self):
        self.assertEqual(parse("help make folder").args, ("make folder",))
        self.assertIn("Create one new directory", help_text("make folder"))

    def test_help_unknown_topic(self):
        self.assertIn("No command help", help_text("spaceship"))

    def test_unix_and_windows_path_tokens(self):
        for raw in (
            r"C:\Users\Farhaan\Projects",
            "/tmp/Hello",
            r"..\demo",
            "../demo",
            r"\\server\share\demo",
        ):
            with self.subTest(raw=raw):
                self.assertEqual(parse(f"move to {raw}").args, (raw,))
