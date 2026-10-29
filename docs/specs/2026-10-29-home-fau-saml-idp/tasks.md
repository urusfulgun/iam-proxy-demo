# Tasks: home-fau as SAML IdP

Spec: [spec.md](spec.md)

- [x] 1. Spike, then record the results in "Notes from the build":
      - Does config-cli 6.5.1 apply a `userProfile` key? If not, use the
        `UserProfileProvider` component as `make export` writes it.
      - Does the persistent NameID attribute `saml.persistent.name.id.for.<clientId>` survive
        with unmanaged attributes disabled, so that a second login gets the same NameID?
      - Does `defaultClientScopes: []` really keep `role_list` out of the assertion?
- [x] 2. Move `admin_token` to `tests/conftest.py` and import it in `test_realm_keys.py`. All
      tests still pass.
- [x] 3. Write the static checks for `home-fau.json` (client, mappers, user profile, alice's
      credential), each with its negative test on synthetic dicts (AC 1). Write them first, so
      they fail on the current file.
- [x] 4. Add the client, mappers, user profile and alice to `home-fau.json`. Add
      `DEMO_USER_PASSWORD` to `.env.example`, to `.env`, and to `keycloak-config` in compose.
      The static tests and the parity test pass (AC 1, AC 7).
- [x] 5. Add `make secrets`, `init: .env secrets keys up`, and the `.env` rule reduced to a
      copy. Run the AC 5 cases in a scratch copy, using sha256 for idempotence.
- [x] 6. `tests/saml.py`: the AuthnRequest builder, Redirect encoding, form parser, Response
      decoder and structural signature check. The check gets its unit negatives on a fixture
      Response (AC 3, last bullet).
- [x] 7. Run `make apply`, then add the e2e login test for alice: Destination, InResponseTo,
      Audience, Issuer, persistent NameID stable across two logins, three `urn:oid` attributes,
      and both signatures (AC 2).
- [x] 8. Add the e2e negatives: unknown Issuer, a different ACS URL, and a wrong password (AC 3).
- [x] 9. Add the e2e user-profile checks: admin-only attributes, alice's values, and an
      undeclared attribute that is dropped (AC 4).
- [x] 10. Run `make reset`, then rerun the e2e tests (AC 6).
- [x] 11. Update `docs/product/tech-stack.md` (demo password, `make secrets`, `tests/saml.py`,
      user-profile format if task 1 changed it), then tick the item in `docs/product/roadmap.md`.
- [x] 12. After the push, the PR's `check` run is green, with the `e2e` and local-`.env` tests
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
- **Task 1, user profile:** config-cli 6.5.1 applies the top-level `userProfile` key only when the
  realm attribute `userProfileEnabled` is `"true"` (`UserProfileImportService`, a leftover from
  Keycloak < 24). Without it, the key is silently ignored, and so are alice's attributes, since
  undeclared attributes get dropped. `home-fau.json` sets `"attributes": {"userProfileEnabled":
  "true"}`, so the readable `userProfile` form stays and no component blob is needed.
- **Task 1, persistent NameID:** Keycloak returned `G-<uuid>`, the same value on both logins.
  It is stored as the user attribute
  `saml.persistent.name.id.for.http://auth.localhost:8080/realms/aloysius` (seen in Postgres).
  The admin API hides it because the user profile doesn't declare it, but unmanaged attributes
  being disabled doesn't stop Keycloak from storing or reusing it. That matters for pinning it
  in Phase 3.
- **Task 1, client scopes:** with `defaultClientScopes: []`, the assertion has exactly the three
  attributes and no `Role`.
- **Task 1, Secure cookies over HTTP:** Keycloak marks `AUTH_SESSION_ID`, `KC_RESTART` and
  `KC_AUTH_SESSION_HASH` as `Secure; SameSite=None`, even on `http://auth.localhost`. Browsers
  send them anyway, because they treat `*.localhost` as a secure context (W3C Secure Contexts
  §3.1). Python's cookiejar doesn't, and the login fails with `cookie_not_found`. `tests/saml.py`
  gives its client a cookie policy that treats `auth.localhost` as secure, which mirrors the
  browser.
- **Parity test and message keys:** the default user-profile attributes use Keycloak message keys
  (`"displayName": "${username}"`). The parity test read them as compose variables and failed.
  Realm files are now scanned only for `$(env:VAR)`, which is all config-cli substitutes, and a
  unit test pins that.
- **Static tests first (AC 1):** run against the committed `home-fau.json` (stashed), the
  realm-file and alice checks failed. They pass on the new file. The 16 negatives, on a
  synthetic realm, cover every case listed in AC 1, plus an unknown SP, a default client scope,
  an extra mapper, a single-valued ePSA and a missing `userProfileEnabled` flag.
- **Live negatives (AC 3):** Keycloak logged exactly the expected `LOGIN_ERROR`s:
  `client_not_found` (unknown Issuer, HTTP 400), `invalid_redirect_uri` (other ACS, HTTP 400)
  and `invalid_user_credentials` (wrong password, login form shown again).
- **AC 4:** a `PUT` with `foo` is accepted (2xx), and alice's attributes afterwards are exactly
  the three declared ones.
- **AC 5:** all four `make secrets` cases passed in a scratch copy: a fresh fill (48/48/12
  characters), a byte-identical rerun with no output, an existing `.env` that only gets
  `DEMO_USER_PASSWORD` added, and output that names variables but never values. On the real
  `.env`, it is a no-op.
- **AC 6:** `make reset` left `.env` byte-identical. Afterwards, 87 tests passed with none
  skipped. With no `.env` (as in CI), 67 passed and 20 were skipped.
- **Build-spec step 4** (alice via home-fau, carol via home-bamberg, `/api/*`) doesn't apply yet:
  there is no broker, no home-bamberg user and no `/api/*` route. alice's direct SP-initiated
  login against home-fau (AC 2) is the closest check, and it passes.
- **AC 7:** the `check` run on PR #20 was green, with the `e2e` and local-`.env` tests skipped
  (confirmed by the user).
