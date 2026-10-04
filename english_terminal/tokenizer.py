"""Small tokenizer that preserves Windows backslashes, unlike POSIX shlex."""

from .models import ParseError, Token


def tokenize(text: str) -> tuple[Token, ...]:
    tokens = []
    i = 0
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        quote = text[i] if text[i] in "\"'" else None
        if quote:
            i += 1
            start = i
            while i < len(text) and text[i] != quote:
                i += 1
            if i == len(text):
                raise ParseError("Unclosed quote. Wrap paths with spaces in matching quotes.")
            value = text[start:i]
            i += 1
            if i < len(text) and not text[i].isspace():
                raise ParseError("Put a space after a quoted path.")
            if not value:
                raise ParseError("A path cannot be empty.")
            tokens.append(Token(value, True))
        else:
            start = i
            while i < len(text) and not text[i].isspace():
                if text[i] in "\"'":
                    raise ParseError("Quote the entire path, not part of it.")
                i += 1
            tokens.append(Token(text[start:i]))
    return tuple(tokens)
