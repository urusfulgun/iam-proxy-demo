# Tasks: home-fau as SAML IdP

Spec: [spec.md](spec.md)

- [ ] 1. Spike, then record the results in "Notes from the build":
      - Does config-cli 6.5.1 apply a `userProfile` key? If not, use the
        `UserProfileProvider` component as `make export` writes it.
      - Does the persistent NameID attribute `saml.persistent.name.id.for.<clientId>` survive
        with unmanaged attributes disabled, so that a second login gets the same NameID?
      - Does `defaultClientScopes: []` really keep `role_list` out of the assertion?
- [ ] 2. Move `admin_token` to `tests/conftest.py` and import it in `test_realm_keys.py`. All
      tests still pass.
- [ ] 3. Write the static checks for `home-fau.json` (client, mappers, user profile, alice's
      credential), each with its negative test on synthetic dicts (AC 1). Write them first, so
      they fail on the current file.
- [ ] 4. Add the client, mappers, user profile and alice to `home-fau.json`. Add
      `DEMO_USER_PASSWORD` to `.env.example`, to `.env`, and to `keycloak-config` in compose.
      The static tests and the parity test pass (AC 1, AC 7).
- [ ] 5. Add `make secrets`, `init: .env secrets keys up`, and the `.env` rule reduced to a
      copy. Run the AC 5 cases in a scratch copy, using sha256 for idempotence.
- [ ] 6. `tests/saml.py`: the AuthnRequest builder, Redirect encoding, form parser, Response
      decoder and structural signature check. The check gets its unit negatives on a fixture
      Response (AC 3, last bullet).
- [ ] 7. Run `make apply`, then add the e2e login test for alice: Destination, InResponseTo,
      Audience, Issuer, persistent NameID stable across two logins, three `urn:oid` attributes,
      and both signatures (AC 2).
- [ ] 8. Add the e2e negatives: unknown Issuer, a different ACS URL, and a wrong password (AC 3).
- [ ] 9. Add the e2e user-profile checks: admin-only attributes, alice's values, and an
      undeclared attribute that is dropped (AC 4).
- [ ] 10. Run `make reset`, then rerun the e2e tests (AC 6).
- [ ] 11. Update `docs/product/tech-stack.md` (demo password, `make secrets`, `tests/saml.py`,
      user-profile format if task 1 changed it), then tick the item in `docs/product/roadmap.md`.
- [ ] 12. After the push, the PR's `check` run is green, with the `e2e` and local-`.env` tests
      skipped (AC 7).

Access checks in this item, each with a passing test and a negative test:
- The ACS is exact. Passing: alice's login gets a Response that posts to the ACS. Negative:
  another ACS URL is refused.
- Only the known SP is served. Passing: the aloysius Issuer gets a Response. Negative: an unknown
  Issuer is refused.
- Only valid credentials get a Response. Passing: alice's password works. Negative: a wrong
  password gets the login form again.
- Signatures pass the structural check. Passing: alice's Response passes. Negative: the four
  fixture cases fail.

This item has no `/api/*` route, so it has no API access test. It has no support drill (the
undeclared-attribute and wrong-ACS drills are in Phase 4), so it needs no runbook task.
Build-spec step 4 doesn't apply yet, because there is no broker or `/api/*` route; task 7's alice
login through home-fau is the closest check.

## Notes from the build
