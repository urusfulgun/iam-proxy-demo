"""One `.env` parser for all tests (docs/specs/2026-10-29-realm-keypairs).

Errors name a line number or key, never a value: `.env` holds secrets.
"""

import re

KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def parse_env(text: str) -> dict[str, str]:
    """`NAME=value` lines in order; blank lines and `#` comments are skipped."""
    env: dict[str, str] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, sep, value = stripped.partition("=")
        if not sep or not KEY.fullmatch(name):
            raise ValueError(f"line {number} is not NAME=value")
        if name in env:
            raise ValueError(f"duplicate key {name}")
        env[name] = value
    return env
