# Tasks: realm files with pinned home keypairs

Spec: [spec.md](spec.md)

- [ ] 1. Spike: generate one pair with openssl and apply it through config-cli in the bare-body
      format. Check that Keycloak accepts it, and whether the undeclared default key components
      survive `make apply`. Record both results in "Notes from the build".
- [ ] 2. Add `cryptography==50.0.2` to the dev group and register the `e2e` marker. Create
      `tests/conftest.py` with the shared `.env` parser and the reachability skip, and switch
      `test_env_parity.py` to the parser. All existing tests still pass.
- [ ] 3. Static realm-file checks, each with a negative test on synthetic input (AC 1). Write them
      first, so they fail on the current stubs.
- [ ] 4. Add the key providers to `home-fau.json` and `home-bamberg.json`, and the four variables
      to `.env.example` and to `keycloak-config` in compose. The static tests and the parity test
      pass (AC 1, AC 7).
- [ ] 5. Keypair checks on the local `.env`, with negative tests on pairs generated in the test
      (AC 2).
- [ ] 6. Add `make keys` and `init: .env keys up`. Run the four `make keys` cases from AC 3,
      using sha256 to check idempotence.
- [ ] 7. Run `make apply`, then add the `e2e` tests for the descriptor, the JWKS and the surviving
      default keys (AC 4). If task 1 showed that config-cli deletes undeclared keys, declare them
      in the realm files.
- [ ] 8. Run `make reset` and compare the descriptor certs before and after (AC 5).
- [ ] 9. Run the manual negative checks from AC 6 and revert each one. Confirm no secret appears
      in the output.
- [ ] 10. Update `docs/product/tech-stack.md` (keypair and testing sections) and tick the item in
      `docs/product/roadmap.md`.
- [ ] 11. After the push, the PR's `check` run is green, with the `e2e` and local-`.env` tests
      skipped (AC 7).

This item has no API access check, so it needs no passing/negative API test pair. The negative
tests in AC 1, AC 2 and AC 6 cover its own checks. It has no support drill (the rotation drill is
in Phase 4), so it needs no runbook task. Build-spec step 4 (the alice/carol login) doesn't apply
yet: there are no IdPs, users or `/api/*` routes.
