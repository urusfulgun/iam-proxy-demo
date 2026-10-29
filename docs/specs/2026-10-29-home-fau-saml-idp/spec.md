# Spec: home-fau as SAML IdP

Roadmap: Phase 2, "M: home-fau as SAML IdP: signed assertions; ePPN, ePSA and
schacHomeOrganization mappers (`urn:oid`, URI format), declared in the user profile".

## Goal
`home-fau` acts as a SAML IdP for one SP, the future `aloysius` broker. When alice logs in, the
SP gets a SAML Response where both the Response and the Assertion are signed with the pinned
`home-fau` key. The Response has a persistent NameID and exactly three attributes, named by their
`urn:oid` with NameFormat `uri`: eduPersonPrincipalName, eduPersonScopedAffiliation and
schacHomeOrganization. Each attribute is declared in `home-fau`'s user profile, so Keycloak
stores it, and only admins can edit it.
The broker side (the IdP in `aloysius`, cert trust, importers) is the next item. This item proves
the IdP side alone, using a scripted SP-initiated login.

## Current state
- `home-fau.json` has only the realm, `enabled` and the pinned `rsa` key provider
  (`home-fau-saml-signing`, priority 200), with `rsa-generated` disabled. It has no clients,
  users or user profile.
- The descriptor already advertises `WantAuthnRequestsSigned="true"` (realm-keypairs notes). That
  is a realm-level default. Signature checking actually depends on the client's *Client
  signature required* setting.
- `.env.example` has the admin and Postgres passwords plus four keypair variables. The Makefile's
  `.env` rule fills the two passwords, but only when `.env` doesn't exist yet. `make keys` fills
  keypairs that are missing or empty.
- `tests/conftest.py` has the `e2e` skip, the `dotenv` fixture and `KEYCLOAK`.
  `tests/test_realm_keys.py` has `admin_token` and `signing_certs`.

## Decisions
- **SP entityID and ACS:** the `home-fau` SAML client has `clientId`
  `http://auth.localhost:8080/realms/aloysius`, which is Keycloak's default broker SP entityID.
  Its only ACS is `http://auth.localhost:8080/realms/aloysius/broker/home-fau/endpoint`. That URL
  appears exactly, with no wildcard, in both `redirectUris` and
  `saml_assertion_consumer_url_post`, so the later "wrong ACS URL" drill gets a hard failure.
  `saml_assertion_consumer_url_redirect` is unset, and `saml.force.post.binding` is `true`.
- **Signatures:** `saml.server.signature` is `true` (the Response) and
  `saml.assertion.signature` is `true` (the Assertion). `saml.signature.algorithm` is
  `RSA_SHA256` and `saml_signature_canonicalization_method` is exc-c14n
  (`http://www.w3.org/2001/10/xml-exc-c14n#`). `saml.server.signature.keyinfo.ext` is `false`,
  and the KeyInfo carries the X.509 cert. `saml.client.signature` is `false`: AuthnRequests stay
  unsigned (tech-stack.md). `saml.encrypt` is `false`; encryption is a non-goal.
- **NameID:** `saml_name_id_format` is `persistent` and `saml_force_name_id_format` is `true`, so
  the client always sends a persistent NameID, whatever format the SP asks for. Keycloak keeps
  the value as the user attribute `saml.persistent.name.id.for.<clientId>` and reuses it on
  every later login. Pinning alice's value is a Phase 3 item. Task 1 checks that this works with
  unmanaged attributes disabled.
- **No default client scopes:** the client sets `defaultClientScopes: []` and
  `optionalClientScopes: []`. This drops `role_list` and `saml_organization`, so the assertion
  holds only the three declared attributes. `fullScopeAllowed` is `false`.
- **Mappers live on the client** (`protocolMappers`), each of type
  `saml-user-attribute-mapper`, with `attribute.nameformat` `URI Reference`:

  | Mapper name | `user.attribute` | `attribute.name` | `friendly.name` | `aggregate.attrs` |
  |---|---|---|---|---|
  | eduPersonPrincipalName | `eduPersonPrincipalName` | `urn:oid:1.3.6.1.4.1.5923.1.1.1.6` | eduPersonPrincipalName | `false` |
  | eduPersonScopedAffiliation | `eduPersonScopedAffiliation` | `urn:oid:1.3.6.1.4.1.5923.1.1.1.9` | eduPersonScopedAffiliation | `true` |
  | schacHomeOrganization | `schacHomeOrganization` | `urn:oid:1.3.6.1.4.1.25178.1.2.9` | schacHomeOrganization | `false` |

  ePSA is multi-valued. `aggregate.attrs` sends a single `<Attribute>` with one
  `<AttributeValue>` per value.
