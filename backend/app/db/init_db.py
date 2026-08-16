"""Schema creation and first-run seeding."""

from __future__ import annotations

from sqlalchemy import func, select

from app.core.logging import get_logger
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import User  # noqa: F401  (ensures every model is imported)

log = get_logger(__name__)


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("Database schema is up to date (%d tables).", len(Base.metadata.tables))


async def drop_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    log.warning("All tables dropped.")


async def is_seeded() -> bool:
    async with SessionLocal() as session:
        count = (await session.execute(select(func.count(User.id)))).scalar_one()
        return int(count) > 0


async def init_database(seed: bool = True) -> None:
    await create_tables()
    if not seed:
        return
    if await is_seeded():
        log.info("Database already contains data - skipping seed.")
        return

    from app.db.seed import seed_all

    async with SessionLocal() as session:
        await seed_all(session)
