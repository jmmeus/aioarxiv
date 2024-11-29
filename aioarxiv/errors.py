from __future__ import annotations

import feedparser
from aioarxiv.models.utilities import _classname


class ArxivError(Exception):
    """This package's base Exception class."""

    url: str
    """The feed URL that could not be fetched."""
    retry: int
    """
    The request try number which encountered this error; 0 for the initial try,
    1 for the first retry, and so on.
    """
    message: str
    """Message describing what caused this error."""

    def __init__(self, url: str, retry: int, message: str):
        """
        Constructs an `ArxivError` encountered while fetching the specified URL.
        """
        self.url = url
        self.retry = retry
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        return "{} ({})".format(self.message, self.url)


class UnexpectedEmptyPageError(ArxivError):
    """
    An error raised when a page of results that should be non-empty is empty.

    This should never happen in theory, but happens sporadically due to
    brittleness in the underlying arXiv API; usually resolved by retries.

    See `Client.results` for usage.
    """

    raw_feed: feedparser.FeedParserDict
    """
    The raw output of `feedparser.parse`. Sometimes this contains useful
    diagnostic information, e.g. in 'bozo_exception'.
    """

    def __init__(self, url: str, retry: int, raw_feed: feedparser.FeedParserDict):
        """
        Constructs an `UnexpectedEmptyPageError` encountered for the specified
        API URL after `retry` tries.
        """
        self.url = url
        self.raw_feed = raw_feed
        super().__init__(url, retry, "Page of results was unexpectedly empty")

    def __repr__(self) -> str:
        return "{}({}, {}, {})".format(
            _classname(self), repr(self.url), repr(self.retry), repr(self.raw_feed)
        )


class HTTPError(ArxivError):
    """
    A non-200 status encountered while fetching a page of results.

    See `Client.results` for usage.
    """

    status: int
    """The HTTP status reported by feedparser."""

    def __init__(self, url: str, retry: int, status: int):
        """
        Constructs an `HTTPError` for the specified status code, encountered for
        the specified API URL after `retry` tries.
        """
        self.url = url
        self.status = status
        super().__init__(
            url,
            retry,
            "Page request resulted in HTTP {}".format(self.status),
        )

    def __repr__(self) -> str:
        return "{}({}, {}, {})".format(
            _classname(self), repr(self.url), repr(self.retry), repr(self.status)
        )