- **User profile:** `home-fau` declares the three attributes alongside the defaults (`username`,
  `email`, `firstName`, `lastName`). Each one has `view` and `edit` permissions for `admin`
  only, so a user can't change their own affiliation on the account page. ePSA is
  `multivalued: true`. A `pattern` validator requires the scope to be `@fau.de` on ePPN
  (`^[^@\s]+@fau\.de$`) and on each ePSA value
  (`^(member|student|staff|faculty|employee|affiliate)@fau\.de$`), and `schacHomeOrganization`
  must equal `fau.de`. `unmanagedAttributePolicy` stays unset (disabled), so Keycloak drops any
  undeclared attribute. The Phase 4 drill relies on that. Task 1 decides the format: config-cli's
  `userProfile` key if 6.5.1 applies it, otherwise the
  `org.keycloak.userprofile.UserProfileProvider` component with `kc.user.profile.config`, written
  as exports show it.
- **alice:** username `alice`, `alice@fau.de`, first name Alice, last name Example, enabled and
  email verified, with no required actions. Her attributes:
  - `eduPersonPrincipalName`: `alice@fau.de`
  - `eduPersonScopedAffiliation`: `member@fau.de`, `staff@fau.de`
  - `schacHomeOrganization`: `fau.de`

  Her password is `$(env:DEMO_USER_PASSWORD)` and is not temporary. Groups, the pre-link and
  `aloysius-admins` come in Phase 3.
- **`DEMO_USER_PASSWORD`:** one generated password shared by every demo user, kept only in
  `.env`. It is 12 hex characters (`openssl rand -hex 6`), short enough to type in a browser
  demo. A new `make secrets` target, run by `init` (`init: .env secrets keys up`), takes over the
  `.env` rule's `sed` fills. For `KC_BOOTSTRAP_ADMIN_PASSWORD` and `POSTGRES_PASSWORD` (24 hex
  bytes) and for `DEMO_USER_PASSWORD`, it fills any value that is empty or missing, including
  in an existing `.env`. It never changes a value that is already set, and never prints one. The
  `.env` rule only copies `.env.example`. Only `keycloak-config` gets the variable, as
  `${DEMO_USER_PASSWORD:?set in .env}`.
- **Test helpers** go in a new `tests/saml.py`, so the next item's broker e2e can reuse them:
  - building an AuthnRequest and encoding it for HTTP-Redirect (DEFLATE, base64, URL-encode)
  - parsing an HTML form's action and hidden inputs (stdlib `html.parser`)
  - decoding a `SAMLResponse` and reading its NameID, Audience, Destination, attributes and
    signature details

  XML is parsed with `ElementTree`, like `signing_certs`, with `# noqa: S314` because it is our
  own Keycloak's output. `admin_token` moves from `test_realm_keys.py` to `tests/conftest.py`.
- **Structural signature check, not cryptographic:** the test checks that the Response and the
  Assertion each carry a `ds:Signature`, and that its `Reference URI` is `#` + the signed
  element's `ID`. It also checks `SignatureMethod` RSA-SHA256, exc-c14n, and that the KeyInfo
  cert equals `HOME_FAU_SAML_CERT`. aloysius verifies the signature cryptographically in the
  next item, so there is no new dependency.

## Scope
- `keycloak/realms/home-fau.json`: the SAML client, its three mappers, the user profile and alice
- `Makefile`: the `secrets` target, `init: .env secrets keys up`, and the `.env` rule reduced to
  a copy
- `.env.example`: `DEMO_USER_PASSWORD=` with a comment
- `docker-compose.yml`: `DEMO_USER_PASSWORD` on `keycloak-config`
- `tests/saml.py` (new), `tests/test_home_fau_idp.py` (new), `tests/conftest.py` (gets
  `admin_token`), `tests/test_realm_keys.py` (imports `admin_token`)
- `docs/product/tech-stack.md`: the demo password in the keypair/secrets text and the
  `tests/saml.py` helpers in the testing section, only where they change. Also, if task 1
  confirms it, the user-profile format note in the config-cli section
- `docs/product/roadmap.md`: tick the item

## Non-goals
- The IdP in `aloysius`, cert trust, attribute importers and account linking (the next item)
- `home-bamberg` (its own item)
- Groups, licences, pinning alice's persistent NameID, and other users (Phase 3)
- Assertion encryption, signed AuthnRequests, SLO and metadata URLs
- Drills and runbooks (Phase 4)

## Acceptance criteria
1. **Static (CI):** `uv run pytest` checks `home-fau.json`:
   - There is exactly one SAML client, and its `clientId` is the aloysius entityID.
   - `redirectUris` equals `[ACS]` and `saml_assertion_consumer_url_post` equals the ACS, with
     no `*`.
   - Response and assertion signing are on, client signature and encryption are off, the
     algorithm is RSA_SHA256 with exc-c14n, and the NameID is persistent and forced.
   - The default and optional client scopes are empty.
   - The three mappers match the table exactly (OID, `URI Reference`, friendly name,
     `aggregate.attrs`), and there are no other mappers.
   - Every mapper's `user.attribute` is declared in the user profile with admin-only `edit`, and
     ePSA is multi-valued.
   - alice's credential is exactly `$(env:DEMO_USER_PASSWORD)`.

   Negative unit tests on synthetic dicts cover:
   - a wildcard ACS
   - a second redirect URI
   - assertion signing off
   - `saml.client.signature` on
   - a transient NameID format
   - a mapper with the `basic` name format
   - a wrong OID
   - a mapper whose attribute isn't declared in the user profile
   - a user-editable attribute
   - a literal password
