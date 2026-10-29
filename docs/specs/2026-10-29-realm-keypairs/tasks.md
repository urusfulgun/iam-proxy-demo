# Tasks: realm files with pinned home keypairs

Spec: [spec.md](spec.md)

- [x] 1. Spike: generate one pair with openssl and apply it through config-cli in the bare-body
      format. Check that Keycloak accepts it, and whether the undeclared default key components
      survive `make apply`. Record both results in "Notes from the build".
- [x] 2. Add `cryptography==50.0.2` to the dev group and register the `e2e` marker. Create
      `tests/conftest.py` with the shared `.env` parser and the reachability skip, and switch
      `test_env_parity.py` to the parser. All existing tests still pass.
- [x] 3. Static realm-file checks, each with a negative test on synthetic input (AC 1). Write them
      first, so they fail on the current stubs.
- [x] 4. Add the key providers to `home-fau.json` and `home-bamberg.json`, and the four variables
      to `.env.example` and to `keycloak-config` in compose. The static tests and the parity test
      pass (AC 1, AC 7).
- [x] 5. Keypair checks on the local `.env`, with negative tests on pairs generated in the test
      (AC 2).
- [x] 6. Add `make keys` and `init: .env keys up`. Run the four `make keys` cases from AC 3,
      using sha256 to check idempotence.
- [x] 7. Run `make apply`, then add the `e2e` tests for the descriptor, the JWKS and the surviving
      default keys (AC 4). If task 1 showed that config-cli deletes undeclared keys, declare them
      in the realm files.
- [x] 8. Run `make reset` and compare the descriptor certs before and after (AC 5).
- [x] 9. Run the manual negative checks from AC 6 and revert each one. Confirm no secret appears
      in the output.
- [x] 10. Update `docs/product/tech-stack.md` (keypair and testing sections) and tick the item in
      `docs/product/roadmap.md`.
- [ ] 11. After the push, the PR's `check` run is green, with the `e2e` and local-`.env` tests
      skipped (AC 7).

This item has no API access check, so it needs no passing/negative API test pair. The negative
tests in AC 1, AC 2 and AC 6 cover its own checks. It has no support drill (the rotation drill is
in Phase 4), so it needs no runbook task. Build-spec step 4 (the alice/carol login) doesn't apply
yet: there are no IdPs, users or `/api/*` routes.

## Notes from the build
- **Task 1 (spike):** Keycloak 26.5.7 accepts the bare base64 body for both `privateKey` and
  `certificate`. The undeclared default key components (`rsa-enc-generated`,
  `hmac-generated-hs512`, `aes-generated`) survive both `make apply` on an existing realm and
  realm creation after `make reset`, so they aren't declared. `rsa-generated` stays as a
  component and its key shows as DISABLED; it isn't in the descriptor or the JWKS.
- **`keyUse` dropped:** the `rsa` provider has no `keyUse` property; Keycloak discarded it from
  the stored config. It isn't in the realm files.
- **Shared parser:** it lives in `tests/envfile.py`, not in `conftest.py`, so test modules import it
  as a module (`tests/__init__.py` added). `conftest.py` has the `dotenv` fixture and the `e2e`
  reachability skip. `test_env_parity.py` keeps `env_keys` as a thin wrapper, so its tests didn't
  change.
- **Parity test caught a comment:** a `$(env:VAR)` in a compose comment counted as a reference
  and failed the parity check. The comment was reworded.
- **curl and `*.localhost`:** from the devcontainer, plain curl connects to loopback for
  `auth.localhost` and ignores `/etc/hosts`. httpx2 (getaddrinfo) uses the host-gateway entry.
  This is noted in tech-stack.md.
- **AC 1/2/4:** 48 passed with the stack up. With the stack down: 42 passed, 6 `e2e` skipped. With
  no stack and no `.env` (CI): 38 passed, 10 skipped.
- **AC 3:** all four `make keys` cases passed in a scratch copy: fresh fill, byte-identical rerun,
  old values kept, and only the FAU pair regenerated.
- **AC 5:** the descriptor cert hashes were identical before and after `make reset`.
- **AC 6:** a mismatched cert makes `make apply` exit 2. Keycloak answers 400
  `Certificate does not match private key` and leaves the realm unchanged (tests still green). A
  missing variable makes compose fail with
  `required variable HOME_BAMBERG_SAML_PRIVATE_KEY is missing a value: set in .env`. Neither log
  contains a secret value.
- **Descriptor:** `home-fau` already advertises `WantAuthnRequestsSigned="true"`. That's for the
  Phase 2 home-fau IdP item, where the home clients turn off *Client signature required*.
- **build-spec step 4** (alice/carol e2e) doesn't apply yet: there are no IdPs, users or `/api/*`
  routes.
