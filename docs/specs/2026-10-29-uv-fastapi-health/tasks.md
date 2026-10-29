# Tasks: uv project on Python 3.14 with a FastAPI `/health` route

Spec: [spec.md](spec.md)

- [ ] 1. Add `fastapi` and `uvicorn` to `dependencies` and a `dev` group (`pytest`, `httpx`) to
      `pyproject.toml`, and set the description. Run `uv lock && uv sync`, then check the pinned
      versions in `uv.lock` (AC 1).
- [ ] 2. Write `tests/test_health.py` with `test_health_ok` (200, `{"status": "ok"}`) and
      `test_health_rejects_post` (405). Run `uv run pytest` and confirm it fails because there
      is no app yet.
- [ ] 3. Add `src/iam_proxy_demo/app.py` with `GET /health`. `uv run pytest` passes (AC 2).
- [ ] 4. Replace the hello-world `main()` with `uvicorn.run("iam_proxy_demo.app:app",
      host="0.0.0.0", port=8000)`. Start it with `uv run iam-proxy-demo` and check
      `curl -s localhost:8000/health` (AC 3).
- [ ] 5. Run `uv run ruff check`, `ruff format --check` and `mypy --strict src tests`; all clean (AC 4).
- [ ] 6. Tick the item in `docs/product/roadmap.md`, and check that the versions in
      `docs/product/tech-stack.md` still match `uv.lock`.

This item has no access check, so it needs no passing/negative test pair, and no support
drill, so it needs no runbook task.
