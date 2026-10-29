# Tasks: `.env.example` parity

Spec: [spec.md](spec.md)

- [ ] 1. Write `env_keys` and `referenced_vars` in `tests/test_env_parity.py`, with a positive
      and a negative unit test for each path on synthetic input (AC 2).
- [ ] 2. Repo parity test: the keys of `.env.example` equal the references in
      `docker-compose.yml` and `keycloak/realms/*.json`; plus the duplicate-key test (AC 1).
- [ ] 3. Git test: `.env` is ignored and untracked, and `.env.example` is tracked (AC 1).
- [ ] 4. Local `.env` key-set test, skipped without `.env`; its message names keys only
      (AC 1, AC 2).
- [ ] 5. Run `ruff check`, `ruff format --check`, `mypy` and `pytest`, with and without a local
      `.env`: all pass, and test 4 runs or skips accordingly (AC 1).
- [ ] 6. Run the manual negative checks from AC 3 one at a time, reverting each: every one fails
      with the variable name and no secret value (AC 3).
- [ ] 7. Update `docs/product/tech-stack.md` (CI section) and tick the item in
      `docs/product/roadmap.md`.
- [ ] 8. After the push, the PR's `check` run is green, with the local-parity test skipped
      (AC 4).

This item has no access check, so it needs no passing/negative API test pair beyond the negative
checks in AC 2 and AC 3. It has no support drill, so it needs no runbook task.
