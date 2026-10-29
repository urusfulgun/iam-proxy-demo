# Spec: realm files with pinned home keypairs

Roadmap: Phase 1, "M: Three realm files in `keycloak/realms/`; home realms with pinned demo
keypairs (private keys via `.env`)".

## Goal
`home-fau` and `home-bamberg` each sign with one RSA keypair. `make init` generates it once and
stores it only in `.env`, and keycloak-config-cli loads it through `$(env:VAR)`. It is the realm's
only RS256 signing key, so the SAML descriptor publishes exactly that certificate. The key stays
the same across `make reset` and `make apply`. `aloysius` is unchanged: its own keys aren't
pinned, because AuthnRequests are unsigned (tech-stack.md).

## Current state
- `keycloak/realms/{home-fau,home-bamberg,aloysius}.json` hold only `realm` and `enabled: true`.
- `.env.example` has `KC_BOOTSTRAP_ADMIN_USERNAME`, `KC_BOOTSTRAP_ADMIN_PASSWORD` and
  `POSTGRES_PASSWORD`. The Makefile's `.env` rule copies it and fills the two passwords. It runs
  only when `.env` is missing.
- `keycloak-config` gets only the admin credentials. Realm files are baked into its image
  (`keycloak/Dockerfile`).
- `tests/test_env_parity.py` requires the keys of `.env.example` to equal the `${VAR}` names in
  compose plus the `$(env:VAR)` names in the realm files. It also requires the local `.env` to
  have the same keys.
- `cryptography` isn't a dependency yet. `httpx2` is in the dev group.

## Decisions
- **Four new variables:** `HOME_FAU_SAML_PRIVATE_KEY`, `HOME_FAU_SAML_CERT`,
  `HOME_BAMBERG_SAML_PRIVATE_KEY` and `HOME_BAMBERG_SAML_CERT`. Each value is the base64 body of
  a PEM on one line, with no header, footer or newlines: a PKCS#8 key and an X.509 cert. `.env`
  stays one `NAME=value` per line, so `env_keys` still parses it. Keycloak's `PemUtils` strips
  headers and whitespace before decoding, so the bare body should be accepted (task 1 checks).
- **Not yet:** the broker's trusted-cert variables (`ALOYSIUS_…_CERT`) belong to the brokering
  item. Adding them now would fail the parity test as unused.
- **Key generation:** a new `make keys` target, which `init` depends on (`init: .env keys up`).
  For each home realm where either variable is missing or empty in `.env`, it runs
  `openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -subj "/CN=<realm>"` and writes both
  values together, so the pair always matches. If a realm's key and cert are both non-empty, it
  leaves them alone. It never prints a value. RSA 2048 matches Keycloak's default, and with 10
  years of validity the cert won't expire during the demo.
- **Wiring:** `keycloak-config` gets the four variables as `${VAR:?set in .env}`. The Keycloak
  server doesn't get them.
- **Key provider:** in each home realm, `components."org.keycloak.keys.KeyProvider"` gets:
  - `<realm>-saml-signing`, `providerId: rsa`: `priority 200`, `enabled` and `active` `true`,
    `algorithm RS256`, `keyUse SIG`, with `privateKey` and `certificate` set to `$(env:…)`
  - `rsa-generated`, `providerId: rsa-generated`: `enabled: false`

  Keycloak signs SAML with the realm's active RS256 key of highest priority. With the generated
  key disabled there's only one, so the rotation drill later has a single cert to swap.
- **The other default keys** (`rsa-enc-generated`, `hmac-generated-hs512`, `aes-generated`) must
  survive. If keycloak-config-cli's component management deletes undeclared components, they are
  declared in the file as exports show them. A task checks this.
- **Exports contain private keys:** `make export` writes the provider's `privateKey`. When copying
  an export into `keycloak/realms/`, replace the key and the cert with the `$(env:…)` form.
  `export/` is already git-ignored. A static test fails if a realm file contains a PEM header or
  an inline base64 blob longer than 200 characters.
- **Live tests:** an `e2e` marker, registered in `pyproject.toml` (`[tool.pytest] markers`, needed
  because `strict = true`). An autouse check in `tests/conftest.py` makes a short httpx2 GET. If
  it fails, `e2e` tests skip with "Keycloak not reachable at http://auth.localhost:8080". So
  `uv run pytest` runs them when the stack is up, and CI skips them.
- **Reading `.env` values in tests:** one shared parser in `tests/conftest.py`, built on the
  `env_keys` line rules, returns a dict. `test_env_parity.py` switches to it, so there is a single
  parser. Messages still name keys only.
- **`cryptography==50.0.2`** joins the dev group (the version tech-stack.md pins). Tests use it to
  check each pair.

