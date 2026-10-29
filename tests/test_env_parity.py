"""`.env.example` parity (docs/specs/2026-10-29-env-example-parity).

Messages name variables only: `.env` holds secrets, so no value is ever printed.
"""

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / ".env.example"

_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# Compose: ${NAME}, ${NAME:?msg}, ${NAME:-default}, ... but not the $${...} escape.
_COMPOSE_REF = re.compile(r"(?<!\$)\$\{(" + _KEY.pattern + ")")
# keycloak-config-cli: $(env:NAME) and $(env:NAME:-default).
_CONFIG_CLI_REF = re.compile(r"\$\(env:(" + _KEY.pattern + ")")


def env_keys(text: str) -> list[str]:
    """Names from `NAME=value` lines; blank lines and `#` comments are skipped."""
    keys: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, sep, _ = stripped.partition("=")
        if not sep or not _KEY.fullmatch(name):
            raise ValueError(f"line {number} is not NAME=value")
        if name in keys:
            raise ValueError(f"duplicate key {name}")
        keys.append(name)
    return keys


def referenced_vars(text: str) -> set[str]:
    return set(_COMPOSE_REF.findall(text)) | set(_CONFIG_CLI_REF.findall(text))


def drift(documented: set[str], other: set[str], where: str) -> str:
    """Empty if `.env.example` and `where` list the same names, else names each side."""
    lines = []
    if missing := sorted(other - documented):
        lines.append(f"in {where} but not in .env.example: {', '.join(missing)}")
    if extra := sorted(documented - other):
        lines.append(f"in .env.example but not in {where}: {', '.join(extra)}")
    return "\n".join(lines)


def git(*args: str) -> int:
    # Fixed arguments, no shell; `git` from PATH as in CI.
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True).returncode  # noqa: S603, S607


def test_env_keys_skips_blanks_and_comments() -> None:
    assert env_keys("# note\n\nA=1\n  B=\n") == ["A", "B"]


def test_env_keys_rejects_duplicate() -> None:
    with pytest.raises(ValueError, match="duplicate key A"):
        env_keys("A=1\nA=2\n")


def test_env_keys_rejects_line_without_equals() -> None:
    with pytest.raises(ValueError, match="line 2"):
        env_keys("A=1\nexport B\n")


def test_env_keys_error_hides_value() -> None:
    with pytest.raises(ValueError) as excinfo:
        env_keys("A=s3cret\nA=s3cret\n")
    assert "s3cret" not in str(excinfo.value)


def test_referenced_vars_compose_forms() -> None:
    text = "${A} ${B:?set} ${C:-x} ${D?msg} ${E-x}"
    assert referenced_vars(text) == {"A", "B", "C", "D", "E"}


def test_referenced_vars_config_cli_forms() -> None:
    assert referenced_vars("$(env:A) $(env:B:-x)") == {"A", "B"}


def test_referenced_vars_ignores_escape_and_bare_form() -> None:
    assert referenced_vars("$${A} $B $(B) plain") == set()


def test_drift_none_when_equal() -> None:
    assert drift({"A"}, {"A"}, "config") == ""


def test_drift_reports_used_but_undocumented() -> None:
    assert drift({"A"}, {"A", "B"}, "config") == "in config but not in .env.example: B"


def test_drift_reports_documented_but_unused() -> None:
    assert drift({"A", "B"}, {"A"}, "config") == "in .env.example but not in config: B"


def test_drift_reports_local_env_missing_and_extra_key() -> None:
    assert drift({"A", "B"}, {"A", "C"}, ".env") == (
        "in .env but not in .env.example: C\nin .env.example but not in .env: B"
    )


def test_env_example_matches_referenced_vars() -> None:
    sources = [
        ROOT / "docker-compose.yml",
        *sorted((ROOT / "keycloak/realms").glob("*.json")),
    ]
    used = set().union(*(referenced_vars(path.read_text()) for path in sources))
    assert used, "no references found; did a source file move?"
    message = drift(
        set(env_keys(EXAMPLE.read_text())),
        used,
        "docker-compose.yml or keycloak/realms",
    )
    assert not message, message


def test_env_example_has_no_duplicates() -> None:
    keys = env_keys(EXAMPLE.read_text())
    assert len(keys) == len(set(keys))


def test_env_is_ignored_and_untracked() -> None:
    # Tracked first: check-ignore never reports a tracked file as ignored.
    assert git("ls-files", "--error-unmatch", ".env") != 0, ".env is tracked"
    assert git("check-ignore", "-q", ".env") == 0, ".env is not git-ignored"
    assert git("ls-files", "--error-unmatch", ".env.example") == 0, (
        ".env.example is untracked"
    )


def test_local_env_matches_env_example() -> None:
    env = ROOT / ".env"
    if not env.exists():
        pytest.skip("no .env (CI)")
    local = set(env_keys(env.read_text()))
    message = drift(set(env_keys(EXAMPLE.read_text())), local, ".env")
    assert not message, message
