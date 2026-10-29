# Tasks: docker-compose stack and Makefile

Spec: [spec.md](spec.md)

- [x] 1. **Gate:** add `--add-host=auth.localhost:host-gateway` to `runArgs` in
      `.devcontainer/devcontainer.json`. Ask the user to rebuild the devcontainer, then check
      that `getent hosts auth.localhost` returns the host-gateway IP (AC 1). If it still
      returns loopback, stop and report: the hostname decision has to be revisited.
- [x] 2. Add `.env.example` (three variables), `export/` to `.gitignore`, and `.dockerignore`.
      Check that `git check-ignore .env export/x` matches both and that `.env.example` is tracked.
- [x] 3. Add the three realm stubs and `keycloak/Dockerfile`. Check that
      `docker build keycloak` succeeds.
- [x] 4. Add the root `Dockerfile`. Check that `docker build .` succeeds, that
      `docker run` on the image serves `/health`, and that the image has no `.env` (AC 12).
- [x] 5. Write `docker-compose.yml`. First check `docker compose config` with a filled `.env`,
      then the negative case without `POSTGRES_PASSWORD` (AC 10).
- [x] 6. Write the Makefile (`help`, `init`, `up`, `down`, `logs`). Run `make init` from a
      state with no `.env` and no volumes. Check AC 2, AC 3, AC 5 and AC 9.
- [x] 7. Check the issuer from the host, the devcontainer and the app container (AC 4).
- [x] 8. Add `make apply`. Check it with the `displayName` change, then the negative case
      with invalid JSON (AC 6), and revert both.
- [x] 9. Add `make export`. Check the three files and that git ignores them (AC 7).
- [x] 10. Add `make reset`. Create a realm by hand, run reset, check the realm is gone and
       `.env` is unchanged, and AC 2 passes (AC 8).
- [x] 11. Negative: stop postgres before keycloak starts, and check that keycloak-config
       never runs and `make up` fails (AC 11).
- [x] 12. Update `docs/product/tech-stack.md` (host-gateway instead of the alias, the RFC 6761
       reason, the baked config image). Tick both items in `docs/product/roadmap.md`.
       Run `uv run pytest`, `ruff check`, `ruff format --check` and `mypy` (AC 13).

This item has no API access check, so it needs no passing/negative test pair. The negative
infrastructure checks are AC 6, 10, 11 and 12. It has no support drill, so it needs no
runbook task. The issuer-mismatch drill (`keycloak:8080` vs `auth.localhost`) is Phase 4 and
builds on AC 4.

## Notes from the build
- **Task 1 / AC 1:** the `devcontainer.json` change is in, but the in-devcontainer check waits
  for a rebuild, which ends the running session. The mechanism was checked first in
  throwaway containers: `docker run --add-host=auth.localhost:host-gateway` on the
  devcontainer base image (glibc 2.43) and on `python:3.14.8-slim` (glibc 2.41). In both,
  `getaddrinfo` returns only the host-gateway IP; without the entry it returns `::1, 127.0.0.1`.
  `getent hosts` still shows `::1`, because it asks for IPv6 only, so AC 1 now uses
  `getent ahosts`.
- **Host port clash:** the first `make init` failed because VS Code was forwarding
  127.0.0.1:8000 and 127.0.0.1:8080 on the host. The user stopped the forwards, and
  `forwardPorts: [8000]` is removed from `devcontainer.json`, because compose publishes both
  ports itself.
- **AC 4** was checked from the host network namespace (loopback, like the browser), from
  the devcontainer (with `curl --resolve` to the host-gateway IP, until the rebuild) and
  from the app container. All three report `http://auth.localhost:8080/realms/<realm>`.
- **`make export`** failed at first, after "Export finished successfully": the second JVM
  inherits `KC_HEALTH_ENABLED` and tried to bind management port 9000, which the running
  server already holds. Fixed with `--http-management-port=9001`, which is runtime-only and
  doesn't trigger a rebuild. The export also writes `master-realm.json`, which includes the
  admin's password hash. It's git-ignored, and must never be copied into `keycloak/realms/`.
- **keycloak-config-cli doesn't unset missing fields.** After `displayName` was removed from
  `aloysius.json` and `make apply` ran again, the realm kept "Aloysius". Only `make reset`
  (or an explicit value) removes it. This is recorded in tech-stack.md.
- **AC 11** used a throwaway override pointing `KC_DB_URL` at a host that doesn't exist
  (`make up COMPOSE="docker compose -f docker-compose.yml -f broken-db.yml"`), because
  `up` would just restart a stopped postgres. Keycloak exited with code 1, keycloak-config
  and the app stayed `Created` with no logs, and `make up` exited 2.
- **`up --wait`** accepts the one-shot keycloak-config exiting with code 0, so that risk is resolved.
- **Timing:** `make init` and `make reset` each take about 1.5 minutes with warm images (the
  first pull took about 3.5 minutes).
- **build-spec step 4** (alice/carol e2e) doesn't apply yet: there are no users, IdPs or `/api/*` routes.
- **Task 1 (checked after the devcontainer rebuild, during the realm-keypairs build):**
  `getent ahosts auth.localhost` returns only `172.17.0.1` (host-gateway), and httpx2 gets issuer
  `http://auth.localhost:8080/realms/aloysius` from the devcontainer. Plain `curl` still connects
  to loopback, because it resolves `*.localhost` itself and ignores `/etc/hosts`.
