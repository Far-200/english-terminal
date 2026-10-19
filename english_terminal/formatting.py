"""Safe plain-text rendering, with optional restrained ANSI styling."""

import os
import sys


def clear_screen() -> bool:
    """Clear a capable terminal, without sending control codes to redirected output."""
    if not sys.stdout.isatty() or os.environ.get("TERM") == "dumb":
        return False
    sequence = "\033[2J\033[3J\033[H"
    if os.name != "nt":
        print(sequence, end="", flush=True)
        return True

    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetConsoleMode.restype = wintypes.BOOL
    kernel32.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.SetConsoleMode.restype = wintypes.BOOL
    try:
        handle = msvcrt.get_osfhandle(sys.stdout.fileno())
    except (OSError, ValueError):
        return False
    mode = wintypes.DWORD()
    if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        return False
    # ENABLE_PROCESSED_OUTPUT | ENABLE_VIRTUAL_TERMINAL_PROCESSING
    if not kernel32.SetConsoleMode(handle, mode.value | 0x0001 | 0x0004):
        return False
    try:
        print(sequence, end="", flush=True)
    finally:
        kernel32.SetConsoleMode(handle, mode.value)
    return True


def safe_text(text: str) -> str:
    return "".join(c if (c in "\n\t" or c.isprintable()) else f"\\u{ord(c):04x}" for c in text)


def emit(text: str = "", *, accent: bool = False) -> None:
    text = safe_text(text)
    if (
        accent
        and sys.stdout.isatty()
        and "NO_COLOR" not in os.environ
        and os.environ.get("TERM") != "dumb"
    ):
        text = f"\033[36m{text}\033[0m"
    encoding = sys.stdout.encoding or "utf-8"
    print(text.encode(encoding, errors="backslashreplace").decode(encoding))


def error_message(error: Exception) -> str:
    if isinstance(error, FileExistsError):
        return "The destination already exists. Choose a new name; nothing is overwritten."
    if isinstance(error, FileNotFoundError):
        return "That path does not exist. Check its name and parent directory."
    if isinstance(error, PermissionError):
        return "Permission denied. Choose a location you can access."
    if isinstance(error, NotADirectoryError):
        return "A path component is not a directory."
    if isinstance(error, IsADirectoryError):
        return "That path is a directory; this operation needs a file."
    if isinstance(error, OSError):
        return f"Filesystem operation failed: {error.strerror or str(error)}"
    return str(error)
