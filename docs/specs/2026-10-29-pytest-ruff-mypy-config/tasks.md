# Tasks: pytest, ruff and `mypy --strict` configured in `pyproject.toml`

Spec: [spec.md](spec.md)

- [x] 1. Add `ruff>=0.17,<0.18` and `mypy>=2.4,<2.5` to the `dev` group. Run `uv lock && uv sync`
      and check that `uv run which ruff mypy` points into `.venv/bin` (AC 1).
- [x] 2. Add `[tool.pytest]` (`testpaths`, `strict = true`, `filterwarnings = ["error"]`).
      `uv run pytest` passes. Then add a throwaway test that emits a `DeprecationWarning`,
      confirm the run fails, and delete it. Do the same with an unknown marker (AC 2, AC 3).
- [x] 3. Add `[tool.mypy]` (`strict`, `files`, `python_version`). `uv run mypy` is clean. Then
      add a throwaway untyped function in `src/`, confirm mypy fails, and remove it (AC 3, AC 4).
- [x] 4. Add `[tool.ruff.lint]` with the curated `select` and the `tests/**` S101 ignore. Run
      `uv run ruff check` and fix the findings: `# noqa: S104` with a reason on the `0.0.0.0` bind
      in `src/iam_proxy_demo/__init__.py`. Check that an `assert` in `src/` is still flagged
      (AC 3, AC 4).
- [x] 5. `uv run ruff format --check` is clean (AC 4).
- [x] 6. Update the CLAUDE.md Commands section (`uv run ruff format`, `uv run mypy`) and the
      linting section in `docs/product/tech-stack.md`. Tick the item in `docs/product/roadmap.md`.

This item has no access check, so it needs no passing/negative test pair beyond the
strictness checks in AC 3. It has no support drill, so it needs no runbook task.

## Notes from the build
- Every AC 3 negative check failed as expected and was then reverted: `DeprecationWarning`
  (test failed), `@pytest.mark.unknown` (collection error), `testpathz` key
  ("Unknown config option"), untyped `def f(x)` (`no-untyped-def`), and an unused `import os`
  plus an `assert` in `src/` (F401, I001, S101).
- The S104 noqa comment first ran past 88 columns, and E501 caught it. The reason now sits on
  its own line above the call.
- `ruff format --check` reports 14 files because ruff 0.17 also formats Python code blocks in
  Markdown. `ruff check` covers only the three `.py` files.
- No Keycloak, `.env` or runbook changes, so `make reset` and the e2e login (build-spec step 4)
  don't apply yet: there is no stack or `/api/*` route.
