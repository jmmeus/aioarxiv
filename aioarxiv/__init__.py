"""aioarxiv: A package for interacting with the arXiv API asynchronously."""

from .client import Client
from .errors import ArxivError, UnexpectedEmptyPageError, HTTPError
from .models import (
    BaseResult,
    BaseQuery,
    SearchResult,
    RSSResult,
    SearchQuery,
    RSSQuery,
    SortCriterion,
    SortOrder,
    AnnounceType,
)

__all__ = [
    "Client",
    "ArxivError",
    "UnexpectedEmptyPageError",
    "HTTPError",
    "BaseResult",
    "BaseQuery",
    "SearchResult",
    "RSSResult",
    "SearchQuery",
    "RSSQuery",
    "SortCriterion",
    "SortOrder",
    "AnnounceType",
]
