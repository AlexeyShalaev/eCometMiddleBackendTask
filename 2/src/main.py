import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final, TypeAlias
from zoneinfo import ZoneInfo

from aiohttp import ClientSession, TCPConnector

try:
    from limiter import TokenBucketRateLimiter
except ImportError:  # pragma: nocover
    from .limiter import TokenBucketRateLimiter # Это сделано ради 3 задания, чтобы была монорепность


logger = logging.getLogger(__name__)

GITHUB_API_BASE_URL: Final[str] = "https://api.github.com"
StrDict: TypeAlias = dict[str, Any]


@dataclass
class RepositoryAuthorCommitsNum:
    author: str
    commits_num: int


@dataclass
class Repository:
    name: str
    owner: str
    position: int
    stars: int
    watchers: int
    forks: int
    language: str
    authors_commits_num_today: list[RepositoryAuthorCommitsNum]


class GithubReposScrapper:
    def __init__(
        self,
        access_token: str,
        simultaneous_requests_limit: int = 100,
        requests_per_second_limit: int = 100,
    ) -> None:
        self._simultaneous_requests_limit: int = simultaneous_requests_limit
        self._requests_per_second_limit: int = requests_per_second_limit
        self._connector = TCPConnector(limit=self._simultaneous_requests_limit)
        self._session = ClientSession(
            connector=self._connector,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"Bearer {access_token}",
            },
        )
        self._rate_limiter = TokenBucketRateLimiter(
            requests_per_period=self._requests_per_second_limit,
            period=1.0,
            max_tokens_multiplier=2,
            min_sleep_time=0.1,
        )
        logger.debug(
            "GithubReposScrapper initialized with limits: %d requests/sec, %d concurrent requests",
            requests_per_second_limit,
            simultaneous_requests_limit,
        )

    async def _make_request(
        self, endpoint: str, method: str = "GET", params: StrDict | None = None
    ) -> Any:
        logger.debug("Making request: %s %s", method, endpoint)
        async with self._rate_limiter.throttle():
            async with self._session.request(
                method, f"{GITHUB_API_BASE_URL}/{endpoint}", params=params
            ) as response:
                logger.debug(
                    "Received response: %s %s - Status: %d",
                    method,
                    endpoint,
                    response.status,
                )
                if response.status > 400:
                    raise Exception(f"Failed to fetch data from {endpoint}, status: {response.status}")
                data = await response.json()
                return data

    async def _get_top_repositories(self, limit: int = 100) -> list[StrDict]:
        logger.debug("Fetching top %d repositories", limit)
        data = await self._make_request(
            endpoint="search/repositories",
            params={
                "q": "stars:>1",
                "sort": "stars",
                "order": "desc",
                "per_page": limit,
            },
        )
        return data.get("items", [])

    async def _get_repository_commits(
        self, owner: str, repo: str
    ) -> list[RepositoryAuthorCommitsNum]:
        logger.debug("Fetching commits for repository: %s/%s", owner, repo)

        # Получаем начало последнего календарного дня (00:00 UTC)
        now = datetime.now(tz=ZoneInfo("UTC"))
        since = (now - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        until = now.replace(
            hour=0, minute=0, second=0, microsecond=0
        )  # Сегодня 00:00 UTC

        data = await self._make_request(
            f"repos/{owner}/{repo}/commits",
            params={"since": since.isoformat(), "until": until.isoformat()},
        )
        authors_count = defaultdict(int)

        for commit in data:
            author: str | None = commit["commit"].get("author")
            if author:
                authors_count[author["name"]] += 1

        logger.debug(
            "Found %d authors in repository %s/%s", len(authors_count), owner, repo
        )
        return [
            RepositoryAuthorCommitsNum(author=author, commits_num=count)
            for author, count in authors_count.items()
        ]

    async def _process_repository(self, position: int, repo: StrDict) -> Repository:
        logger.debug(
            "Processing repository #%d: %s/%s",
            position,
            repo["owner"]["login"],
            repo["name"],
        )
        authors_commits: list[RepositoryAuthorCommitsNum] = (
            await self._get_repository_commits(repo["owner"]["login"], repo["name"])
        )
        return Repository(
            name=repo["name"],
            owner=repo["owner"]["login"] if repo["owner"] else "Unknown",
            position=position,
            stars=repo["stargazers_count"],
            watchers=repo["watchers_count"],
            forks=repo["forks_count"],
            language=repo.get("language", "Unknown"),
            authors_commits_num_today=authors_commits,
        )

    async def get_repositories(self) -> list[Repository]:
        logger.debug("Starting to fetch repositories")
        top_repositories: list[StrDict] = await self._get_top_repositories()
        tasks = [
            self._process_repository(pos, repo)
            for pos, repo in enumerate(top_repositories, start=1)
        ]
        results = await asyncio.gather(*tasks)
        logger.debug("Successfully fetched %d repositories", len(results))
        return results

    async def close(self):
        logger.debug("Closing GithubReposScrapper session")
        await self._session.close()


async def main() -> None:
    import os
    import time

    access_token: str | None = (
        os.getenv("GITHUB_AT")
        or "PLACE_YOUR_TOKEN_FOR_DEV"
    )
    scrapper = GithubReposScrapper(access_token)
    try:

        start_time: float = time.perf_counter()
        repos: list[Repository] = await scrapper.get_repositories()
        elapsed_time: float = time.perf_counter() - start_time
        print(f"Elapsed time: {elapsed_time:.2f} seconds")
        for r in repos[:5]:
            print(r)
    except Exception as e:
        print(e)
    finally:
        await scrapper.close()


if __name__ == "__main__":
    asyncio.run(main())
