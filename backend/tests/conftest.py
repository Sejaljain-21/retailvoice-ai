"""Test configuration.

Environment variables are set *before* the application is imported so that the
cached `Settings` object picks up the test database and the deterministic mock
LLM provider.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

TEST_DB = Path(__file__).resolve().parent / "test_retailvoice.db"

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB.as_posix()}"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["STT_PROVIDER"] = "mock"
os.environ["TTS_PROVIDER"] = "mock"
os.environ["SEED_ON_STARTUP"] = "false"
os.environ["DEBUG"] = "false"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db.init_db import create_tables, drop_tables  # noqa: E402
from app.db.seed import DEMO_PASSWORD, seed_all  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

CUSTOMER_EMAIL = "customer@retailvoice.ai"
ADMIN_EMAIL = "admin@retailvoice.ai"


@pytest.fixture(scope="session", autouse=True)
def prepared_database():
    """Build and seed the test database once for the whole session."""

    async def _prepare() -> None:
        await drop_tables()
        await create_tables()
        async with SessionLocal() as session:
            await seed_all(session)
        await engine.dispose()

    asyncio.run(_prepare())
    yield
    asyncio.run(engine.dispose())
    TEST_DB.unlink(missing_ok=True)


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
async def db():
    async with SessionLocal() as session:
        yield session


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["tokens"]["access_token"]


@pytest.fixture
async def customer_token(client: AsyncClient) -> str:
    return await _login(client, CUSTOMER_EMAIL, DEMO_PASSWORD)


@pytest.fixture
async def admin_token(client: AsyncClient) -> str:
    from app.core.config import settings

    return await _login(client, ADMIN_EMAIL, settings.DEMO_ADMIN_PASSWORD)


@pytest.fixture
def auth(customer_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {customer_token}"}


@pytest.fixture
def admin_auth(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}
