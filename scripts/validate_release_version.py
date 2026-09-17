"""Validate a release version against paginated GitHub releases JSON."""

import argparse
import json
import re
from pathlib import Path

VERSION_PATTERN = re.compile(r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


def parse_version(value: str) -> tuple[int, int, int] | None:
    match = VERSION_PATTERN.fullmatch(value)
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def validate_version(version: str, releases: list[dict]) -> None:
    requested = parse_version(version)
    if requested is None:
        raise ValueError("Version must have the form 0.1.0 or v0.1.0.")
    published = [
        parsed
        for release in releases
        if not release["draft"]
        and (parsed := parse_version(release["tag_name"])) is not None
    ]
    latest = max(published, default=(0, 0, 0))
    major, minor, patch = latest
    allowed = [(major + 1, 0, 0), (major, minor + 1, 0), (major, minor, patch + 1)]
    if requested not in allowed:
        baseline = ".".join(map(str, latest))
        choices = ", ".join("v" + ".".join(map(str, item)) for item in allowed)
        raise ValueError(f"Version must be one increment from v{baseline}; allowed: {choices}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("releases", type=Path, help="Output of gh api --paginate --slurp")
    args = parser.parse_args()
    pages = json.loads(args.releases.read_text(encoding="utf-8"))
    try:
        validate_version(args.version, [release for page in pages for release in page])
    except ValueError as error:
        parser.exit(1, f"::error::{error}\n")


if __name__ == "__main__":
    main()
