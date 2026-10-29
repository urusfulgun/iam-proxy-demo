# Spec: CI workflow

Roadmap: Phase 1, "S: CI workflow: `uv sync`, ruff, mypy, pytest, pip-audit on `uv.lock`".

## Goal
Every push to `main` and every pull request runs the same checks as the local commands in
CLAUDE.md, against the locked dependencies. The run fails on any lint, format, type, test or
known-vulnerability finding.

## Current state
- There is no `.github/` directory.
- `pyproject.toml` configures pytest, ruff and mypy. `uv.lock` pins ruff 0.17, mypy 2.4,
  pytest 9.2 and httpx2 2.16.0.
- The Dockerfile pins uv 0.13.6, and the devcontainer pins Python 3.14.8 (`UV_PYTHON`).
- `docs/product/tech-stack.md` already fixes the pip-audit command:
  `uv export --format requirements-txt --no-hashes | uvx pip-audit -r - --no-deps`.

## Decisions
- **One workflow, one job:** `.github/workflows/ci.yml`, job `check` on `ubuntu-24.04`, with
  `timeout-minutes: 10`, `permissions: contents: read`, and a `concurrency` group per ref that
  cancels in-progress runs for pull requests.
- **Triggers:** `push` to `main` and `pull_request` (all branches).
- **Actions pinned by full commit SHA** with a `# vX.Y.Z` comment:
  - `actions/checkout` with `persist-credentials: false`
  - `astral-sh/setup-uv` with `version: "0.13.6"` (same as the Dockerfile) and
    `enable-cache: true`

  The SHAs are resolved at build time with `gh api`, from the latest release that is at least
  two weeks old.
- **Dependabot keeps the pins current:** `.github/dependabot.yml` with
  `package-ecosystem: github-actions`, directory `/`, schedule weekly. Dependabot updates the
  SHA and the version comment together.
- **Python:** job-level `UV_PYTHON: "3.14.8"`, the same as the devcontainer. uv downloads it.
- **Steps, in order, one step each** so the failing check is obvious in the log:
  1. `uv sync --locked`: fails if `uv.lock` is out of date with `pyproject.toml`
  2. `uv run ruff check`
  3. `uv run ruff format --check`
  4. `uv run mypy`
  5. `uv run pytest`
  6. `uv export --locked --format requirements-txt --no-hashes --no-emit-project | uvx pip-audit==<X.Y.Z> -r - --no-deps --strict`
- **pip-audit details:**
  - `--no-emit-project` drops the `-e .` line, because the local project isn't on PyPI.
  - `--strict` fails the step if a package can't be audited, instead of skipping it.
  - The dev group stays in the export: httpx2 runs the e2e tests.
  - The exact pip-audit version is pinned at build time.
  - If `-r -` isn't accepted, use `-r /dev/stdin` and update tech-stack.md.

## Scope
- `.github/workflows/ci.yml` (new)
- `.github/dependabot.yml` (new)
- `docs/product/tech-stack.md`: the pip-audit section says actions are pinned by SHA and kept
  current by Dependabot, and gives the exact command if it changed
- `docs/product/roadmap.md`: tick the item

## Non-goals
- The `.env` / `.env.example` parity check (next roadmap item)
- Trivy or building the app image in CI
- Running the compose stack or the e2e tests in CI
- Dependabot for `uv` dependencies
- Branch protection and required checks: a GitHub setting the user makes; the PR description
  mentions it
- An OS or Python version matrix
- A README badge

## Acceptance criteria
1. `.github/workflows/ci.yml` and `.github/dependabot.yml` exist. Every `uses:` is a 40-character
   commit SHA with a version comment.
2. Running each workflow command locally, in order, on a clean tree passes. pip-audit reports no
   known vulnerabilities, or the finding is fixed by a lock bump in this change.
3. Negative checks (local, not committed) each make the matching command exit non-zero:
   - an unused import: `uv run ruff check`
   - a misformatted line: `uv run ruff format --check`
   - an untyped `def` in `src/`: `uv run mypy`
   - a failing assert: `uv run pytest`
   - a dependency added to `pyproject.toml` without `uv lock`: `uv sync --locked`
   - a known-vulnerable pin such as `jinja2==3.1.2`, piped to the same pip-audit invocation
4. On the PR for this build, the `check` job runs on GitHub and is green, with each step shown
   separately in the log.
5. `actionlint` (via its Docker image or release binary) reports no errors on `ci.yml`.

## Realm settings and mappers changed
None.

## New `.env` variables
None.

## Spec references
None apply. This item has no SAML2 Core, OIDC Core or RFC 7636 check; CI is the gate that will
run the tests for those checks.
