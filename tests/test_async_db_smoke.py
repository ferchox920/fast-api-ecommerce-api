# tests/test_async_db_smoke.py
import pytest
from sqlalchemy import text

from app.db.session_async import AsyncSessionLocal, run_in_transaction


@pytest.mark.asyncio
async def test_async_engine_executes_simple_query() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_run_in_transaction_commits_successfully() -> None:
    async def _operation(session):
        result = await session.execute(text("SELECT 1"))
        return result.scalar_one()

    value = await run_in_transaction(_operation)
    assert value == 1
