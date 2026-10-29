# Tasks: `.env.example` parity

Spec: [spec.md](spec.md)

- [x] 1. Write `env_keys` and `referenced_vars` in `tests/test_env_parity.py`, with a positive
      and a negative unit test for each path on synthetic input (AC 2).
- [x] 2. Repo parity test: the keys of `.env.example` equal the references in
      `docker-compose.yml` and `keycloak/realms/*.json`; plus the duplicate-key test (AC 1).
- [x] 3. Git test: `.env` is ignored and untracked, and `.env.example` is tracked (AC 1).
- [x] 4. Local `.env` key-set test, skipped without `.env`; its message names keys only
      (AC 1, AC 2).
- [x] 5. Run `ruff check`, `ruff format --check`, `mypy` and `pytest`, with and without a local
      `.env`: all pass, and test 4 runs or skips accordingly (AC 1).
- [x] 6. Run the manual negative checks from AC 3 one at a time, reverting each: every one fails
      with the variable name and no secret value (AC 3).
- [x] 7. Update `docs/product/tech-stack.md` (CI section) and tick the item in
      `docs/product/roadmap.md`.
- [x] 8. After the push, the PR's `check` run is green, with the local-parity test skipped
      (AC 4).

This item has no access check, so it needs no passing/negative API test pair beyond the negative
checks in AC 2 and AC 3. It has no support drill, so it needs no runbook task.

## Notes from the build
- The test also has a `drift(documented, other, where)` helper, so the repo and local checks
  share one message format: "in <where> but not in .env.example: X" and
  "in .env.example but not in <where>: Y". This replaces the spec's wording ("used but not
  in…", "…but unused"). `where` is "docker-compose.yml or keycloak/realms" or ".env".
- `env_keys` raises on a duplicate key and on a line that isn't `NAME=value`. Its error names the
  line number or key, never the value (tested).
- `git check-ignore` never reports a tracked file as ignored, so with `.env` force-added the
  first version failed with ".env is not git-ignored". The test now checks "tracked" first, so
  that case says ".env is tracked". Commenting out `.env` in `.gitignore` gives
  ".env is not git-ignored".
- AC 1: 17 passed with a local `.env`; 16 passed and 1 skipped ("no .env (CI)") with it moved
  aside.
- AC 3: all five manual checks exited 1, named the variable (FOO, BAR, BAZ, POSTGRES_PASSWORD) or
  ".env is tracked", and were reverted. A grep of each output for every value in `.env` found
  nothing.
- AC 4: the `check` run on PR #14 was green, with the local-parity test skipped (confirmed by
  the user).
- No Keycloak, `.env` or `/api/*` changes, and the realms aren't wired up yet. So `make reset`
  and the alice/carol e2e login (build-spec step 4) don't apply to this item.
