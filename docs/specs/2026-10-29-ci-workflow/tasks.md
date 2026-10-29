# Tasks: CI workflow

Spec: [spec.md](spec.md)

- [ ] 1. Resolve the pins: the latest `actions/checkout` and `astral-sh/setup-uv` releases that
      are at least two weeks old, and their commit SHAs (`gh api repos/<owner>/<repo>/git/ref/tags/<tag>`,
      dereferencing annotated tags). Also the latest pip-audit release at least two weeks old.
      Record all three in the build notes.
- [ ] 2. Run the pip-audit command locally (`-r -`, falling back to `-r /dev/stdin`). It is
      clean, or a finding is fixed by bumping the lock (AC 2).
- [ ] 3. Write `.github/workflows/ci.yml` as the spec describes and run `actionlint` on it
      (AC 1, AC 5).
- [ ] 4. Write `.github/dependabot.yml` (github-actions, weekly) (AC 1).
- [ ] 5. Run all six commands locally in workflow order on a clean tree: all pass (AC 2).
- [ ] 6. Run the negative checks from AC 3 one at a time, reverting each: every command exits
      non-zero (AC 3).
- [ ] 7. Update `docs/product/tech-stack.md` (SHA pinning, Dependabot, the exact command) and
      tick the item in `docs/product/roadmap.md`.
- [ ] 8. After the push, the PR's `check` run is green with six separate steps (AC 4).

This item has no access check, so it needs no passing/negative test pair beyond the negative
checks in AC 3. It has no support drill, so it needs no runbook task.
