from __future__ import annotations

from datetime import datetime
from typing import Optional
import feedparser
import re
import logging
from typing import List, Dict

from aioarxiv.models import BaseResult, BaseQuery
from aioarxiv.models.enums import SortCriterion, SortOrder
from aioarxiv.models.utilities import _classname, _to_datetime, _DEFAULT_TIME

logger = logging.getLogger(__name__)

class SearchQuery(BaseQuery):
    """
    A specification for a search of arXiv's database.

    To run a query, use `Client.results` with an instantiated client.
    """

    id_list: List[str]
    """
    A list of arXiv article IDs to which to limit the search.

    See [the arXiv API User's
    Manual](https://arxiv.org/help/api/user-manual#search_query_and_id_list)
    for documentation of the interaction between `query` and `id_list`.
    """
    sort_by: SortCriterion
    """The sort criterion for results."""
    sort_order: SortOrder
    """The sort order for results."""

    def __init__(
        self,
        query: str = "",
        id_list: List[str] = [],
        max_results: Optional[int] = None,
        sort_by: SortCriterion = SortCriterion.Relevance,
        sort_order: SortOrder = SortOrder.Descending,
    ):
        """
        Constructs an arXiv API search with the specified criteria.
        """
        super().__init__(query=query, max_results=max_results)
        self.id_list = id_list
        self.sort_by = sort_by
        self.sort_order = sort_order

    def __repr__(self) -> str:
        return ("{}(query={}, id_list={}, max_results={}, sort_by={}, sort_order={})").format(
            _classname(self),
            repr(self.query),
            repr(self.id_list),
            repr(self.max_results),
            repr(self.sort_by),
            repr(self.sort_order),
        )

    def _url_args(self) -> Dict[str, str]:
        """
        Returns a dict of search parameters that should be included in an API
        request for this search.
        """
        return {
            "search_query": self.query,
            "id_list": ",".join(self.id_list),
            "sortBy": self.sort_by.value,
            "sortOrder": self.sort_order.value,
        }

class SearchResult(BaseResult):
    """
    An entry in an arXiv query results feed.

    See [the arXiv API User's Manual: Details of Atom Results
    Returned](https://arxiv.org/help/api/user-manual#_details_of_atom_results_returned).
    """

    updated: datetime
    """When the result was last updated."""
    published: Optional[datetime]
    """When the result was originally published."""
    comment: Optional[str]
    """The authors' comment if present."""
    primary_category: str
    """
    The result's primary arXiv category. See [arXiv: Category
    Taxonomy](https://arxiv.org/category_taxonomy).
    """

    def __init__(
        self,
        entry_id: str,
        updated: datetime = _DEFAULT_TIME,
        published: datetime = _DEFAULT_TIME,
        comment: str = "",
        primary_category: str = "",
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
        Constructs an arXiv search result item.

        In most cases, prefer using `SearchResult._from_feed_entry` to parsing and
        constructing `SearchResult`s yourself.
        """

        self.updated = updated
        self.published = published
        self.comment = comment
        self.primary_category = primary_category
        super().__init__(
            entry_id=entry_id,
            title=title,
            authors=authors,
            summary=summary,
            journal_ref=journal_ref,
            doi=doi,
            categories=categories,
            links=links,
            _raw=_raw
        )

    @classmethod
    def _from_feed_entry(cls, entry: feedparser.FeedParserDict) -> SearchResult:
        """
        Converts a feedparser entry for an arXiv search result feed into a
        SearchResult object.
        """
        if not hasattr(entry, "id"):
            raise cls.MissingFieldError("id")
        # Title attribute may be absent for certain titles. Defaulting to "0" as
        # it's the only title observed to cause this bug.
        # https://github.com/lukasschwab/arxiv.py/issues/71
        # title = entry.title if hasattr(entry, "title") else "0"
        title = "0"
        if hasattr(entry, "title"):
            title = entry.title
        else:
            logger.warning("Result %s is missing title attribute; defaulting to '0'", entry.id)
        return cls(
            entry_id=entry.id,
            updated=_to_datetime(entry.updated_parsed),
            published=_to_datetime(entry.published_parsed),
            title=re.sub(r"\s+", " ", title),
            authors=[cls.Author._from_feed_author(a) for a in entry.authors],
            summary=entry.summary,
            comment=entry.get("arxiv_comment"),
            journal_ref=entry.get("arxiv_journal_ref"),
            doi=entry.get("arxiv_doi"),
            primary_category=entry.arxiv_primary_category.get("term"),
            categories=[tag.get("term") for tag in entry.tags],
            links=[cls.Link._from_feed_link(link) for link in entry.links],
            _raw=entry,
        )

    def __repr__(self) -> str:
        return (
            "{}(entry_id={}, updated={}, published={}, title={}, authors={}, "
            "summary={}, comment={}, journal_ref={}, doi={}, "
            "primary_category={}, categories={}, links={})"
        ).format(
            _classname(self),
            repr(self.entry_id),
            repr(self.updated),
            repr(self.published),
            repr(self.title),
            repr(self.authors),
            repr(self.summary),
            repr(self.comment),
            repr(self.journal_ref),
            repr(self.doi),
            repr(self.primary_category),
            repr(self.categories),
            repr(self.links),
        )
