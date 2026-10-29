# Tasks: docker-compose stack and Makefile

Spec: [spec.md](spec.md)

- [ ] 1. **Gate:** add `--add-host=auth.localhost:host-gateway` to `runArgs` in
      `.devcontainer/devcontainer.json`. Ask the user to rebuild the devcontainer, then check
      that `getent hosts auth.localhost` returns the host-gateway IP (AC 1). If it still
      returns loopback, stop and report: the hostname decision has to be revisited.
- [ ] 2. Add `.env.example` (three variables), `export/` to `.gitignore`, and `.dockerignore`.
      Check that `git check-ignore .env export/x` matches both and that `.env.example` is tracked.
- [ ] 3. Add the three realm stubs and `keycloak/Dockerfile`. Check that
      `docker build keycloak` succeeds.
- [ ] 4. Add the root `Dockerfile`. Check that `docker build .` succeeds, that
      `docker run` on the image serves `/health`, and that the image has no `.env` (AC 12).
- [ ] 5. Write `docker-compose.yml`. First check `docker compose config` with a filled `.env`,
      then the negative case without `POSTGRES_PASSWORD` (AC 10).
- [ ] 6. Write the Makefile (`help`, `init`, `up`, `down`, `logs`). Run `make init` from a
      state with no `.env` and no volumes. Check AC 2, AC 3, AC 5 and AC 9.
- [ ] 7. Check the issuer from the host, the devcontainer and the app container (AC 4).
- [ ] 8. Add `make apply`. Check it with the `displayName` change, then the negative case
      with invalid JSON (AC 6), and revert both.
- [ ] 9. Add `make export`. Check the three files and that git ignores them (AC 7).
- [ ] 10. Add `make reset`. Create a realm by hand, run reset, check the realm is gone and
       `.env` is unchanged, and AC 2 passes (AC 8).
- [ ] 11. Negative: stop postgres before keycloak starts, and check that keycloak-config
       never runs and `make up` fails (AC 11).
- [ ] 12. Update `docs/product/tech-stack.md` (host-gateway instead of the alias, the RFC 6761
       reason, the baked config image). Tick both items in `docs/product/roadmap.md`.
       Run `uv run pytest`, `ruff check`, `ruff format --check` and `mypy` (AC 13).

This item has no API access check, so it needs no passing/negative test pair. The negative
infrastructure checks are AC 6, 10, 11 and 12. It has no support drill, so it needs no
runbook task. The issuer-mismatch drill (`keycloak:8080` vs `auth.localhost`) is Phase 4 and
builds on AC 4.
