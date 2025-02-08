import asyncio
import logging
from datetime import datetime

import aiohttp
from aiochclient import ChClient

from scrapper.core import GithubReposScrapper, Repository

logger = logging.getLogger(__name__)


class ClickHouseManager:
    def __init__(
        self,
        clickhouse_url: str = "http://localhost:8123/",
        clickhouse_user: str | None = None,
        clickhouse_password: str | None = None,
        clickhouse_database: str = "default",
    ) -> None:
        self._clickhouse_url: str = clickhouse_url
        self._clickhouse_user: str | None = clickhouse_user
        self._clickhouse_password: str | None = clickhouse_password
        self._clickhouse_database: str = clickhouse_database

    def _create_client(self) -> ChClient:
        logger.debug("Creating ClickHouse client session")
        session = aiohttp.ClientSession()
        return ChClient(
            session,
            url=self._clickhouse_url,
            user=self._clickhouse_user,
            password=self._clickhouse_password,
            database=self._clickhouse_database,
        )

    async def _save_repositories(
        self, client: ChClient, repositories: list[Repository]
    ) -> None:
        if not repositories:
            logger.warning("No repositories to save, skipping ClickHouse insertion")
            return

        now: datetime = datetime.now()
        updated: str = now.strftime("%Y-%m-%d %H:%M:%S")
        current_date: str = now.strftime("%Y-%m-%d")

        # Формируем батчи

        logger.info("Preparing batch insert for %d repositories", len(repositories))

        repo_data: list[tuple] = [
            (
                repo.name,
                repo.owner,
                repo.stars,
                repo.watchers,
                repo.forks,
                repo.language,
                updated,
            )
            for repo in repositories
        ]
        logger.debug("Repository batch prepared with %d entries", len(repo_data))

        position_data: list[tuple] = [
            (current_date, repo.name, repo.position) for repo in repositories
        ]
        logger.debug("Position batch prepared with %d entries", len(position_data))

        author_commit_data: list[tuple] = [
            (current_date, repo.name, author_commit.author, author_commit.commits_num)
            for repo in repositories
            for author_commit in repo.authors_commits_num_today
        ]
        logger.debug(
            "Author commit batch prepared with %d entries", len(author_commit_data)
        )

        # Параллельное выполнение вставок
        tasks = [
            client.execute(
                f"""
                INSERT INTO {self._clickhouse_database}.repositories 
                (name, owner, stars, watchers, forks, language, updated) 
                SETTINGS async_insert=1, wait_for_async_insert=0 
                VALUES
                """,
                *repo_data,
            ),
            client.execute(
                f"""
                INSERT INTO {self._clickhouse_database}.repositories_positions 
                (date, repo, position) 
                SETTINGS async_insert=1, wait_for_async_insert=0 
                VALUES
                """,
                *position_data,
            ),
        ]

        if author_commit_data:
            tasks.append(
                client.execute(
                    f"""
                    INSERT INTO {self._clickhouse_database}.repositories_authors_commits 
                    (date, repo, author, commits_num) 
                    SETTINGS async_insert=1, wait_for_async_insert=0 
                    VALUES
                    """,
                    *author_commit_data,
                )
            )

        await asyncio.gather(*tasks)
        logger.info("All ClickHouse insertions completed successfully")

    async def save_repositories(
        self, github_repos_scrapper: GithubReposScrapper
    ) -> None:
        try:
            repositories: list[Repository] = (
                await github_repos_scrapper.get_repositories()
            )
        except Exception as e:
            logger.error("Failed to fetch repositories: %s", e)
            raise
        else:
            logger.info(f"Fetched {len(repositories)} repositories")
        finally:
            await github_repos_scrapper.close()

        async with self._create_client() as client:
            await self._save_repositories(client, repositories)

        logger.info("All repositories saved to ClickHouse")
