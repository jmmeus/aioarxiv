import re
from datetime import datetime, timezone
import time
from calendar import timegm

_DEFAULT_TIME = datetime.min


def _classname(o):
    """A helper function for use in __repr__ methods: aioarxiv.BaseResult.Link."""
    return "arxiv.{}".format(o.__class__.__qualname__)


def _to_datetime(ts: time.struct_time) -> datetime:
    """
    Converts a UTC time.struct_time into a time-zone-aware datetime.

    This will be replaced with feedparser functionality [when it becomes
    available](https://github.com/kurtmckee/feedparser/issues/212).
    """
    return datetime.fromtimestamp(timegm(ts), tz=timezone.utc)


def validate_arxiv_url(url: str) -> bool:
    """Validates an arXiv URL based on pre- and post-2007 formats."""
    post2007regex = r"https://arxiv\.org/abs/\d{4}\.\d{5}(v\d+)?"
    pre2007regex = r"https://arxiv\.org/abs/[a-zA-Z0-9_.+-]+/\d{7}(v\d+)?"
    return bool(re.match(post2007regex, url) or re.match(pre2007regex, url))
