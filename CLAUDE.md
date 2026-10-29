# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Goal

Minimal demo of an Aloysius-style IAM proxy: Keycloak realm 'aloysius' brokers two
home-university realms over SAML2, enriches attributes (groups, guests, licenses) and
serves a FastAPI app (Python 3.14) over OIDC with PKCE. No business logic, no UI,
no database.

## Product docs

@docs/product/mission.md
@docs/product/roadmap.md
@docs/product/tech-stack.md

## Commands

- `make init` starts the stack; `make reset` rebuilds it from scratch
- `make export` dumps the live realm config so you can copy it into `keycloak/realms/`
- `uv sync` installs dependencies into `.venv`
- `uv run pytest` runs the tests; for a single test, `uv run pytest path/to/test_x.py::test_name`
- `uv run ruff check` lints and `ruff format` formats; `mypy --strict` type-checks

## Rules

- Every non-trivial change starts with a spec in `docs/specs/`. `/next-spec` writes it, `/build-spec` implements it.
- Keycloak config lives in `keycloak/realms/*.json`, applied by keycloak-config-cli. Never rely on manual Admin Console changes: run `make export` and copy the result into the files.
- Attribute names follow eduPerson and SCHAC, with their `urn:oid` names in SAML.
- Keep code small; comments reference the spec section (SAML2 Core, OIDC Core, RFC 7636).
- Every access check in the API gets a negative test.
- Every failure demo gets a short runbook in `docs/runbooks/`.
- Secrets live only in `.env`; every new variable also goes into `.env.example`.
- Keycloak is `http://auth.localhost:8080` everywhere; container healthchecks use `http://keycloak:9000/health/ready`.
