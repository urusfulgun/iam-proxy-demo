# Spec: uv project on Python 3.14 with a FastAPI `/health` route

Roadmap: Phase 1, "S: uv project on Python 3.14 with a FastAPI `/health` route".

## Goal
On a clean clone, `uv sync` creates a Python 3.14 virtualenv with FastAPI installed, and
`uv run iam-proxy-demo` serves `GET /health` on port 8000, returning `200 {"status": "ok"}`.

## Current state
The repo still has the `uv init` skeleton: `pyproject.toml` with no dependencies,
`src/iam_proxy_demo/__init__.py` with a hello-world `main()`, `.python-version` set to `3.14`,
and a `uv.lock` with no packages. There is no Makefile, `docker-compose.yml`, realm file or
`.env.example` yet.

## Decisions
- **Entrypoint:** the existing `iam-proxy-demo` script stays. `main()` calls `uvicorn.run` on
  `0.0.0.0:8000`, so dev and the later compose `app` service use the same command. Port 8000
  matches the devcontainer's `forwardPorts`.
- **`/health` is liveness only.** It makes no call to Keycloak, so the app container's
  healthcheck never depends on Keycloak. Keycloak readiness is checked separately on
  `http://keycloak:9000/health/ready`.
- **Test tooling is minimal:** a `dev` dependency group with pytest and httpx2 (which
  `TestClient` needs), plus one test file. httpx2 replaces httpx 0.28.1, which Starlette 1.10's
  `TestClient` deprecates; `tech-stack.md` now uses httpx2 everywhere. `[tool.pytest]`, `[tool.ruff]` and `[tool.mypy]`
  config belongs to the next roadmap item.

## Scope
- `pyproject.toml`
  - `description`: a real one-line description, replacing "Add your description here"
  - `dependencies`: `fastapi>=0.162,<0.163`, `uvicorn>=0.54,<0.55`
  - `[dependency-groups]` `dev = ["pytest>=9.2,<10", "httpx2==2.16.0"]`
  - `requires-python = ">=3.14"` stays as it is
- `src/iam_proxy_demo/app.py`: `app = FastAPI(title="aloysius-app")` and `GET /health`
  returning `{"status": "ok"}` with a typed return value
- `src/iam_proxy_demo/__init__.py`: `main()` runs
  `uvicorn.run("iam_proxy_demo.app:app", host="0.0.0.0", port=8000)`
- `tests/test_health.py`: uses `fastapi.testclient.TestClient`
- `uv.lock`: regenerated with `uv lock`

## Non-goals
- `[tool.*]` config for pytest, ruff and mypy (next roadmap item)
- CI workflow, Dockerfile, `docker-compose.yml`, Makefile
- Any Keycloak, OIDC or SAML code
- Probing Keycloak from `/health`

## Acceptance criteria
1. `uv sync` succeeds on Python 3.14, and `uv.lock` pins fastapi 0.162.x, uvicorn 0.54.x,
   pytest 9.2.x and httpx2 2.16.0.
2. `uv run pytest` passes:
   - `GET /health` returns 200 with body `{"status": "ok"}`
   - `POST /health` returns 405 (negative test)
3. With `uv run iam-proxy-demo` running, `curl -s localhost:8000/health` prints `{"status":"ok"}`.
4. `uv run ruff check`, `ruff format --check` and `mypy --strict src tests` are clean with
   default settings.

## Realm settings and mappers changed
None.

## New `.env` variables
None. `.env.example` does not exist yet and is not created here.

## Spec references
None apply. `/health` is an unauthenticated liveness route, with no SAML2 Core, OIDC Core or
RFC 7636 check.
