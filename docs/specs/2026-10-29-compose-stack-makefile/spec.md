# Spec: docker-compose stack and Makefile

Roadmap: Phase 1, two items in one spec, so every Makefile target is tested against a real stack:
- "M: `docker-compose.yml`: postgres, keycloak (alias `auth.localhost`, bootstrap admin from
  `.env`, healthcheck on `:9000/health/ready`), one-shot keycloak-config, app"
- "S: Makefile targets `init`, `apply`, `reset`, `export`, `up`, `down`, `logs`"

## Goal
From a clean clone, `make init` creates `.env` with random secrets and starts postgres,
keycloak, keycloak-config and the app. It returns once Keycloak is ready and keycloak-config
has applied three stub realms. After that:
- `http://auth.localhost:8080` opens the same Keycloak from the host browser, the app
  container and the devcontainer
- `make apply`, `make export`, `make logs`, `make down` and `make reset` each do one thing
  and can be checked

## Current state
- There is no `docker-compose.yml`, Makefile, `.env.example`, Dockerfile or `keycloak/` directory yet.
- The app is `src/iam_proxy_demo/` with `GET /health`. `main()` runs uvicorn on `0.0.0.0:8000`.
- `.gitignore` already ignores `.env`.
- Docker runs outside the devcontainer (docker-outside-of-docker, Docker 28.3, Compose v5.6).
  The devcontainer sits on the external network `iam-proxy-demo-network`, and the repo is at
  a different path on the host than in the devcontainer.
- glibc 2.43 in the devcontainer resolves `auth.localhost` to loopback without asking DNS
  (`getent hosts auth.localhost` gives `::1`), as RFC 6761 §6.3 allows for `.localhost`.

## Decisions
- **One hostname, through the host:** Keycloak publishes `8080:8080` on the host, and
  `KC_HOSTNAME=http://auth.localhost:8080`.
  - The app container gets `extra_hosts: ["auth.localhost:host-gateway"]`.
  - The devcontainer gets `--add-host=auth.localhost:host-gateway` in `runArgs`.
  - The browser resolves `auth.localhost` to loopback on the host, where 8080 is published.
  - So all three see the same URL, and `iss` matches (OIDC Core §3.1.3.7, step 2).
  - This replaces the network alias in tech-stack.md, which glibc's `.localhost` shortcut
    defeats. The `/etc/hosts` entry from `--add-host`/`extra_hosts` must win over that
    shortcut. Task 1 checks this first, before anything else is built on it.
- **Realm files are baked into an image:** `keycloak/Dockerfile` is
  `FROM adorsys/keycloak-config-cli:6.5.1-26.5.5` with `COPY realms/ /config/`.
  `make apply` runs `docker compose run --rm --build keycloak-config`. A bind mount won't
  work here because the Docker daemon resolves paths on the host. The build context is sent
  from the client, so this works from the devcontainer and in CI.
- **Three bare realm stubs:** `keycloak/realms/{home-fau,home-bamberg,aloysius}.json` with
  only `realm` and `enabled: true`. The next roadmap item fills them in.
- **`make init` generates secrets:** if `.env` is missing, it copies `.env.example` and fills
  `KC_BOOTSTRAP_ADMIN_PASSWORD` and `POSTGRES_PASSWORD` with `openssl rand -hex 24`. It never
  overwrites an existing `.env`, so secrets (and the keypairs added later) survive `make reset`.
- **Compose fails loudly on missing secrets:** they are interpolated as `${VAR:?set in .env}`.
- **App image:** a root `Dockerfile` built on `python:3.14.8-slim`, with uv copied from
  `ghcr.io/astral-sh/uv:0.13.6`.
  - Dependencies are installed with `uv sync --locked --no-dev` in two layers (dependencies
    first, then the project), and the process runs as a non-root user.
  - The healthcheck uses `python -c` with urllib on `/health`, because the image has no curl.
  - `.dockerignore` keeps out `.env`, `.venv`, `.git` and `export/`.
- **Startup order:** keycloak-config waits for keycloak `service_healthy`. The app waits for
  keycloak-config `service_completed_successfully`, so `docker compose up -d --wait`
  returns only after the realms are applied.
- **Export:** `make export` runs
  `docker compose exec keycloak /opt/keycloak/bin/kc.sh export --dir /tmp/export --users realm_file`,
  then `docker compose cp keycloak:/tmp/export ./export`. `export/` is git-ignored. Copying
  into `keycloak/realms/`, and stripping the IdP `types` field, stays a manual step, as
  CLAUDE.md says.
- **Only what's needed is published:** host ports 8080 (Keycloak) and 8000 (app). Postgres
  5432 and the Keycloak management port 9000 stay internal.

