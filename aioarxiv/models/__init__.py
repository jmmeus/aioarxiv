"""Models module for aioarxiv. Contains base classes, search models, RSS models, and enums."""

from .base import BaseResult, BaseQuery
from .search import SearchResult, SearchQuery
from .rss import RSSResult, RSSQuery
from .enums import SortCriterion, SortOrder, AnnounceType
from .utilities import validate_arxiv_url

__all__ = [
    "BaseResult",
    "BaseQuery",
    "SearchResult",
    "SearchQuery",
    "RSSResult",
    "RSSQuery",
    "SortCriterion",
    "SortOrder",
    "AnnounceType",
    "validate_arxiv_url",
]
