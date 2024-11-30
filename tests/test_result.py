import aioarxiv
import unittest
import re
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from unittest.mock import patch

import aiohttp
import os


def load_mock_feed(filename: str) -> str:
    """
    Load mock RSS feed content from a file in the mock_feeds directory.

    Args:
        filename (str): Name of the file to load

    Returns:
        str: Content of the mock feed file
    """
    path = os.path.join("./tests/mock_feeds/", filename)

    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Mock feed file not found: {path}")
    except Exception as e:
        raise Exception(f"Error loading mock feed file: {e}")


def session_with_mock_feed(feed_type: str = "valid", code: int = 200) -> AsyncMock:
    """
    Create a mock ClientSession that returns content from a mock feed file.

    Args:
        feed_type (str): Type of feed to mock ("valid", "empty", or "error")
        code (int): HTTP status code to return in the mock response

    Returns:
        AsyncMock: Configured mock session
    """
    # Map feed types to filenames
    feed_files = {
        "valid": "rss_mock_feed.xml",
        "empty": "empty_rss_mock_feed.xml",
        "error": "error_rss_mock_feed.xml",
    }

    filename = feed_files.get(feed_type)
    if not filename:
        raise ValueError(
            f"Invalid feed type: {feed_type}. Must be one of {list(feed_files.keys())}"
        )

    # Create a mock ClientSession
    mock_session = AsyncMock(spec=aiohttp.ClientSession)

    # Create a mock response
    mock_response = AsyncMock(spec=aiohttp.ClientResponse)
    mock_response.status = code

    # Load and set the appropriate mock content
    content = load_mock_feed(filename)
    mock_content = AsyncMock()
    mock_content.read = AsyncMock(return_value=content.encode("utf-8"))
    mock_response.content = mock_content

    # Configure the mock session's get method to return the mock response
    mock_session.get.return_value.__aenter__.return_value = mock_response

    return mock_session


