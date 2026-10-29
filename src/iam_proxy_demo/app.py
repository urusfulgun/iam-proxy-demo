from fastapi import FastAPI

app = FastAPI(title="aloysius-app")


@app.get("/health")
def health() -> dict[str, str]:
    # Liveness only: no Keycloak call, so the app's healthcheck never depends on it.
    return {"status": "ok"}
