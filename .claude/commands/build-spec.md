---
description: Implement the approved spec task by task, verify end to end and commit
argument-hint: "[optional path to the spec folder]"
---

Implement the tasks.md of the most recent spec in docs/specs/ (or this spec folder, if given:
$ARGUMENTS), one task at a time:

1. Write the test first, then the code. Run `uv run pytest` and `uv run ruff check` after each
   task and tick the task off in tasks.md.
2. Put every Keycloak change into keycloak/realms/ and run `make apply`. Never leave a change
   that exists only in the Admin Console.
3. Add every new environment variable to both .env and .env.example in the same change.
4. When all tasks are done, run `make reset`, log in as alice through home-fau and as carol
   through home-bamberg, and call /api/me, /api/licensed-tool and /api/admin end to end.
   Report the status codes against the users table in the playbook.
5. Check the item off in docs/product/roadmap.md and update docs/product/tech-stack.md if
   anything changed.
6. Commit with a message referencing the spec folder.

If a test fails twice for the same reason, stop and explain what you found instead of
working around it.
