from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator

import asyncpg
import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Request

from src.settings import EnvSettings
from src.utils import singleton


@singleton
class Settings(EnvSettings):
    DATABASE_URL: str
    DATABASE_MIN_SIZE: int = 10
    DATABASE_MAX_SIZE: int = 10


@asynccontextmanager
async def get_pg_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    """
    Create a new pool.

    Warning: Use Odyssey or PgBouncer for production.

    Note: You can extend Settings class to add more database settings.

    Docs: https://magicstack.github.io/asyncpg/current/api/index.html#asyncpg.pool.create_pool
    """
    settings = Settings()
    async with asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=settings.DATABASE_MIN_SIZE,
        max_size=settings.DATABASE_MAX_SIZE,
    ) as pool:
        yield pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Создаём пул соединений
    async with get_pg_pool() as pool:
        app.state.pool = pool
        yield


async def get_pg_connection(
    request: Request,
) -> AsyncGenerator[asyncpg.Connection, None]:
    """
    Create a new connection.
    """
    async with request.app.state.pool.acquire() as connection:
        yield connection


async def get_db_version(
    conn: Annotated[asyncpg.Connection, Depends(get_pg_connection)]
):
    return await conn.fetchval("SELECT version()")


def register_routes(app: FastAPI):
    router = APIRouter(prefix="/api")
    router.add_api_route(path="/db_version", endpoint=get_db_version)
    app.include_router(router)


def create_app() -> FastAPI:
    app = FastAPI(title="e-Comet", lifespan=lifespan)
    register_routes(app)
    return app


if __name__ == "__main__":
    uvicorn.run("main:create_app", factory=True, host="0.0.0.0")