2. **Live (`e2e`), with alice logging in SP-initiated through HTTP-Redirect and receiving
   HTTP-POST:**
   - The form posts to the ACS. The Response has `Destination` equal to the ACS, a Success
     `StatusCode`, and an `InResponseTo` that matches the request ID.
   - The Assertion's Audience is the aloysius entityID, and its Issuer is
     `http://auth.localhost:8080/realms/home-fau`.
   - The NameID has format `urn:oasis:names:tc:SAML:2.0:nameid-format:persistent`. It isn't
     `alice`, and a second login returns the same value.
   - There are exactly three attributes, each with NameFormat
     `urn:oasis:names:tc:SAML:2.0:attrname-format:uri`, the OID names from the table, and alice's
     values. ePSA comes as one `<Attribute>` with two values.
   - The Response and the Assertion each carry a signature that passes the structural check
     against `HOME_FAU_SAML_CERT`.
3. **Live negatives (`e2e`):**
   - An AuthnRequest with an unknown `Issuer` gets no SAMLResponse; Keycloak shows an error page.
   - An `AssertionConsumerServiceURL` other than the ACS gets no SAMLResponse (invalid redirect
     URI).
   - A wrong password gets the login form again and no SAMLResponse.
   - Unit negatives for the structural check, on a fixture Response, cover:
     - a missing Assertion signature
     - a Reference URI that points at another ID
     - an RSA-SHA1 SignatureMethod
     - a KeyInfo cert other than the pinned one
4. **User profile live (`e2e`):** the admin API `GET /admin/realms/home-fau/users/profile` lists
   the three attributes as admin-edit-only. The admin user record for alice holds all three
   values. A `PUT` that sets an undeclared attribute `foo` is accepted, but `foo` isn't stored.
5. **`make secrets`:**
   - On a fresh copy of `.env.example`, it fills all three passwords.
   - Run again, `.env` is byte-identical (sha256).
   - On an existing `.env` without `DEMO_USER_PASSWORD`, it adds that variable and leaves every
     other value unchanged.
   - No value appears in its output.
6. **Persistence:** after `make reset`, alice can still log in with the same `.env` password, and
   the e2e tests pass.
7. `ruff check`, `ruff format --check`, `mypy` and `pytest` pass, including the parity test with
   `DEMO_USER_PASSWORD`. On the PR, the CI `check` job is green, with the `e2e` and local-`.env`
   tests skipped.

## Realm settings and mappers changed
- `home-fau`:
  - SAML client `http://auth.localhost:8080/realms/aloysius`, configured as in Decisions:
    - exact POST ACS, POST binding forced
    - Response and Assertion signed with RSA_SHA256 and exc-c14n
    - client signature off, no encryption
    - persistent NameID, forced
    - no client scopes, `fullScopeAllowed` false
  - the three `saml-user-attribute-mapper`s from the table
  - user profile: the three attributes declared, admin-only, with scope validators; unmanaged
    attributes stay disabled
  - user `alice` with her three attributes and the demo password
- `home-bamberg`, `aloysius`: none

## New `.env` variables
`DEMO_USER_PASSWORD`: 12 hex characters, filled by `make secrets`, empty in `.env.example`, and
used only by `keycloak-config` (`$(env:DEMO_USER_PASSWORD)` in `home-fau.json`).

## Spec references
- SAML2 Bindings §3.4 (HTTP-Redirect, DEFLATE encoding) for the test's AuthnRequest, and §3.5
  (HTTP-POST) for the auto-submit form with the Response.
- SAML2 Core §3.4.1 (`AssertionConsumerServiceURL`, `Issuer`): the ACS and unknown-SP negatives.
- SAML2 Core §3.2.2 (`Destination`, `InResponseTo`, `StatusCode`).
- SAML2 Core §2.5.1.4 (`AudienceRestriction`): the Audience check.
- SAML2 Core §8.3.7 (persistent NameID: opaque, stable per SP): the format and repeat-login
  checks.
- SAML2 Core §2.7.3 (`AttributeStatement`) and §8.2.2 (`attrname-format:uri`): the attribute
  checks.
- SAML2 Core §5.4.1–5.4.4 (enveloped signature, Reference to the element's ID, exc-c14n) and
  SAML2 Profiles §4.1.3.5 (signed assertion over POST): the structural signature check.
- eduPerson (OIDs `1.3.6.1.4.1.5923.1.1.1.6` and `.9`) and SCHAC (`1.3.6.1.4.1.25178.1.2.9`),
  using the urn:oid naming of the MACE-Dir SAML Attribute Profile.
- OIDC Core and RFC 7636: no checks in this item.
