"""Shared structured command and result types."""

from dataclasses import dataclass
from enum import Enum, auto


class Action(Enum):
    HELP = auto()
    EXIT = auto()
    LOCATION = auto()
    FILES = auto()
    FOLDERS = auto()
    CREATE_FOLDER = auto()
    CREATE_FILE = auto()
    ENTER = auto()
    UP = auto()
    READ = auto()
    COPY = auto()
    MOVE = auto()
    RENAME = auto()
    REMOVE_FILE = auto()
    REMOVE_FOLDER = auto()
    CLEAR = auto()
    GITHUB_REPOS = auto()
    GITHUB_ISSUES = auto()
    GITHUB_RELEASE = auto()
    GITHUB_MY_REPOS = auto()


@dataclass(frozen=True)
class Token:
    value: str
    quoted: bool = False


@dataclass(frozen=True)
class Command:
    action: Action
    args: tuple[str, ...] = ()


class TerminalError(Exception):
    """An expected, user-facing error."""


class ParseError(TerminalError):
    pass


@dataclass(frozen=True)
class Result:
    text: str
    teach: bool = True
    api_hints: tuple[str, ...] = ()
