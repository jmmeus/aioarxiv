from __future__ import annotations

import logging
import feedparser
import aiohttp
from yarl import URL
from typing import AsyncGenerator, Optional, Union, cast

from aioarxiv.models import SearchResult, RSSResult, RSSQuery, SearchQuery
from aioarxiv.errors import HTTPError, UnexpectedEmptyPageError
from aioarxiv.rate_limiter import AsyncRateLimiter
from aioarxiv.decorators import refcount_context
from aioarxiv.models.utilities import _classname

logger = logging.getLogger(__name__)

MAX_PAGE_SIZE = 2_000


@refcount_context
class Client(object):
    """
    Specifies a strategy for fetching results from arXiv's API.

    This class obscures pagination and retry logic, and exposes
    `Client.results`.
    """

    query_url_format = "https://export.arxiv.org/api/query?"
    """
    The arXiv query API endpoint format.
    """
    rss_url_format = "https://rss.arxiv.org/{}/{}"
    """
    The arXiv RSS feed API endpoint format.
    """
    page_size: int
    """
    Maximum number of results fetched in a single API request. Smaller pages can
    be retrieved faster, but may require more round-trips.

    The API's limit is 2000 results per page.
    """
    delay_seconds: float
    """
    Number of seconds to wait between API requests.

    [arXiv's Terms of Use](https://arxiv.org/help/api/tou) ask that you "make no
    more than one request every three seconds."
    """
    num_retries: int
    """
    Number of times to retry a failing API request before raising an Exception.
    """
    rate_limiter: AsyncRateLimiter
    """
    An asynchronous rate limiter for API requests.
    """
    _session: aiohttp.ClientSession

    def __init__(self, page_size: int = 100, delay_seconds: float = 3.0, num_retries: int = 3):
        """
        Constructs an arXiv API client with the specified options.

        Note: the default parameters should provide a robust request strategy
        for most use cases. Extreme page sizes, delays, or retries risk
        violating the arXiv [API Terms of Use](https://arxiv.org/help/api/tou),
        brittle behavior, and inconsistent results.
        """
        self.page_size = min(page_size, MAX_PAGE_SIZE)
        self.delay_seconds = delay_seconds
        self.num_retries = num_retries
        self.rate_limiter = AsyncRateLimiter(period=delay_seconds)
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """
        Async context manager entry point to create aiohttp session.
        """
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """
        Async context manager exit point to close aiohttp session.
        """
        if self._session:
            await self._session.close()
            self._session = None

    def __str__(self) -> str:
        # TODO: develop a more informative string representation.
        return repr(self)

    def __repr__(self) -> str:
        return "{}(page_size={}, delay_seconds={}, num_retries={})".format(
            _classname(self),
            repr(self.page_size),
            repr(self.delay_seconds),
            repr(self.num_retries),
        )

    async def results(
        self, query: Union[RSSQuery, SearchQuery], offset: int = 0
    ) -> AsyncGenerator[Union[SearchResult, RSSResult], None]:
        """
        Uses this client configuration to fetch results based on the query type.

        For SearchQuery: Fetches one page at a time, yielding parsed SearchResults
        For RSSQuery: Fetches all results at once (max 2000) and applies offset in memory

        If all tries fail, raises an UnexpectedEmptyPageError or HTTPError.

        Args:
            query: Either an RSSQuery or SearchQuery instance
            offset: Number of results to skip (applied differently for RSS vs Search)

        Returns:
            An async generator yielding either SearchResult or RSSResult instances
        """
        if isinstance(query, RSSQuery):
            # Handle RSS feeds (single request, in-memory offset)
            if offset >= MAX_PAGE_SIZE:
                return

            limit = query.max_results - offset if query.max_results else None
            if limit is not None and limit <= 0:
                return

            async for result in self._rss_results(query, offset, limit):
                yield result
        else:
            # Handle Search API (server-side pagination)
            limit = query.max_results - offset if query.max_results else None
            if limit is not None and limit <= 0:
                return

            async for result in self._search_results(cast(SearchQuery, query), offset, limit):
                yield result

    async def _rss_results(
        self, query: RSSQuery, offset: int, limit: Optional[int]
    ) -> AsyncGenerator[RSSResult, None]:
        """
        Internal method to handle RSS feed results with offset support.
        RSS feeds are fetched in a single request and filtered in memory.
        """
        if not self._session:
            raise RuntimeError("Client session not initialized. Use async context manager.")

        url = self._format_url(query, 0, MAX_PAGE_SIZE)
        print(url)
        feed = await self._parse_feed(url, first_page=True)

        if not feed.entries:
            logger.info("Got empty RSS feed; stopping generation")
            return

        # Apply offset and limit in memory
        entries = feed.entries[offset:]
        if limit is not None:
            entries = entries[:limit]

        for entry in entries:
            try:
                yield RSSResult._from_feed_entry(entry)
            except RSSResult.MissingFieldError as e:
                logger.warning("Skipping partial RSS result: %s", e)

    async def _search_results(
        self, query: SearchQuery, offset: int, limit: Optional[int]
    ) -> AsyncGenerator[SearchResult, None]:
        """
        Internal method to handle Search API results with server-side pagination.
        """
        if not self._session:
            raise RuntimeError("Client session not initialized. Use async context manager.")

        current_offset = offset
        remaining = limit

        while True:
            page_url = self._format_url(query, current_offset, self.page_size)
            feed = await self._parse_feed(page_url, first_page=(current_offset == offset))

            if not feed.entries:
                return

            total_results = int(feed.feed.opensearch_totalresults)

            for entry in feed.entries:
                try:
                    yield SearchResult._from_feed_entry(entry)
                    if remaining is not None:
                        remaining -= 1
                        if remaining <= 0:
                            return
                except SearchResult.MissingFieldError as e:
                    logger.warning("Skipping partial search result: %s", e)

            current_offset += len(feed.entries)
            if current_offset >= total_results:
                break

    def _format_url(self, query: Union[RSSQuery, SearchQuery], start: int, page_size: int) -> str:
        """
        Construct a request URL for the query.

        For RSS queries: Returns the RSS feed URL (ignores pagination params)
        For Search queries: Returns the API URL with pagination parameters
        """
        if isinstance(query, RSSQuery):
            return URL(self.rss_url_format.format(query.feed.lower(), query.query))

        url_args = query._url_args()
        url_args.update(
            {
                "start": start,
                "max_results": page_size,
            }
        )
        return URL(self.query_url_format).with_query(url_args)

    async def _parse_feed(
        self, url: str, first_page: bool = True, _try_index: int = 0
    ) -> feedparser.FeedParserDict:
        """
        Fetches and parses the feed from the specified URL.
        Implements retry logic for failed requests.
        """
        try:
            return await self.__try_parse_feed(url, first_page=first_page, try_index=_try_index)
        except (HTTPError, UnexpectedEmptyPageError, aiohttp.ClientError) as err:
            if _try_index < self.num_retries:
                logger.debug("Got error (try %d): %s", _try_index, err)
                return await self._parse_feed(url, first_page=first_page, _try_index=_try_index + 1)
            logger.debug("Giving up (try %d): %s", _try_index, err)
            raise err

    async def __try_parse_feed(
        self,
        url: str,
        first_page: bool,
        try_index: int,
    ) -> feedparser.FeedParserDict:
        """
        Helper method for _parse_feed that implements rate limiting.
        """
        async with self.rate_limiter.acquire():
            logger.info("Requesting page (first: %r, try: %d): %s", first_page, try_index, url)

            async with self._session.get(url, headers={"user-agent": "aioarxiv/1.1.2"}) as resp:
                if resp.status != 200:
                    raise HTTPError(url, try_index, resp.status)

                content = await resp.content.read()
                feed = feedparser.parse(content)

                if len(feed.entries) == 0 and not first_page:
                    raise UnexpectedEmptyPageError(url, try_index, feed)

                if feed.bozo:
                    logger.warning(
                        "Bozo feed; consider handling: %s",
                        feed.bozo_exception if "bozo_exception" in feed else None,
                    )

                return feed
