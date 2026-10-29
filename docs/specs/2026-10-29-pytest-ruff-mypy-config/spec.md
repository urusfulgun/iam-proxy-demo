# Spec: pytest, ruff and `mypy --strict` configured in `pyproject.toml`

Roadmap: Phase 1, "S: pytest, ruff and `mypy --strict` configured in `pyproject.toml`".

## Goal
One `pyproject.toml` holds the configuration for all three tools, and `uv.lock` pins their
versions. On a clean clone, `uv sync` followed by `uv run pytest`, `uv run ruff check`,
`uv run ruff format --check` and `uv run mypy` runs with no extra flags, gives the same
result as CI will, and is clean.

## Current state
- `pyproject.toml` has no `[tool.*]` tables. The `dev` group has only pytest 9.2 and httpx2 2.16.0.
- ruff 0.17.3 and mypy 2.4.1 are installed only as global uv tools by the devcontainer.
  `uv run ruff`/`uv run mypy` fall through to those tools. The global mypy can't import the
  venv packages and reports `import-not-found` (see the previous spec's build notes).
- Code: `src/iam_proxy_demo/{__init__,app}.py` and `tests/test_health.py`.
- There is no Makefile, `docker-compose.yml`, realm file or `.env.example` yet.

## Decisions
- **Tools are pinned in the dev group:** `ruff>=0.17,<0.18` and `mypy>=2.4,<2.5`. `uv run` then
  uses the venv binaries, so mypy sees fastapi/starlette/pydantic without needing
  `python_executable`. The global devcontainer tools stay for editor use, but the
  commands in CLAUDE.md go through `uv run`.
- **pytest uses native `[tool.pytest]`** (pytest 9 TOML table, not `ini_options`):
  `testpaths = ["tests"]`, `strict = true` (strict config, markers, xfail and parametrize
  ids), `filterwarnings = ["error"]`. A new deprecation, like the httpx one Starlette raised,
  fails the run as soon as it appears.
- **mypy:** `strict = true`, `files = ["src", "tests"]`, `python_version = "3.14"`, so
  plain `uv run mypy` checks the whole repo. There is no pydantic plugin yet, because there
  are no models.
- **ruff:** the default line length (88) and the target version inferred from
  `requires-python`. `[tool.ruff.lint] select = ["E", "F", "W", "I", "B", "UP", "SIM", "S"]`.
  `per-file-ignores` allows `S101` (assert) under `tests/**`. `[tool.ruff.format]` uses the
  defaults.
- **The S104 finding on `host="0.0.0.0"` in `main()` is intended:** the compose `app` service
  has to accept connections from other containers. It gets an inline `# noqa: S104` with a
  short reason, not a global ignore.

## Scope
- `pyproject.toml`: the dev group gains ruff and mypy; new `[tool.pytest]`, `[tool.mypy]`,
  `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.lint.per-file-ignores]`
- `uv.lock`: regenerated with `uv lock`
- `src/`, `tests/`: only the fixes the new rules require (expected: the S104 noqa, and
  possibly import order)
- `CLAUDE.md` Commands: `uv run ruff format`, `uv run mypy` (config supplies `--strict`
  and the paths)
- `docs/product/tech-stack.md`: the linting section says ruff and mypy are pinned in the dev group

## Non-goals
- CI workflow and pip-audit (next roadmap item)
- pytest-cov, a coverage threshold, an `e2e` marker (added with the first e2e test)
- pre-commit hooks
- Changing the devcontainer's global tool installs or VS Code settings

## Acceptance criteria
1. `uv sync` installs ruff 0.17.x and mypy 2.4.x into `.venv`, and `uv.lock` pins both.
   `uv run which ruff mypy` resolves to `.venv/bin`.
2. `uv run pytest` (no args) collects only `tests/` and passes. The existing negative test
   `test_health_rejects_post` still passes.
3. Strictness is real (negative checks, which are not committed):
   - a test that emits `warnings.warn("x", DeprecationWarning)` fails the run
   - `@pytest.mark.unknown` fails with "not found in `markers`"
   - a typo'd key in `[tool.pytest]` fails with `--strict-config`
   - an untyped `def f(x): return x` in `src/` makes `uv run mypy` fail
   - `import os` left unused, or `assert` in `src/`, makes `uv run ruff check` fail
4. `uv run ruff check`, `uv run ruff format --check` and `uv run mypy` are all clean on the repo.

## Realm settings and mappers changed
None.

## New `.env` variables
None.

## Spec references
None apply. This is tooling config with no SAML2 Core, OIDC Core or RFC 7636 check.
