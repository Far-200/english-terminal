"""Deterministic matching; suggestions are informational and never executed."""

from difflib import SequenceMatcher

from .github.identifiers import validate
from .models import Action, Command, ParseError
from .registry import DEFINITIONS
from .tokenizer import tokenize


def suggestions(text: str) -> list[str]:
    ranked = []
    for definition in DEFINITIONS:
        if definition.alias:
            continue
        prefix = definition.pattern.split(" <", 1)[0]
        score = SequenceMatcher(None, text.casefold(), prefix).ratio()
        if score >= 0.48:
            ranked.append((score, definition.pattern))
    return [pattern for _, pattern in sorted(ranked, reverse=True)[:3]]


def parse(text: str) -> Command:
    tokens = tokenize(text)
    if not tokens:
        raise ParseError('Enter a command. Type "help" for examples.')
    if tokens[0].value.casefold() == "help" and not tokens[0].quoted:
        return Command(Action.HELP, (" ".join(t.value for t in tokens[1:]),))
    for definition in DEFINITIONS:
        pattern = definition.pattern.split()
        if len(pattern) != len(tokens):
            continue
        args = []
        for part, token in zip(pattern, tokens, strict=True):
            if part.startswith("<"):
                args.append(token.value)
            elif token.quoted or token.value.casefold() != part:
                break
        else:
            validate(definition.action, tuple(args))
            return Command(definition.action, tuple(args))
    hints = suggestions(text)
    message = f'I don\'t understand "{text}".'
    if hints:
        message += "\n\nKnown command patterns:\n  " + "\n  ".join(hints)
    message += '\nType "help" for commands. Quote paths that contain spaces.'
    raise ParseError(message)