## Scope
- `keycloak/realms/home-fau.json`, `keycloak/realms/home-bamberg.json`: key providers
- `docker-compose.yml`: four variables on `keycloak-config`
- `Makefile`: `keys` target; `init: .env keys up`
- `.env.example`: four empty variables, with a comment that `make keys` fills them
- `pyproject.toml` and `uv.lock`: `cryptography` in the dev group, the `e2e` marker
- `tests/conftest.py` (new), `tests/test_realm_keys.py` (new), `tests/test_env_parity.py`
  (switches to the shared parser)
- `docs/product/tech-stack.md`: the keypair section (value format, `make keys`, `rsa-generated`
  disabled) and the testing section (`e2e` marker, auto-skip)
- `docs/product/roadmap.md`: tick the item

## Non-goals
- SAML clients, mappers, user profile and users in the home realms (Phase 2)
- The SAML IdPs in `aloysius` and the broker's trusted-cert variables (Phase 2)
- Pinning the `aloysius` keys
- The rotation drill and its runbook (Phase 4)
- Regenerating or rotating keys automatically

## Acceptance criteria
1. **Static (CI):** `uv run pytest` checks that:
   - each realm file is valid JSON
   - each home realm has exactly one enabled, active `rsa` provider with priority above 100
   - that provider's `privateKey` is exactly `$(env:HOME_<X>_SAML_PRIVATE_KEY)` and its
     `certificate` is exactly `$(env:HOME_<X>_SAML_CERT)`
   - each home realm declares `rsa-generated` with `enabled: false`
   - no realm file holds an inline PEM or a long base64 blob

   Negative unit tests on synthetic dicts cover a missing provider, a second active `rsa`
   provider, a literal key instead of `$(env:…)`, the other realm's variable, `rsa-generated`
   left enabled, and a `-----BEGIN` string.
2. **Local `.env` (skipped without `.env`):** for each home realm, the key and cert parse and
   their public keys match. The key is RSA with at least 2048 bits, and the cert stays valid for
   at least 365 more days. The FAU and Bamberg keys differ. Negative unit tests on pairs
   generated in the test cover a mismatched pair, a 1024-bit key, an expired cert, and one key
   used for both realms. No message contains a value.
3. **`make keys`:**
   - On a fresh `.env` copied from `.env.example`, it fills all four variables.
   - Run again, `.env` is byte-identical (same sha256).
   - On an existing `.env` with only the three old keys, it adds the four and leaves the old
     values unchanged.
   - With only `HOME_FAU_SAML_CERT` emptied, it regenerates the FAU pair and nothing else.
4. **Live (`e2e`):**
   - `GET /realms/<home>/protocol/saml/descriptor` has exactly one signing
     `<ds:X509Certificate>`, and it equals `HOME_<X>_SAML_CERT`.
   - The realm's JWKS (`/protocol/openid-connect/certs`) has exactly one RS256 `sig` key, and its
     `x5c[0]` is the same cert.
   - The other default keys still exist (admin `GET /admin/realms/<home>/keys`).
5. **Persistence:** after `make reset`, both realms' descriptor certs are the same as before.
6. **Manual negative checks (reverted):**
   - With `HOME_FAU_SAML_CERT` set to the Bamberg cert, `make apply` exits non-zero because
     Keycloak rejects the cert/key mismatch.
   - With a variable removed from `.env`, compose fails with `set in .env` and the variable's
     name.
7. `ruff check`, `ruff format --check`, `mypy` and `pytest` pass, including the parity test with
   the four new variables. On the PR, the CI `check` job is green, with the `e2e` and local-`.env`
   tests skipped.

## Realm settings and mappers changed
- `home-fau`, `home-bamberg`: a new `rsa` key provider `<realm>-saml-signing` (priority 200,
  RS256, SIG, key and cert from `.env`); `rsa-generated` disabled
- `aloysius`: none
- Mappers: none

## New `.env` variables
`HOME_FAU_SAML_PRIVATE_KEY`, `HOME_FAU_SAML_CERT`, `HOME_BAMBERG_SAML_PRIVATE_KEY` and
`HOME_BAMBERG_SAML_CERT`. `make keys` generates them. They are empty in `.env.example`, and only
`keycloak-config` uses them.

## Spec references
- SAML2 Core §5 (Signatures): the key that will sign assertions. Signing itself is turned on in
  Phase 2.
- SAML2 Metadata §2.4.1.1 (`<KeyDescriptor use="signing">`): what the descriptor check reads.
- RFC 7517 §4.7 (`x5c`): what the JWKS check reads.
- OIDC Core and RFC 7636: no checks in this item.
