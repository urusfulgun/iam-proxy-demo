# Tasks: CI workflow

Spec: [spec.md](spec.md)

- [x] 1. Resolve the pins: the latest `actions/checkout` and `astral-sh/setup-uv` releases that
      are at least two weeks old, and their commit SHAs (`gh api repos/<owner>/<repo>/git/ref/tags/<tag>`,
      dereferencing annotated tags). Also the latest pip-audit release at least two weeks old.
      Record all three in the build notes.
- [x] 2. Run the pip-audit command locally (`-r -`, falling back to `-r /dev/stdin`). It is
      clean, or a finding is fixed by bumping the lock (AC 2).
- [x] 3. Write `.github/workflows/ci.yml` as the spec describes and run `actionlint` on it
      (AC 1, AC 5).
- [x] 4. Write `.github/dependabot.yml` (github-actions, weekly) (AC 1).
- [x] 5. Run all six commands locally in workflow order on a clean tree: all pass (AC 2).
- [x] 6. Run the negative checks from AC 3 one at a time, reverting each: every command exits
      non-zero (AC 3).
- [x] 7. Update `docs/product/tech-stack.md` (SHA pinning, Dependabot, the exact command) and
      tick the item in `docs/product/roadmap.md`.
- [ ] 8. After the push, the PR's `check` run is green with six separate steps (AC 4).

This item has no access check, so it needs no passing/negative test pair beyond the negative
checks in AC 3. It has no support drill, so it needs no runbook task.

## Notes from the build
- Pins (cutoff 2026-10-15, two weeks before the build):
  - `actions/checkout` v7.0.1 (2026-07-20) = `3d3c42e5aac5ba805825da76410c181273ba90b1`
  - `astral-sh/setup-uv` v10.3.0 (2026-10-09) = `1c37ad07a6a961277cf70c0d37d6f313000f5884`;
    v10.3.1 to v10.3.3 are newer than two weeks
  - pip-audit 2.10.1 (2026-06-10)
- `gh` isn't installed in the devcontainer, so the SHAs came from the public GitHub REST API via
  curl. Both tags pointed straight at commits (no annotated tag to dereference).
- pip-audit 2.10.1 rejects `-r -` ("invalid requirements input: -"), so the workflow uses
  `-r /dev/stdin`, as the spec allowed. tech-stack.md now has the exact command. The audit is
  clean: "No known vulnerabilities found". The `--no-deps` warning about hashes is expected,
  because the export is unhashed by design.
- actionlint 1.7.7 (Docker image) reports 0 errors. The file goes in on stdin, because the Docker
  daemon runs on the host and can't see the devcontainer's paths for a bind mount.
- AC 3: all six negative checks exited 1 and were reverted. They were an unused import, a
  misformatted line, an untyped `def`, a failing assert, `"rich"` added without `uv lock`, and
  `jinja2==3.1.2` (10 known vulnerabilities).
- No Keycloak, `.env` or `/api/*` changes, and the realms aren't wired up yet. So `make reset`
  and the alice/carol e2e login (build-spec step 4) don't apply to this item.
