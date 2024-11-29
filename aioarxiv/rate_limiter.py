from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class AsyncRateLimiter:
    """A rate limiter for async contexts."""

    def __init__(self, calls: int = 1, period: float = 3.0):
        self.calls = calls
        self.period = period
        self.lock = asyncio.Lock()
        self._last_request_dt: Optional[datetime] = None

    @asynccontextmanager
    async def acquire(self):
        """
        Acquires the rate limiter, waiting if necessary.
        Usage:
            async with rate_limiter.acquire():
                # do rate-limited work here
        """
        async with self.lock:
            if self._last_request_dt is not None:
                required = timedelta(seconds=self.period)
                since_last_request = datetime.now() - self._last_request_dt
                if since_last_request < required:
                    to_sleep = (required - since_last_request).total_seconds()
                    logger.info("Sleeping: %f seconds", to_sleep)
                    await asyncio.sleep(to_sleep)
            try:
                yield
            finally:
                self._last_request_dt = datetime.now()
