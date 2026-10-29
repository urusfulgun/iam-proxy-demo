---
description: Write the spec and tasks for the next unchecked roadmap item, then stop for review
argument-hint: "[optional roadmap item to pick instead of the next one]"
---

Take the next unchecked item from @docs/product/roadmap.md (or this item, if given: $ARGUMENTS).

Read the existing code, the realm files in keycloak/realms/, docker-compose.yml, the Makefile
and .env.example. Then use the AskUserQuestion tool to resolve any open decisions, with your
recommended option first and a one-line reason.

Write:
- docs/specs/YYYY-MM-DD-<slug>/spec.md: goal, scope, non-goals, acceptance criteria, the realm
  settings and mappers it changes, any new .env variables, and the spec section (SAML2 Core,
  OIDC Core, RFC 7636) each check comes from
- docs/specs/YYYY-MM-DD-<slug>/tasks.md: small, testable tasks with checkboxes; every access
  check has one passing test and one negative test; every support drill has a runbook task
  in docs/runbooks/

Do not write any code or change any other file. Stop and wait for my review.
