import asyncio
import random
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator


class TokenBucketRateLimiter:
    def __init__(
        self,
        requests_per_period: int,
        period: float,
        concurrency_limit: int | None = None,
        max_tokens_multiplier: int | None = None,
        min_sleep_time: float | None = None,
    ) -> None:
        """
        :param requests_per_period: Максимальное количество запросов за период
        :param period: Период (в секундах) для лимита запросов
        :param concurrency_limit: Максимальное число параллельных запросов (или None)
        :param max_tokens_multiplier: Во сколько раз больше можно накопить токенов (или None — без накопления)
        :param min_sleep_time: Минимальный интервал сна при ожидании токена (или None — без ограничения)
        """
        self._requests_per_period: int = requests_per_period
        self._period: float = period
        self._concurrency_limit: int | None = concurrency_limit
        self._max_tokens_multiplier: int | None = max_tokens_multiplier
        self._min_sleep_time: float | None = min_sleep_time

        self._rate_limit_lock: asyncio.Lock = asyncio.Lock()
        self._last_checked: float = time.monotonic()
        self._available_tokens: float = float(requests_per_period)

        if max_tokens_multiplier is not None:
            self._max_tokens: int = (
                max_tokens_multiplier * requests_per_period
            )  # Позволяет накопить больше токенов

        if concurrency_limit:
            self._concurrency_semaphore: asyncio.Semaphore = asyncio.Semaphore(
                concurrency_limit
            )

    async def _refill_tokens(self) -> None:
        """Пополняет токены с учетом прошедшего времени, если их не хватает."""
        now: float = time.monotonic()
        elapsed_time: float = now - self._last_checked
        self._last_checked = now

        new_tokens: float = (elapsed_time / self._period) * self._requests_per_period

        if self._max_tokens_multiplier is not None:
            self._available_tokens = min(
                self._available_tokens + new_tokens, self._max_tokens
            )
        else:
            self._available_tokens = min(
                self._available_tokens + new_tokens, self._requests_per_period
            )

    @asynccontextmanager
    async def throttle(self) -> AsyncGenerator[None, None]:
        """Контекстный менеджер для ограничения количества запросов."""
        if self._concurrency_limit:
            await self._concurrency_semaphore.acquire()

        # Пополняем токены только если их не хватает
        if self._available_tokens < 1:
            async with self._rate_limit_lock:
                await self._refill_tokens()

            while self._available_tokens < 1:
                sleep_time: float = (1 - self._available_tokens) * (
                    self._period / self._requests_per_period
                )

                if self._min_sleep_time is not None:
                    # Если `min_sleep_time` задан, спим минимум `min_sleep_time`
                    await asyncio.sleep(min(sleep_time, self._min_sleep_time))
                else:
                    # Если `min_sleep_time` не задан, спим столько, сколько нужно
                    await asyncio.sleep(sleep_time)

                await self._refill_tokens()

        # Уменьшаем количество токенов
        self._available_tokens -= 1

        try:
            if self._concurrency_limit and self._concurrency_semaphore.locked():
                # Jitter для разгрузки запросов, если `min_sleep_time` задан
                if self._min_sleep_time is not None:
                    await asyncio.sleep(random.uniform(0, self._min_sleep_time))
            yield
        finally:
            if self._concurrency_limit:
                self._concurrency_semaphore.release()
