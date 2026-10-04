"""Explicitly opted-in anonymous live check; not part of the offline test suite."""

import argparse
import os

from english_terminal.cli import main


def smoke() -> int:
    parser = argparse.ArgumentParser(description="Anonymous live GitHub smoke test (GET only).")
    parser.add_argument("--live", action="store_true", help="allow public GitHub HTTP requests")
    args = parser.parse_args()
    if not args.live:
        parser.error("pass --live to opt into public network requests")
    os.environ.pop("GITHUB_TOKEN", None)
    failed = False
    for command in (
        "show github repos for octocat",
        "show github issues in python/cpython",
        "show latest github release of cli/cli",
    ):
        print(f"\nenglish> {command}")
        failed |= main([command]) != 0
    print("\nenglish> show my github repos (missing authentication expected)")
    failed |= main(["show my github repos"]) != 1
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(smoke())
