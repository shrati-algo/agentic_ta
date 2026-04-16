"""Async SQLAlchemy engine and session factory.

Consumers should depend on the ``AsyncSessionFactory`` protocol rather
than the concrete ``async_sessionmaker`` so they stay testable.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def build_engine(dsn: str, *, echo: bool = False):  # type: ignore[no-untyped-def]
    """Create the asyncpg/psycopg engine used by the service."""
    return create_async_engine(dsn, echo=echo, future=True)


def build_session_factory(engine) -> async_sessionmaker[AsyncSession]:  # type: ignore[no-untyped-def]
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def transactional_session(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield a session inside a transaction that commits on success,
    rolls back on any raised exception."""
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
