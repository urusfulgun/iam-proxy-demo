# Tech stack

Versions current as of 2026-10-29. Python packages are pinned in `uv.lock`, images by exact tag in `docker-compose.yml`.

## Language: Python
- **What:** CPython, managed by uv
- **Version:** 3.14 (devcontainer pins 3.14.8)
- **Why:** Fixed choice. Every dependency below ships wheels that install on 3.14.

## Package manager: uv
- **What:** uv for the interpreter, the virtualenv, dependencies and the lockfile (`uv sync`, `uv run`)
- **Version:** 0.13.x (build backend `uv_build` 0.13)
- **Why:** Already in use in the repo and installed by the devcontainer. One tool instead of pip, venv and a lock tool.

## Web framework: FastAPI
- **What:** FastAPI served by uvicorn. Endpoints are `/login`, `/callback`, `/api/me`, `/api/licensed-tool` and `/api/admin`.
- **Version:** FastAPI 0.162, uvicorn 0.54
- **Why:** Fixed choice. Dependency injection gives each access check its own small, testable function.

## Identity provider: Keycloak
- **What:** One Keycloak server with three realms: `home-fau`, `home-bamberg` and `aloysius`. It runs in `start-dev` mode with Postgres configured via `KC_DB=postgres`. The hostname is `http://auth.localhost:8080` (`KC_HOSTNAME`), and Keycloak publishes 8080 on the host. The browser resolves `auth.localhost` to loopback on the host. The app container (`extra_hosts`) and the devcontainer (`--add-host` in `runArgs`) map `auth.localhost` to `host-gateway`, so the browser, the app's back-channel calls and the tests all hit the same published port and `iss` matches. A Docker network alias would not work: the resolver chain answers `*.localhost` with loopback (RFC 6761 §6.3) before the alias is consulted. An `/etc/hosts` entry wins over that, which was checked on glibc 2.43 (devcontainer) and 2.41 (app image) with `getaddrinfo`. `getent hosts` still shows `::1`, because it asks for IPv6 only. `KC_HEALTH_ENABLED=true` turns on the healthcheck, which probes `http://keycloak:9000/health/ready` on the management port (not published to the host). The image has no curl, so the check uses bash `/dev/tcp` and greps for `"UP"`.
- **Version:** `quay.io/keycloak/keycloak:26.5.7`
- **Why:** 26.5.7 is the latest patch of the newest line that keycloak-config-cli is built for (see below). 26.6–26.8 have no matching config-cli build. `start-dev` gives plain HTTP with no TLS or `kc.sh build` step, which is enough for a local demo, and the database is still the real one. `/health/ready` reports `UP` only after startup and a healthy database connection, so keycloak-config-cli and the app can safely wait on `service_healthy`.

## Database: PostgreSQL
- **What:** Keycloak's own database. The app has no database.
- **Version:** `postgres:18.6-alpine`
- **Why:** The newest major that Keycloak's database docs list as tested (18.x, 17.x, 16.x, 15.x, 14.x), in a small image. `make reset` drops the volume, so data never outlives a rebuild.

## Realm configuration: keycloak-config-cli
- **What:** A one-shot container that applies `keycloak/realms/*.json` after Keycloak is healthy. Files are JSON, and secrets come in via `$(env:VAR)` substitution from `.env`. The realm files are copied into a small image (`keycloak/Dockerfile`) instead of bind-mounted, because the Docker daemon runs on the host, where the devcontainer's paths don't exist. `make apply` rebuilds and reruns it. It only updates the fields a file contains, so deleting a field from a file doesn't unset it in Keycloak; `make reset` does.
- **Version:** `adorsys/keycloak-config-cli:6.5.1-26.5.5`
- **Why:** 6.5.1 is the latest release, and 26.5.5 is the newest Keycloak version it is built against, which is compatible with 26.5.7. JSON matches what `make export` produces, so exports copy straight in. Known issue: 6.5.1 rejects the `types` field that 26.5+ adds to exported identity providers (fixed upstream, not yet released). Strip that field when copying exports.

