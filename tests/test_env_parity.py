"""`.env.example` parity (docs/specs/2026-10-29-env-example-parity).

Messages name variables only: `.env` holds secrets, so no value is ever printed.
"""

import re
import subprocess
from pathlib import Path

import pytest

from tests.envfile import KEY, parse_env

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / ".env.example"

# Compose: ${NAME}, ${NAME:?msg}, ${NAME:-default}, ... but not the $${...} escape.
_COMPOSE_REF = re.compile(r"(?<!\$)\$\{(" + KEY.pattern + ")")
# keycloak-config-cli: $(env:NAME) and $(env:NAME:-default).
_CONFIG_CLI_REF = re.compile(r"\$\(env:(" + KEY.pattern + ")")


def env_keys(text: str) -> list[str]:
    return list(parse_env(text))


def referenced_vars(text: str) -> set[str]:
    return set(_COMPOSE_REF.findall(text)) | set(_CONFIG_CLI_REF.findall(text))


def realm_vars(text: str) -> set[str]:
    """Realm files: config-cli substitutes only `$(env:…)`; `${…}` is a message key."""
    return set(_CONFIG_CLI_REF.findall(text))


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


def test_realm_vars_ignore_keycloak_message_keys() -> None:
    # `${username}` in a realm file is a Keycloak i18n key, not a variable.
    assert realm_vars('"${username}" "$(env:A)"') == {"A"}


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
    realms = sorted((ROOT / "keycloak/realms").glob("*.json"))
    used = referenced_vars((ROOT / "docker-compose.yml").read_text()).union(
        *(realm_vars(path.read_text()) for path in realms)
    )
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


def test_local_env_matches_env_example(dotenv: dict[str, str]) -> None:
    local = set(dotenv)
    message = drift(set(env_keys(EXAMPLE.read_text())), local, ".env")
    assert not message, message