class TestResult(unittest.IsolatedAsyncioTestCase):
    client = aioarxiv.Client()

    def assert_nonempty(self, s):
        self.assertIsNotNone(s)
        self.assertNotEqual(s, "")

    def assert_valid_author(self, a: aioarxiv.BaseResult.Author):
        self.assert_nonempty(a.name)

    def assert_valid_link(self, link: aioarxiv.BaseResult.Link):
        self.assert_nonempty(link.href)

    def assert_valid_search_result(self, result: aioarxiv.SearchResult):
        self.assert_nonempty(result.entry_id)
        self.assertIsNotNone(result.updated)
        self.assertIsNotNone(result.published)
        self.assert_nonempty(result.title)
        self.assertNotEqual(len(result.authors), 0)
        for author in result.authors:
            self.assert_valid_author(author)
        self.assert_nonempty(result.summary)
        self.assert_nonempty(result.primary_category)
        self.assertNotEqual(len(result.categories), 0)
        for category in result.categories:
            self.assert_nonempty(category)
        for link in result.links:
            self.assert_valid_link(link)
        self.assert_nonempty(result.pdf_url)

    def assert_valid_rss_result(self, result: aioarxiv.RSSResult):
        self.assert_nonempty(result.entry_id)
        self.assertIsNotNone(result.feed_date)
        self.assert_nonempty(result.title)
        self.assert_nonempty(result.announce_type)
        self.assertNotEqual(len(result.authors), 0)
        for author in result.authors:
            self.assert_valid_author(author)
        self.assert_nonempty(result.summary)
        self.assertNotEqual(len(result.categories), 0)
        for category in result.categories:
            self.assert_nonempty(category)
        for link in result.links:
            self.assert_valid_link(link)
        self.assert_nonempty(result.pdf_url)

    async def test_search_result_shape(self):
        max_results = 100
        search = aioarxiv.SearchQuery("testing", max_results=max_results)
        async with self.client as _client:
            results = [r async for r in _client.results(search)]
            self.assertEqual(len(results), max_results)
            for result in results:
                self.assert_valid_search_result(result)

    async def test_rss_result_shape(self):
        max_results = 100
        mock_session = session_with_mock_feed("valid")
        async with self.client as _client:
            with patch.object(_client, "_session", mock_session):
                query = aioarxiv.RSSQuery("test", max_results=max_results)
                results = [r async for r in _client.results(query)]
                self.assertEqual(len(results), max_results)
                for result in results:
                    self.assert_valid_rss_result(result)

    async def test_from_feed_entry(self):
        async with self.client as _client:
            feed = await _client._parse_feed(
                "https://export.arxiv.org/api/query?search_query=testing"
            )
            feed_entry = feed.entries[0]
            result = aioarxiv.SearchResult._from_feed_entry(feed_entry)
            self.assert_valid_search_result(result)

    async def test_rss_from_feed_entry(self):
        mock_session = session_with_mock_feed("valid")
        async with self.client as _client:
            with patch.object(_client, "_session", mock_session):
                feed = await _client._parse_feed(
                    "https://rss.arxiv.org/rss/testing"  # NOTE: This URL is not used
                )
                feed_entry = feed.entries[0]
                result = aioarxiv.RSSResult._from_feed_entry(feed_entry)
                self.assert_valid_rss_result(result)

    async def test_get_short_id(self):
        result_id = "1707.08567"
        mock_session = session_with_mock_feed("valid")
        async with self.client as _client:
            result = await _client.results(aioarxiv.SearchQuery(id_list=[result_id])).__anext__()
            got = result.get_short_id()
            self.assertTrue(got.startswith(result_id))
            # Should be of form `1707.08567v1`.
            self.assertTrue(re.match(r"^{}v\d+$".format(result_id), got))
            with patch.object(_client, "_session", mock_session):
                result_rss = await _client.results(aioarxiv.RSSQuery("test")).__anext__()
                got_rss = result_rss.get_short_id()
                self.assertTrue(re.match(r"\d{4}\.\d{5}(v\d+)?", got_rss))

    def test_to_datetime(self):
        """Test time.struct_time to datetime conversion."""
        # paper_published and paper_published_parsed correspond to
        # r._raw.published and r._raw.published_parsed for 1605.08386v1. It's
        # critical to the test that they remain equivalent.
        paper_published = "2016-05-26T17:59:46Z"
        paper_published_parsed = time.struct_time((2016, 5, 26, 17, 59, 46, 3, 147, 0))
        expected = datetime(2016, 5, 26, hour=17, minute=59, second=46, tzinfo=timezone.utc)
        actual = aioarxiv.models.utilities._to_datetime(paper_published_parsed)
        self.assertEqual(actual, expected)
        self.assertEqual(actual.strftime("%Y-%m-%dT%H:%M:%SZ"), paper_published)

    def test_eq(self):
        # Results
        id = "some-result"
        result = aioarxiv.BaseResult(entry_id=id)
        self.assertTrue(result == result)
        self.assertTrue(result == aioarxiv.BaseResult(entry_id=id))
        self.assertTrue(aioarxiv.BaseResult(entry_id=id) == result)
        self.assertFalse(result == aioarxiv.BaseResult(entry_id="other"))
        self.assertFalse(result == id)
        # Authors
        name = "some-name"
        author = aioarxiv.BaseResult.Author(name)
        self.assertTrue(author == author)
        self.assertTrue(author == aioarxiv.BaseResult.Author(name))
        self.assertTrue(aioarxiv.BaseResult.Author(name) == author)
        self.assertFalse(author == aioarxiv.BaseResult.Author("other"))
        self.assertFalse(author == id)
        # Links
        href = "some-href"
        link = aioarxiv.BaseResult.Link(href)
        self.assertTrue(link == link)
        self.assertTrue(link == aioarxiv.BaseResult.Link(href))
        self.assertTrue(aioarxiv.BaseResult.Link(href) == link)
        self.assertFalse(link == aioarxiv.BaseResult.Link("other"))
        self.assertFalse(link == id)

    async def test_legacy_ids(self):
        full_legacy_id = "quant-ph/0201082v1"
        async with self.client as _client:
            result = await _client.results(
                aioarxiv.SearchQuery(id_list=[full_legacy_id])
            ).__anext__()
            self.assertEqual(result.get_short_id(), full_legacy_id)
