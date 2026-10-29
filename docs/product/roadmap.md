# Roadmap

Sizes: S = under half a day, M = about a day, L = several days. Each item becomes one spec via `/next-spec`.

**First slice:** phases 1–3, which take the stack from a clean clone to the users table passing end to end.

## Phase 1: Foundation
- [x] S: uv project on Python 3.14 with a FastAPI `/health` route
- [x] S: pytest, ruff and `mypy --strict` configured in `pyproject.toml`
- [ ] S: CI workflow: `uv sync`, ruff, mypy, pytest, pip-audit on `uv.lock`
- [ ] S: `.env.example` committed, `.env` git-ignored; CI check that both list the same variables
- [x] M: `docker-compose.yml`: postgres, keycloak (`auth.localhost` via host-gateway, bootstrap admin from `.env`, healthcheck on `:9000/health/ready`), one-shot keycloak-config, app
- [x] S: Makefile targets `init`, `apply`, `reset`, `export`, `up`, `down`, `logs`
- [ ] M: Three realm files in `keycloak/realms/`; home realms with pinned demo keypairs (private keys via `.env`)

## Phase 2: Federation core
- [ ] M: home-fau as SAML IdP: signed assertions; ePPN, ePSA and schacHomeOrganization mappers (`urn:oid`, URI format), declared in the user profile
- [ ] L: aloysius brokers home-fau over SAML: trusts the pinned cert, persistent NameID, signature validation on, attribute importer mappers
- [ ] S: OIDC client `aloysius-app` with PKCE S256 required and an exact redirect URI
- [ ] M: FastAPI `/login`, `/callback` (state, nonce, PKCE) and `/whoami` printing the claims
- [ ] M: Scripted httpx2 e2e login through both hops (alice via home-fau)
- [ ] M: home-bamberg as a second SAML IdP, brokered the same way
- [ ] S: IdP chooser and `kc_idp_hint` via `/login?idp=`

## Phase 3: Enrichment and authorization
- [ ] S: Hardcoded group mapper on the home-fau IdP: `license-matlab`
- [ ] S: alice pre-linked (`federatedIdentities`, pinned persistent NameID) with group `aloysius-admins`
- [ ] S: dave as a local guest user in aloysius
- [ ] S: Protocol mappers emitting `groups` and an eduPersonEntitlement-style claim, plus an audience mapper
- [ ] M: Token validation: JWKS via PyJWKClient, RS256 pinned, `iss`, `aud`, `exp`, `typ`
- [ ] M: `/api/me`, `/api/licensed-tool`, `/api/admin` with entitlement and group checks; a negative test for each
- [ ] S: Users table in the docs and an e2e test asserting every status code

## Phase 4: Support drills
Each drill is a failing test or a reproducible break, with a runbook in `docs/runbooks/`.
- [ ] M: Attribute not released by the home IdP
- [ ] M: Home IdP signing key rotated without updating the broker
- [ ] S: Wrong ACS URL or entityID
- [ ] M: Clock skew on the assertion
- [ ] S: PKCE verifier missing or wrong
- [ ] S: Issuer mismatch when a container uses `keycloak:8080` instead of `auth.localhost`
- [ ] S: carol and dave calling `/api/admin` (403)
- [ ] M: Transient NameID breaks the pre-link
- [ ] S: Undeclared attribute dropped by the user profile
- [ ] S: Missing audience mapper gives 401
- [ ] S: Forged, alg-confused or expired token gives 401

## Phase 5: Stretch
- [ ] L: aloysius also serves a SAML client (a service connected via SAML)
- [ ] S: Onboarding guide for a new service operator
- [ ] L: DPoP-bound tokens (RFC 9449)
- [ ] M: Single logout
- [ ] S: Trivy scan of the app image in CI (HIGH/CRITICAL, `--ignore-unfixed`, action pinned by commit SHA)
