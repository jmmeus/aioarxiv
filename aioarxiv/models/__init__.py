"""Models module for aioarxiv. Contains base classes, search models, RSS models, and enums."""

from .base import BaseResult
from .search import SearchResult, Search
from .rss import RSSResult
from .enums import SortCriterion, SortOrder, AnnounceType
from .utilities import validate_arxiv_url

__all__ = [
    "BaseResult",
    "SearchResult",
    "Search",
    "RSSResult",
    "SortCriterion",
    "SortOrder",
    "AnnounceType",
    "validate_arxiv_url",
]
