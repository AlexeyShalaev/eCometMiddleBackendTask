import asyncio
import logging
import os

from scrapper.core import GithubReposScrapper

from src.clickhouse import ClickHouseManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def main() -> None:
    access_token: str = os.getenv("GITHUB_AT", "PLACE_YOUR_TOKEN_FOR_DEV")
    clickhouse_url: str = os.getenv("CLICKHOUSE_URL", "http://localhost:8123")
    clickhouse_user: str | None = os.getenv("CLICKHOUSE_USER")
    clickhouse_password: str | None = os.getenv("CLICKHOUSE_PASSWORD")
    clickhouse_database: str = os.getenv("CLICKHOUSE_DATABASE", "default")

    github_repos_scrapper = GithubReposScrapper(access_token)

    clickhouse_manager = ClickHouseManager(
        clickhouse_url=clickhouse_url,
        clickhouse_user=clickhouse_user,
        clickhouse_password=clickhouse_password,
        clickhouse_database=clickhouse_database,
    )

    await clickhouse_manager.save_repositories(github_repos_scrapper)


if __name__ == "__main__":
    asyncio.run(main())
