from enum import Enum


class AnnounceType(Enum):
    """
    The type of announcement in an arXiv RSS feed.

    See [arXiv: ATOM feed Specifications]
    (https://info.arxiv.org/help/atom_specifications.html).
    """

    New = "new"
    Replace = "replace"
    Cross = "cross"
    ReplaceCross = "replace-cross"


class SortCriterion(Enum):
    """
    A SortCriterion identifies a property by which search results can be
    sorted.

    See [the arXiv API User's Manual: sort order for return
    results](https://arxiv.org/help/api/user-manual#sort).
    """

    Relevance = "relevance"
    LastUpdatedDate = "lastUpdatedDate"
    SubmittedDate = "submittedDate"


class SortOrder(Enum):
    """
    A SortOrder indicates order in which search results are sorted according
    to the specified arxiv.SortCriterion.

    See [the arXiv API User's Manual: sort order for return
    results](https://arxiv.org/help/api/user-manual#sort).
    """

    Ascending = "ascending"
    Descending = "descending"
