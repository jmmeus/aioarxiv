from __future__ import annotations

import logging
import feedparser
import aiohttp
from yarl import URL
from typing import AsyncGenerator, Optional

from aioarxiv.models import SearchResult, RSSResult, Search
from aioarxiv.errors import HTTPError, UnexpectedEmptyPageError
from aioarxiv.rate_limiter import AsyncRateLimiter
from aioarxiv.decorators import refcount_context
from aioarxiv.models.utilities import _classname

logger = logging.getLogger(__name__)


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
        self.page_size = page_size
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

    async def results(self, search: Search, offset: int = 0) -> AsyncGenerator[SearchResult, None]:
        """
        Uses this client configuration to fetch one page of the search results
        at a time, yielding the parsed `SearchResult`s, until `max_results` results
        have been yielded or there are no more search results.

        If all tries fail, raises an `UnexpectedEmptyPageError` or `HTTPError`.

        Setting a nonzero `offset` discards leading records in the result set.
        When `offset` is greater than or equal to `search.max_results`, the full
        result set is discarded.

        For more on using async generators, see
        [Async Generators](https://peps.python.org/pep-0525/).
        """
        limit = search.max_results - offset if search.max_results else None
        if limit and limit < 0:
            return

        async for result in self._results(search, offset):
            if limit is not None:
                limit -= 1
                if limit < 0:
                    break
            yield result

    async def _results(self, search: Search, offset: int = 0) -> AsyncGenerator[SearchResult, None]:
        """
        Internal async method to generate results from arXiv API.
        """
        if not self._session:
            raise RuntimeError("Client session not initialized. Use async context manager.")

        page_url = self._format_url(search, offset, self.page_size)
        feed = await self._parse_feed(page_url, first_page=True)
        if not feed.entries:
            logger.info("Got empty first page; stopping generation")
            return
        total_results = int(feed.feed.opensearch_totalresults)
        logger.info(
            "Got first page: %d of %d total results",
            len(feed.entries),
            total_results,
        )

        while feed.entries:
            for entry in feed.entries:
                try:
                    yield SearchResult._from_feed_entry(entry)
                except SearchResult.MissingFieldError as e:
                    logger.warning("Skipping partial result: %s", e)
            offset += len(feed.entries)
            if offset >= total_results:
                break
            page_url = self._format_url(search, offset, self.page_size)
            feed = await self._parse_feed(page_url, first_page=False)

    def _format_url(self, search: Search, start: int, page_size: int) -> str:
        """
        Construct a request API for search that returns up to `page_size`
        results starting with the result at index `start`.
        """
        url_args = search._url_args()
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
        Fetches the specified URL and parses it with feedparser.

        If a request fails or is unexpectedly empty, retries the request up to
        `self.num_retries` times.
        """
        try:
            return await self.__try_parse_feed(url, first_page=first_page, try_index=_try_index)
        except (
            HTTPError,
            UnexpectedEmptyPageError,
            aiohttp.ClientError,
        ) as err:
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
        Recursive helper for _parse_feed. Enforces `self.delay_seconds`: if that
        number of seconds has not passed since `_parse_feed` was last called,
        sleeps until delay_seconds seconds have passed.
        """
        async with self.rate_limiter.acquire():
            logger.info("Requesting page (first: %r, try: %d): %s", first_page, try_index, url)

            async with self._session.get(url, headers={"user-agent": "aioarxiv/1.1.1"}) as resp:
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

    async def get_feed(
        self, query: str, max_results: int = 2000, feed_type: str = "RSS"
    ) -> AsyncGenerator[RSSResult, None]:
        """
        Fetches results from the specified feed type (RSS or ATOM).

        Args:
            query (str): The query string for the arXiv feed.
            max_results (int): The maximum number of results to return. Defaults to 2000 (the maximum for a feed).
            feed_type (str): The feed type, either 'RSS' or 'ATOM'. Defaults to 'RSS'.

        Returns:
            AsyncGenerator[RSSResult, None]: An async generator of parsed results.
        """
        base_url = "https://rss.arxiv.org"
        if feed_type.upper() == "ATOM":
            feed_url = f"{base_url}/atom/{query}"
        elif feed_type.upper() == "RSS":
            feed_url = f"{base_url}/rss/{query}"
        else:
            raise ValueError("Invalid feed type. Use 'RSS' or 'ATOM'.")

        if max_results and max_results <= 0:
            return

        async for result in self._rss_results(feed_url):
            if max_results is not None:
                max_results -= 1
                if max_results < 0:
                    break
            yield result

    async def _rss_results(self, feed_url: str) -> AsyncGenerator[RSSResult, None]:
        """
        Fetches and parses an RSS or ATOM feed from the given URL.

        Args:
            feed_url (str): The full URL to the RSS/ATOM feed.

        Returns:
            AsyncGenerator[RSSResult, None]: An async generator of parsed results.
        """
        if not self._session:
            raise RuntimeError("Client session not initialized. Use async context manager.")

        page_url = URL(feed_url)
        feed = await self._parse_feed(page_url, first_page=True)
        if not feed.entries:
            logger.info("Got empty first page; stopping generation")
            return

        logger.info(
            "Got RSS feed: %d / 2000 results",
            len(feed.entries),
        )

        for entry in feed.entries:
            try:
                yield RSSResult._from_feed_entry(entry)
            except RSSResult.MissingFieldError as e:
                logger.warning("Skipping partial result: %s", e)
