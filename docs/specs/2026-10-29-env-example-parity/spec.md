# Spec: `.env.example` parity

Roadmap: Phase 1, "S: `.env.example` committed, `.env` git-ignored; CI check that both list the
same variables".

## Goal
CI fails when `.env.example` and the variables the stack actually uses drift apart, or when
`.env` is tracked or not ignored. Locally, `uv run pytest` also fails when an existing `.env`
is missing keys from `.env.example` (or has extra ones). Failure messages name the keys and
never print a value.

## Current state
- `.env.example` is committed and lists `KC_BOOTSTRAP_ADMIN_USERNAME`,
  `KC_BOOTSTRAP_ADMIN_PASSWORD` and `POSTGRES_PASSWORD`.
- `docker-compose.yml` references exactly those three, as `${VAR:?set in .env}`.
- The realm files in `keycloak/realms/` have no `$(env:VAR)` substitutions yet.
- `.gitignore` ignores `.env` (the "Environments" block of the stock Python template).
- The Makefile's `.env` rule copies `.env.example` and fills the two secrets with
  `openssl rand -hex 24`. It never overwrites an existing `.env`, so a variable added to
  `.env.example` later goes missing from a developer's `.env`.
- `.env` doesn't exist in CI, and CI already runs `uv run pytest`.

## Decisions
- **The CI side compares `.env.example` to the referenced variables**, not to `.env`: the keys
  of `.env.example` must equal the union of the variables used in `docker-compose.yml` and
  `keycloak/realms/*.json`. That catches both directions of drift: a variable that is used but
  undocumented, and one that is documented but dead.
- **It is a pytest test**, `tests/test_env_parity.py`, so it runs in the existing CI `Test` step
  with no new workflow step, and its negative tests sit next to it.
- **Small pure helpers in the test module:**
  - `env_keys(text) -> list[str]`: the names from `NAME=value` lines, skipping blank lines and
    `#` comments.
  - `referenced_vars(text) -> set[str]`: compose's braced form `${NAME` (which covers
    `${NAME}`, `${NAME:?msg}`, `${NAME:-default}`, `${NAME?msg}` and `${NAME-default}`),
    ignoring the `$${…}` escape, plus keycloak-config-cli's `$(env:NAME` (including
    `$(env:NAME:-default)`).
- **Tests on the real repo:**
  1. The keys of `.env.example` equal the referenced variables. The failure message lists
     "used but not in .env.example" and "in .env.example but unused" separately.
  2. `.env.example` has no duplicate keys.
  3. `.env` is git-ignored (`git check-ignore -q .env` succeeds) and not tracked
     (`git ls-files --error-unmatch .env` fails), and `.env.example` is tracked. `git` runs via
     `subprocess.run` with list arguments and an inline `# noqa: S603, S607` with a one-line
     reason.
  4. If `.env` exists, its key set equals the key set of `.env.example`, and the message names
     keys only. Otherwise the test calls `pytest.skip("no .env (CI)")`.
- Only the braced `${…}` form counts in compose; that is the repo's convention. Bare `$VAR` is
  not recognised.
- The Makefile's `.env` rule is not a source of references: it only fills in values.

## Scope
- `tests/test_env_parity.py` (new)
- `docs/product/tech-stack.md`: the CI section says pytest also enforces `.env.example` parity
- `docs/product/roadmap.md`: tick the item

## Non-goals
- Merging new keys into an existing `.env` automatically
- Validating values or secret strength
- The realm keypair variables (next roadmap item)
- A separate CI step or a `make check-env` target
- Scanning the Dockerfiles, the Makefile or the devcontainer for variables

## Acceptance criteria
1. `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` and `uv run pytest` pass on
   a clean tree. With a local `.env`, the local-parity test runs; without one, it is skipped.
2. Committed negative unit tests on synthetic input cover each failure path of the helpers:
   - a variable used but not documented, and one documented but unused, are both reported
   - `${VAR:-x}` and `$(env:VAR:-x)` count as references
   - `$${VAR}` does not count
   - a duplicate key is rejected
   - a `.env` missing a key, and one with an extra key, are both detected
3. Manual negative checks (local, reverted), each making `uv run pytest` fail with the variable
   name in the message:
   - add `${FOO:?x}` to `docker-compose.yml`
   - add `BAR=` to `.env.example`
   - add `$(env:BAZ)` to a realm file
   - delete a line from the local `.env`
   - `git add -f .env` (then `git rm --cached .env`)

   None of the failure output contains a secret value.
4. On the PR for this build, the CI `check` job is green, with test 4 shown as skipped.

## Realm settings and mappers changed
None.

## New `.env` variables
None.

## Spec references
None apply. This item has no SAML2 Core, OIDC Core or RFC 7636 check; it enforces the CLAUDE.md
rule "every new variable also goes into `.env.example`".