## SAML signing certificates: pinned demo keypairs
- **What:** `make init` generates a self-signed RSA keypair once for each home realm and writes it to `.env`. Each home realm file declares an `rsa` key provider that reads the key and cert from `.env`. Each aloysius SAML IdP lists its home realm's cert under *Validating X509 certificates*, also read from `.env`. The broker's trusted cert has its own variable, which `make init` sets equal to the home cert. AuthnRequests are unsigned (*Client signature required* off on the home clients), so aloysius's own keys don't need pinning.
- **Version:** Keycloak `rsa` key provider and SAML IdP settings; keys generated with `openssl`
- **Why:** The keys survive `make reset`, and the trust relationship is explicit in the config. The rotation drill can change the home key without changing the broker's trusted cert and get a real signature failure. A metadata descriptor URL would refetch the new key automatically and hide that failure. The private keys live only in `.env`.

## OIDC client: httpx2 + PyJWT
- **What:** Hand-rolled authorization code flow with PKCE (S256). httpx2 makes the token request, and PyJWT validates the ID token and access tokens (`algorithms=["RS256"]`; `iss`, `aud`, `exp` and `typ` required). State, nonce and verifier live in a signed session cookie (Starlette `SessionMiddleware`).
- **Version:** httpx2 2.16.0, PyJWT 2.15.1 with `cryptography` 50.0.2 (pure-Python and abi3 wheels, which install on 3.14)
- **Why:** About 60 lines where every step and check is visible and can cite OIDC Core or RFC 7636 in a comment. A teaching demo should show these steps; authlib would hide them. httpx2 is Pydantic's successor to httpx; Starlette uses it as a drop-in (`import httpx2 as httpx`). Starlette 1.10's `TestClient` deprecates httpx in its favour, so one HTTP client serves the app, the unit tests and the e2e scripts.

## JWKS fetching and caching: PyJWKClient
- **What:** One module-level `PyJWKClient` for `http://auth.localhost:8080/realms/aloysius/protocol/openid-connect/certs`. It caches keys in-process with a TTL, selects by `kid`, and refetches once on an unknown `kid`.
- **Version:** Built into PyJWT 2.15.1
- **Why:** Handles key rotation without a restart and without a network call on every request. No extra dependency.

## Testing: pytest, locally signed tokens, scripted httpx2 login
- **What:**
  - *Unit tests:* tokens signed with a test RSA key, and the JWKS client patched to return that key. Every access check gets a passing test and a negative test.
  - *End-to-end tests (against the running stack):* scripted httpx2 clients follow `/login`, parse each auto-submit form (`SAMLRequest`, `SAMLResponse`, `RelayState`), POST it on, and submit the home realm login form. They log in alice, bob, carol and dave, then compare `/api/*` status codes to the users table.
- **Version:** pytest 9.2
- **Why:** No browser download. Each SAML and OIDC hop is an explicit step in the test, so the test reads like the flow diagram and runs in seconds.

## Linting, formatting and type checking: ruff + mypy
- **What:** `uv run ruff check`, `uv run ruff format` and `uv run mypy`, configured in `pyproject.toml` (ruff rules E, F, W, I, B, UP, SIM, S; mypy `strict` over `src` and `tests`)
- **Version:** ruff 0.17, mypy 2.4, pinned in the `dev` dependency group
- **Why:** Pinning them in the dev group means `uv run` uses the venv binaries, so mypy sees the project's packages and CI runs the same versions. The devcontainer also installs both globally for VS Code (format on save, strict mypy). Strict typing catches claim-handling mistakes early.

## Dependency audit: pip-audit
- **What:** A blocking CI step that checks the locked dependencies against known vulnerabilities: `uv export --format requirements-txt --no-hashes | uvx pip-audit -r - --no-deps`
- **Version:** Run via `uvx`; the exact version is pinned in the CI workflow
- **Why:** The app's security rests on PyJWT, `cryptography` and Starlette, so a CVE in any of them matters. The dependency set is small, so the step takes seconds and rarely fails on something that isn't real. Image scanning (Trivy) waits until there is an app image: the upstream Keycloak and Postgres images are pinned and their findings can't be fixed here.
