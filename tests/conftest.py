from functools import cache
from pathlib import Path

import httpx2
import pytest

from tests.envfile import parse_env

ROOT = Path(__file__).resolve().parent.parent
KEYCLOAK = "http://auth.localhost:8080"


@cache
def keycloak_up() -> bool:
    try:
        return httpx2.get(f"{KEYCLOAK}/realms/master", timeout=2).is_success
    except httpx2.HTTPError:
        return False


@pytest.fixture(autouse=True)
def _e2e_needs_keycloak(request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("e2e") and not keycloak_up():
        pytest.skip(f"Keycloak not reachable at {KEYCLOAK}")


@pytest.fixture
def dotenv() -> dict[str, str]:
    """The local `.env`; tests that need it skip in CI."""
    env = ROOT / ".env"
    if not env.exists():
        pytest.skip("no .env (CI)")
    return parse_env(env.read_text())
