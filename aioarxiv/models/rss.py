from __future__ import annotations

from datetime import datetime
import feedparser
import re
import logging
from typing import Literal, Optional, List

from aioarxiv.models import BaseResult, BaseQuery
from aioarxiv.models.enums import AnnounceType
from aioarxiv.models.utilities import _classname, _to_datetime, _DEFAULT_TIME

logger = logging.getLogger(__name__)

ArXivFeed = Literal["RSS", "ATOM"]


class RSSQuery(BaseQuery):
    """
    A specification to query arXiv's RSS feed.

    To run a query, use `Client.results` with an instantiated client.
    """

    feed: ArXivFeed
    """The feed type to query."""

    def __init__(
        self,
        query: str = "",
        max_results: Optional[int] = None,
        feed: ArXivFeed = "RSS",
    ):
        """
        Constructs an arXiv RSS feed with the specified criteria.
        """
        # Validate that the feed is one of the accepted values
        if feed not in ("RSS", "ATOM"):
            raise ValueError(f"Invalid feed type: {feed}. Must be 'RSS' or 'ATOM'.")

        super().__init__(query=query, max_results=max_results)
        self.feed = feed

    def __repr__(self) -> str:
        return ("{}(query={}, feed={}, max_results={})").format(
            _classname(self),
            repr(self.query),
            repr(self.feed),
            repr(self.max_results),
        )


class RSSResult(BaseResult):
    """
    An entry in an arXiv RSS feed.

    See [the arXiv API User's Manual: RSS feed Specifications
    ](https://info.arxiv.org/help/rss_specifications.html).
    """

    announce_type: AnnounceType
    """
    The type of announcement. Can be one of `AnnounceType.New`, `AnnounceType.Replace`, `AnnounceType.Cross`,
    or `AnnounceType.ReplaceCross`. See [arXiv: ATOM feed Specifications](https://info.arxiv.org/help/atom_specifications.html)
    """
    feed_date: datetime
    """The date this feed was updated. Feeds are updated daily at midnight Eastern Standard Time."""

    def __init__(
        self,
        entry_id: str,
        announce_type: AnnounceType = None,
        feed_date: datetime = _DEFAULT_TIME,
        title: str = "",
        authors: List[BaseResult.Author] = [],
        summary: str = "",
        journal_ref: str = "",
        doi: str = "",
        categories: List[str] = [],
        links: List[BaseResult.Link] = [],
        _raw: feedparser.FeedParserDict = None,
    ):
        """
        Constructs an arXiv RSS feed result item.

        In most cases, prefer using `RSSResult._from_feed_entry` to parsing and
        constructing `RSSResult`s yourself.
        """
        self.announce_type = announce_type
        self.feed_date = feed_date
        super().__init__(
            entry_id=entry_id,
            title=title,
            authors=authors,
            summary=summary,
            journal_ref=journal_ref,
            doi=doi,
            categories=categories,
            links=links,
            _raw=_raw,
        )

    @classmethod
    def _from_feed_entry(cls, entry: feedparser.FeedParserDict) -> RSSResult:
        """
        Converts a feedparser entry for an arXiv RSS feed into a
        BaseResult object.
        """
        title = "0"
        if hasattr(entry, "title"):
            title = entry.title
        else:
            logger.warning("Result %s is missing title attribute; defaulting to '0'", entry.id)
        return cls(
            entry_id=str("https://arxiv.org/abs/" + entry.summary.split(" ", 1)[0])
            if "arxiv:" not in entry.summary.lower()
            else str("https://arxiv.org/abs/" + entry.summary.split(" ", 1)[0][6:]),
            feed_date=_to_datetime(entry.published_parsed),
            title=re.sub(r"\s+", " ", title),
            authors=[cls.Author._from_feed_author(a) for a in entry.authors],
            summary=entry.summary.split("Abstract: ", 1)[-1],
            announce_type=AnnounceType(entry.arxiv_announce_type),
            journal_ref=entry.get("arxiv_journal_ref"),
            doi=entry.get("arxiv_doi"),
            categories=[tag.get("term") for tag in entry.tags],
            links=[cls.Link._from_feed_link(link) for link in entry.links],
            _raw=entry,
        )

    def __repr__(self) -> str:
        return (
            "{}(entry_id={}, feed_date={}, title={}, authors={}, "
            "summary={}, announce_type={}, journal_ref={}, doi={}, "
            "categories={}, links={})"
        ).format(
            _classname(self),
            repr(self.entry_id),
            repr(self.feed_date),
            repr(self.title),
            repr(self.authors),
            repr(self.summary),
            repr(self.announce_type),
            repr(self.journal_ref),
            repr(self.doi),
            repr(self.categories),
            repr(self.links),
        )