## Scope
- `docker-compose.yml`
  - `postgres`: `postgres:18.6-alpine`, a named volume, and `pg_isready` as its healthcheck
  - `keycloak`: `quay.io/keycloak/keycloak:26.5.7`, `start-dev`, with:
    - `KC_DB=postgres`, `KC_DB_URL`, `KC_DB_USERNAME`, `KC_DB_PASSWORD`
    - `KC_HOSTNAME`, `KC_HEALTH_ENABLED=true`, and the `KC_BOOTSTRAP_ADMIN_*` variables
    - port `8080:8080`
    - healthcheck: bash `/dev/tcp` to `keycloak:9000`, then `GET /health/ready`, grepping for `"UP"`
  - `keycloak-config`: build `./keycloak`, with:
    - `KEYCLOAK_URL=http://keycloak:8080`, and `KEYCLOAK_USER`/`KEYCLOAK_PASSWORD` from the bootstrap admin
    - `IMPORT_FILES_LOCATIONS=/config/*`, `IMPORT_VARSUBSTITUTION_ENABLED=true`
    - `restart: "no"`
  - `app`: build `.`, port `8000:8000`, `extra_hosts`, `/health` healthcheck
- `Dockerfile`, `.dockerignore`
- `keycloak/Dockerfile` and `keycloak/realms/{home-fau,home-bamberg,aloysius}.json` (stubs)
- `Makefile` with targets:
  - `init`: create `.env` if missing, then `up`
  - `up`: `docker compose up -d --build --wait`
  - `apply`: rerun keycloak-config
  - `export`: as described under Decisions
  - `down`: `docker compose down`
  - `reset`: `docker compose down -v --remove-orphans`, then `init`
  - `logs`: `docker compose logs -f`
  - `help` is the default target. Every target is `.PHONY`.
- `.env.example` with the three variables below. `.gitignore` gains `export/`.
- `.devcontainer/devcontainer.json`: `--add-host=auth.localhost:host-gateway` in `runArgs`
- `docs/product/tech-stack.md`: replace the network-alias explanation with host-gateway and
  the RFC 6761 reason; mention the baked config image

## Non-goals
- Realm contents: clients, IdPs, mappers, users, and the pinned keypairs (next roadmap item)
- The CI check that `.env` and `.env.example` list the same variables (its own roadmap item)
- The CI workflow, and Trivy scanning of the app image
- Joining the stack to `iam-proxy-demo-network` (host-gateway makes it unnecessary)
- TLS, production Keycloak mode, resource limits

## Acceptance criteria
1. **Resolution (devcontainer):** after the devcontainer is rebuilt,
   `getent hosts auth.localhost` in it returns the host-gateway IP, not loopback.
2. **Clean start:** with no `.env` and no volumes, `make init` exits 0.
   - `.env` has non-empty random values for both passwords.
   - `docker compose ps` shows postgres, keycloak and app healthy, and keycloak-config exited with code 0.
3. **Running `make init` again keeps the secrets:** the second run leaves `.env` byte for byte unchanged.
4. **One issuer everywhere:**
   `curl -s http://auth.localhost:8080/realms/aloysius/.well-known/openid-configuration | jq -r .issuer`
   prints `http://auth.localhost:8080/realms/aloysius`. The same check run in the devcontainer
   and inside the app container (`docker compose exec app python -c ...`) prints the same
   value. All three realms answer.
5. **The app is up:** `curl -s localhost:8000/health` from the host (or `auth.localhost`'s
   host-gateway IP from the devcontainer) returns `{"status":"ok"}`.
6. **`make apply`:** after `"displayName": "Aloysius"` is added to `aloysius.json`,
   `make apply` exits 0 and the realm's well-known/admin view shows the new display name.
   - **Negative:** an invalid JSON realm file makes `make apply` exit non-zero.
7. **`make export`:** it writes `export/{home-fau,home-bamberg,aloysius}-realm.json`, and
   `git status` doesn't list them.
8. **`make reset`:** it drops the postgres volume, so a realm created by hand in the Admin
   Console is gone afterwards, while `.env` is unchanged. AC 2's checks pass again.
9. **`make down`** stops everything. **`make logs`** follows the logs, and Ctrl-C ends it.
10. **Negative: missing secret.** With `POSTGRES_PASSWORD` removed from `.env`,
    `docker compose config` fails with "set in .env".
11. **Negative: the healthcheck gates config.** If Keycloak isn't ready (for example postgres
    is stopped before keycloak starts), keycloak-config doesn't start and `make up` doesn't
    return 0.
12. **No secrets in the image:** `docker compose run --rm app ls -a /app` shows no `.env`.
13. `uv run pytest`, `ruff check`, `ruff format --check` and `mypy` stay clean.

## Realm settings and mappers changed
Three new realms (`home-fau`, `home-bamberg`, `aloysius`), each with only `realm` and
`enabled: true`. There are no clients, IdPs, mappers or users yet.

## New `.env` variables
| Variable | `.env.example` value | Set by `make init` |
|---|---|---|
| `KC_BOOTSTRAP_ADMIN_USERNAME` | `admin` | copied |
| `KC_BOOTSTRAP_ADMIN_PASSWORD` | empty | `openssl rand -hex 24` |
| `POSTGRES_PASSWORD` | empty | `openssl rand -hex 24` |

## Spec references
- **OIDC Core §3.1.3.7, step 2:** the ID token `iss` must exactly match the issuer. This is
  why the browser, the app and the tests all use `http://auth.localhost:8080`, never
  `keycloak:8080` (AC 4).
- **RFC 6761 §6.3:** resolvers may answer `*.localhost` with loopback themselves. This is why
  the network alias is replaced by an `/etc/hosts` entry (AC 1).
- No SAML2 Core or RFC 7636 check applies yet.
