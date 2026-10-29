# Mission

## Why
A minimal, reproducible demo of an Aloysius-style IAM proxy. One Keycloak realm, `aloysius`, brokers two home-university realms over SAML2, enriches their attributes, and serves a FastAPI app over OIDC with PKCE.

## Audience
- **Me, learning:** build it and understand every hop, message and check.
- **An interviewer:** a walkthrough of about 15 minutes that is correct and that I can explain without notes.

## What it proves
1. **SAML brokering:** `aloysius` acts as SP for `home-fau` and `home-bamberg`, with signed assertions, persistent NameID and account linking (including a pre-linked user).
2. **Protocol translation:** the inner hop is SAML2, and the app sees only OIDC + PKCE.
3. **Attribute enrichment:** eduPerson/SCHAC attributes are imported by their `urn:oid` names. The proxy adds groups, guest status and licences.
4. **Entitlement-based access:** the API decides on token claims. alice, bob, carol and dave each get the expected 200 or 403 on `/api/me`, `/api/licensed-tool` and `/api/admin`.

## Failures it shows and explains
Each failure is reproducible on demand and has a runbook in `docs/runbooks/`.
- **Broker side:** transient NameID (the pre-link is lost and a duplicate user appears); signature or certificate failure; an undeclared attribute dropped by the user profile; a wrong audience or ACS URL.
- **Token side:** missing audience mapper; a forged or alg-confused token; an expired token; a PKCE or state mismatch at `/callback`.

## How it is shown
- **Tests:** unit tests with locally signed tokens, and scripted end-to-end logins through both hops.
- **Browser + SAML-tracer:** a live login showing the AuthnRequest, Response and attributes.
- **Logs:** Keycloak broker/event logs and app logs that explain each decision.
- **Runbooks:** for each failure, the symptom, what to check, the cause and the fix.

## Done when
From a clean clone, `make init` (or `make reset`) plus one test command shows the users table and passes every failure drill, in under 5 minutes.

## Non-goals
- Real DFN-AAI or eduGAIN registration
- A real Shibboleth IdP (Keycloak realms stand in for home IdPs)
- Provisioning between universities (SCIM)
- Any UI beyond Keycloak's own pages; the app returns JSON
- An app database; Postgres is only Keycloak's store

## Stretch goals
- DPoP-bound tokens (RFC 9449): the access token is bound to a client key, so a stolen bearer token can't be replayed.
- Single logout (SAML SLO, OIDC logout): logging out of the app also ends the aloysius and home realm sessions.

## Last priority
Production hardening (TLS, HA, secret management, rate limiting) comes last, if time allows. During development, add only what the browser flow actually needs to work.
