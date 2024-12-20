import unittest
from unittest.mock import MagicMock, call, patch, AsyncMock
import aioarxiv
from datetime import datetime, timedelta
from typing import List
from pytest import approx
import aiohttp
import asyncio
import os


def session_with_empty_response(code: int) -> AsyncMock:
    # Create a mock ClientSession
    mock_session = AsyncMock(spec=aiohttp.ClientSession)

    # Create a mock response with 500 status
    mock_response = AsyncMock(spec=aiohttp.ClientResponse)
    mock_response.status = code

    # Create a mock content with read method
    mock_content = AsyncMock()
    mock_content.read = AsyncMock(return_value=b"")
    mock_response.content = mock_content

    # Configure the mock session's get method to return the mock response
    mock_session.get.return_value.__aenter__.return_value = mock_response

    return mock_session


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


class TestClient(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_format_id(self):
        with self.assertRaises(aioarxiv.HTTPError):
            async with aioarxiv.Client(num_retries=0) as _client:
                async for _r in _client.results(aioarxiv.SearchQuery(id_list=["abc"])):
                    pass

    async def test_invalid_id(self):
        async with aioarxiv.Client(num_retries=0) as _client:
            results = [
                r async for r in _client.results(aioarxiv.SearchQuery(id_list=["0000.0000"]))
            ]
            self.assertEqual(len(results), 0)

    async def test_nonexistent_id_in_list(self):
        async with aioarxiv.Client() as client:
            # Assert thrown error is handled and hidden by generator.
            results = [
                r async for r in client.results(aioarxiv.SearchQuery(id_list=["0808.05394"]))
            ]
            self.assertEqual(len(results), 0)
            # Generator should still yield valid entries.
            results = [
                r
                async for r in client.results(
                    aioarxiv.SearchQuery(id_list=["0808.05394", "1707.08567"])
                )
            ]
            self.assertEqual(len(results), 1)

    async def test_invalid_rss_feed(self):
        mock_session = session_with_mock_feed("error")
        async with aioarxiv.Client() as client:
            with patch.object(client, "_session", mock_session):
                # Assert thrown error is handled and hidden by generator.
                results = [r async for r in client.results(aioarxiv.RSSQuery("test"))]
                self.assertEqual(len(results), 0)

    async def test_empty_rss_feed(self):
        # Feeds are empty on weekends + arXiv holidays.
        mock_session = session_with_mock_feed("empty")
        async with aioarxiv.Client() as client:
            with patch.object(client, "_session", mock_session):
                # Assert thrown error is handled and hidden by generator.
                results = [r async for r in client.results(aioarxiv.RSSQuery("test"))]
                self.assertEqual(len(results), 0)

    async def test_max_results(self):
        async with aioarxiv.Client(page_size=10) as client:
            search = aioarxiv.SearchQuery(query="testing", max_results=2)
            results = [r async for r in client.results(search)]
            self.assertEqual(len(results), 2)

    async def test_rss_id_list(self):
        mock_session = session_with_mock_feed("valid")
        desired_ids = ["2411.17700v1", "2411.17701v1", "1901.01108v5"]
        async with aioarxiv.Client() as client:
            with patch.object(client, "_session", mock_session):
                search = aioarxiv.RSSQuery(
                    query="test",
                    id_list=[
                        "2411.17700",
                        "2411.17701",
                        "1901.01108",
                        "2006.09386v2",
                        "2006.09386v2",
                        "2411.15345v1",
                    ],
                )
                result_ids = [r.get_short_id() async for r in client.results(search)]
                self.assertEqual(result_ids, desired_ids)

    async def test_query_page_count(self):
        async with aioarxiv.Client(page_size=10) as client:
            client._parse_feed = MagicMock(wraps=client._parse_feed)
            generator = client.results(aioarxiv.SearchQuery(query="testing", max_results=55))
            results = [r async for r in generator]

            # NOTE: don't directly assert on call count; allow for retries.
            unique_urls = set()
            for parse_call in client._parse_feed.call_args_list:
                args, _kwargs = parse_call
                unique_urls.add(str(args[0]))

            self.assertEqual(len(results), 55)
            self.assertSetEqual(
                unique_urls,
                {
                    "https://export.arxiv.org/api/query?search_query=testing&id_list=&sortBy=relevance&sortOrder=descending&start=0&max_results=10",
                    "https://export.arxiv.org/api/query?search_query=testing&id_list=&sortBy=relevance&sortOrder=descending&start=10&max_results=10",
                    "https://export.arxiv.org/api/query?search_query=testing&id_list=&sortBy=relevance&sortOrder=descending&start=20&max_results=10",
                    "https://export.arxiv.org/api/query?search_query=testing&id_list=&sortBy=relevance&sortOrder=descending&start=30&max_results=10",
                    "https://export.arxiv.org/api/query?search_query=testing&id_list=&sortBy=relevance&sortOrder=descending&start=40&max_results=10",
                    "https://export.arxiv.org/api/query?search_query=testing&id_list=&sortBy=relevance&sortOrder=descending&start=50&max_results=10",
                },
            )

    async def test_offset(self):
        max_results = 10
        search = aioarxiv.SearchQuery(query="testing", max_results=max_results)
        async with aioarxiv.Client(page_size=10) as client:
            default = [r async for r in client.results(search)]
            no_offset = [r async for r in client.results(search)]
            self.assertListEqual(default, no_offset)

            offset = max_results // 2
            half_offset = [r async for r in client.results(search, offset=offset)]
            self.assertListEqual(default[offset:], half_offset)

            offset_above_max_results = [r async for r in client.results(search, offset=max_results)]
            self.assertListEqual(offset_above_max_results, [])

    async def test_rss_offset(self):
        max_results = 10
        mock_session = session_with_mock_feed("valid")
        search = aioarxiv.RSSQuery(query="test", max_results=max_results)
        async with aioarxiv.Client(page_size=10) as client:
            with patch.object(client, "_session", mock_session):
                default = [r async for r in client.results(search)]
                no_offset = [r async for r in client.results(search)]
                self.assertListEqual(default, no_offset)

                offset = max_results // 2
                half_offset = [r async for r in client.results(search, offset=offset)]
                self.assertListEqual(default[offset:], half_offset)

                offset_above_max_results = [
                    r async for r in client.results(search, offset=max_results)
                ]
                self.assertListEqual(offset_above_max_results, [])

    async def test_rss_offset_with_id_list(self):
        max_results = 10
        mock_session = session_with_mock_feed("valid")
        search = aioarxiv.RSSQuery(
            query="test",
            max_results=max_results,
            id_list=[
                "2411.17700",
                "2411.17701",
                "1901.01108",
                "2006.09386",
                "2411.15345",
                "2411.16850",
                "2401.08895",
                "2401.13483",
                "2401.15112",
                "2401.16037",
                "2402.02266",
            ],
        )
        async with aioarxiv.Client(page_size=10) as client:
            with patch.object(client, "_session", mock_session):
                default = [r async for r in client.results(search)]
                no_offset = [r async for r in client.results(search)]
                self.assertListEqual(default, no_offset)

                offset = max_results // 2
                half_offset = [r async for r in client.results(search, offset=offset)]
                self.assertListEqual(default[offset:], half_offset)

                offset_above_max_results = [
                    r async for r in client.results(search, offset=max_results)
                ]
                self.assertListEqual(offset_above_max_results, [])

    async def test_search_results_offset(self):
        # NOTE: page size is irrelevant here.
        async with aioarxiv.Client(page_size=15) as client:
            search = aioarxiv.SearchQuery(query="testing", max_results=10)
            all_results = [r async for r in client.results(search, offset=0)]
            self.assertEqual(len(all_results), 10)

            for offset in [0, 5, 9, 10, 11]:
                client_results = [r async for r in client.results(search, offset=offset)]
                self.assertEqual(len(client_results), max(0, search.max_results - offset))
                if client_results:
                    self.assertEqual(all_results[offset].entry_id, client_results[0].entry_id)

    async def test_rss_results_offset(self):
        # NOTE: page size is irrelevant here.
        mock_session = session_with_mock_feed("valid")
        async with aioarxiv.Client(page_size=15) as client:
            with patch.object(client, "_session", mock_session):
                search = aioarxiv.RSSQuery(query="test", max_results=10)
                all_results = [r async for r in client.results(search, offset=0)]
                self.assertEqual(len(all_results), 10)

                for offset in [0, 5, 9, 10, 11]:
                    client_results = [r async for r in client.results(search, offset=offset)]
                    self.assertEqual(len(client_results), max(0, search.max_results - offset))
                    if client_results:
                        self.assertEqual(all_results[offset].entry_id, client_results[0].entry_id)

    async def test_rss_results_offset_with_id_list(self):
        # NOTE: page size is irrelevant here.
        mock_session = session_with_mock_feed("valid")
        async with aioarxiv.Client(page_size=15) as client:
            with patch.object(client, "_session", mock_session):
                search = aioarxiv.RSSQuery(
                    query="test",
                    max_results=10,
                    id_list=[
                        "2411.17700",
                        "2411.17701",
                        "1901.01108",
                        "2006.09386",
                        "2411.15345",
                        "2411.16850",
                        "2401.08895",
                        "2401.13483",
                        "2401.15112",
                        "2401.16037",
                        "2402.02266",
                    ],
                )
                all_results = [r async for r in client.results(search, offset=0)]
                self.assertEqual(len(all_results), 10)

                for offset in [0, 5, 9, 10, 11]:
                    client_results = [r async for r in client.results(search, offset=offset)]
                    self.assertEqual(len(client_results), max(0, search.max_results - offset))
                    if client_results:
                        self.assertEqual(all_results[offset].entry_id, client_results[0].entry_id)

    async def test_no_duplicates(self):
        search = aioarxiv.SearchQuery("testing", max_results=100)
        ids = set()
        async with aioarxiv.Client() as client:
            async for r in client.results(search):
                self.assertFalse(r.entry_id in ids)
                ids.add(r.entry_id)

    @patch("asyncio.sleep", return_value=None)
    async def test_retry(self, mock_sleep):
        # Create a mock ClientSession
        mock_session = session_with_empty_response(code=500)

        async with aioarxiv.Client() as broken_client:
            # Patch the ClientSession creation in the Client class
            with patch.object(broken_client, "_session", mock_session):

                async def broken_get():
                    search = aioarxiv.SearchQuery(query="quantum")
                    async for r in broken_client.results(search):
                        return r

                with self.assertRaises(aioarxiv.HTTPError):
                    await broken_get()

                for num_retries in [2, 5]:
                    broken_client.num_retries = num_retries
                    try:
                        await broken_get()
                        self.fail("broken_get didn't throw HTTPError")
                    except aioarxiv.HTTPError as e:
                        self.assertEqual(e.status, 500)
                        self.assertEqual(e.retry, broken_client.num_retries)

    @patch("asyncio.sleep", return_value=None)
    async def test_retry_rss_feed(self, mock_sleep):
        # Create a mock ClientSession
        mock_session = session_with_mock_feed("valid", code=500)
        query = aioarxiv.RSSQuery("test")

        async with aioarxiv.Client() as broken_client:
            # Patch the ClientSession creation in the Client class
            with patch.object(broken_client, "_session", mock_session):

                async def broken_get():
                    async for r in broken_client.results(query):
                        return r

                with self.assertRaises(aioarxiv.HTTPError):
                    await broken_get()

                for num_retries in [2, 5]:
                    broken_client.num_retries = num_retries
                    try:
                        await broken_get()
                        self.fail("broken_get didn't throw HTTPError")
                    except aioarxiv.HTTPError as e:
                        self.assertEqual(e.status, 500)
                        self.assertEqual(e.retry, broken_client.num_retries)

    @patch("asyncio.sleep", return_value=None)
    async def test_sleep_standard(self, mock_sleep):
        # Create a mock ClientSession
        mock_session = session_with_empty_response(code=200)

        async with aioarxiv.Client() as client:
            # Patch the ClientSession creation in the Client class
            with patch.object(client, "_session", mock_session):
                url = client._format_url(aioarxiv.SearchQuery(query="quantum"), 0, 1)
                # A client should sleep until delay_seconds have passed.
                await client._parse_feed(url)
                mock_sleep.assert_not_called()
                # Overwrite _last_request_dt to minimize flakiness: different
                # environments will have different page fetch times.
                client.rate_limiter._last_request_dt = datetime.now()
                await client._parse_feed(url)
                mock_sleep.assert_called_once_with(approx(client.delay_seconds, rel=1e-3))

    @patch("asyncio.sleep", return_value=None)
    async def test_sleep_multiple_requests(self, mock_sleep):
        # Create a mock ClientSession
        mock_session = session_with_empty_response(code=200)

        async with aioarxiv.Client() as client:
            # Patch the ClientSession creation in the Client class
            with patch.object(client, "_session", mock_session):
                url1 = client._format_url(aioarxiv.SearchQuery(query="quantum"), 0, 1)
                url2 = client._format_url(aioarxiv.SearchQuery(query="testing"), 0, 1)
                # Rate limiting is URL-independent; expect same behavior as in
                # `test_sleep_standard`.
                await client._parse_feed(url1)
                mock_sleep.assert_not_called()
                client.rate_limiter._last_request_dt = datetime.now()
                await client._parse_feed(url2)
                mock_sleep.assert_called_once_with(approx(client.delay_seconds, rel=1e-3))

    @patch("asyncio.sleep", return_value=None)
    async def test_sleep_elapsed(self, mock_sleep):
        # Create a mock ClientSession
        mock_session = session_with_empty_response(code=200)
        async with aioarxiv.Client() as client:
            # Patch the ClientSession creation in the Client class
            with patch.object(client, "_session", mock_session):
                url = client._format_url(aioarxiv.SearchQuery(query="quantum"), 0, 1)
                # If _last_request_dt is less than delay_seconds ago, sleep.
                client.rate_limiter._last_request_dt = datetime.now() - timedelta(
                    seconds=client.delay_seconds - 1
                )
                await client._parse_feed(url)
                mock_sleep.assert_called_once()
                mock_sleep.reset_mock()
                # If _last_request_dt is at least delay_seconds ago, don't sleep.
                client.rate_limiter._last_request_dt = datetime.now() - timedelta(
                    seconds=client.delay_seconds
                )
                await client._parse_feed(url)
                mock_sleep.assert_not_called()

    @patch("asyncio.sleep", return_value=None)
    async def test_sleep_zero_delay(self, mock_sleep):
        # Create a mock ClientSession
        mock_session = session_with_empty_response(code=200)

        async with aioarxiv.Client(delay_seconds=0) as client:
            # Patch the ClientSession creation in the Client class
            with patch.object(client, "_session", mock_session):
                url = client._format_url(aioarxiv.SearchQuery(query="quantum"), 0, 1)
                await client._parse_feed(url)
                await client._parse_feed(url)
                mock_sleep.assert_not_called()

    @patch("asyncio.sleep", return_value=None)
    async def test_sleep_between_errors(self, mock_sleep):
        # Create a mock ClientSession
        mock_session = session_with_empty_response(code=500)
        async with aioarxiv.Client() as client:
            # Patch the ClientSession creation in the Client class
            with patch.object(client, "_session", mock_session):
                url = client._format_url(aioarxiv.SearchQuery(query="quantum"), 0, 1)
                try:
                    await client._parse_feed(url)
                except aioarxiv.HTTPError:
                    pass
                # Should sleep between retries.
                mock_sleep.assert_called()
                self.assertEqual(mock_sleep.call_count, client.num_retries)
                mock_sleep.assert_has_calls(
                    [
                        call(approx(client.delay_seconds, abs=1e-2)),
                    ]
                    * client.num_retries
                )

    async def test_concurrent_requests_rate_limit(self):
        # Create a mock session that simulates network requests
        mock_session = session_with_empty_response(200)

        async with aioarxiv.Client(delay_seconds=1) as client:
            # Patch the session
            with patch.object(client, "_session", mock_session):
                # Simulate many concurrent requests
                search = aioarxiv.SearchQuery(query="test", max_results=10)

                # List to store request times
                request_times: List[datetime] = []

                async def concurrent_request(i):
                    url = client._format_url(search, i * 10, 10)
                    await client._parse_feed(url)
                    request_times.append(datetime.now())

                # Use a counter to track `asyncio.sleep` calls
                sleep_call_count = 0

                async def wrapped_sleep(seconds):
                    nonlocal sleep_call_count
                    sleep_call_count += 1
                    # Call the original asyncio.sleep
                    await original_sleep(seconds)

                # Access the original asyncio.sleep
                original_sleep = asyncio.sleep

                # Patch asyncio.sleep to monitor calls
                with patch("asyncio.sleep", side_effect=wrapped_sleep):
                    # Run 5 concurrent requests
                    await asyncio.gather(*[concurrent_request(i) for i in range(5)])

                # Verify that requests were properly spaced
                for i in range(1, len(request_times)):
                    time_diff = (request_times[i] - request_times[i - 1]).total_seconds()
                    # Ensure each request is at least 1 second apart
                    self.assertGreaterEqual(
                        time_diff,
                        0.9,  # Allow slight tolerance
                        f"Requests {i-1} and {i} were too close: {time_diff} seconds",
                    )

                # Verify the number of GET requests matches the number of requests
                self.assertEqual(mock_session.get.call_count, 5)

                # Should have slept 4 times
                self.assertEqual(sleep_call_count, 4)

    async def test_live_concurrent_requests(self):
        async with aioarxiv.Client() as client:
            request_times: List[datetime] = []

            async def make_request(query):
                search = aioarxiv.SearchQuery(query=query, max_results=1)
                results = [r async for r in client.results(search)]
                request_times.append(datetime.now())
                return results

            # Perform 3 concurrent requests
            results = await asyncio.gather(
                make_request("quantum physics"),
                make_request("machine learning"),
                make_request("artificial intelligence"),
            )

            # Verify results
            for result_list in results:
                self.assertTrue(len(result_list) > 0)

            # Check timing between requests
            for i in range(1, len(request_times)):
                time_diff = (request_times[i] - request_times[i - 1]).total_seconds()
                self.assertGreaterEqual(
                    time_diff,
                    2.9,  # Allowing slight tolerance under 3 seconds
                    f"Requests {i-1} and {i} were too close: {time_diff} seconds",
                )

    async def test_live_concurrent_rss_feed_requests(self):
        mock_session = session_with_mock_feed("valid")
        async with aioarxiv.Client() as client:
            with patch.object(client, "_session", mock_session):
                request_times: List[datetime] = []

                async def make_request(query):
                    rss_query = aioarxiv.RSSQuery(query)
                    results = [r async for r in client.results(rss_query)]
                    request_times.append(datetime.now())
                    return results

                # Perform 3 concurrent requests
                results = await asyncio.gather(
                    make_request("astro-ph.CO"),
                    make_request("math"),
                    make_request("cs.AI astro-ph.CO"),
                )

                # Verify results
                for result_list in results:
                    self.assertTrue(len(result_list) > 0)

                # Check timing between requests
                for i in range(1, len(request_times)):
                    time_diff = (request_times[i] - request_times[i - 1]).total_seconds()
                    self.assertGreaterEqual(
                        time_diff,
                        2.9,  # Allowing slight tolerance under 3 seconds
                        f"Requests {i-1} and {i} were too close: {time_diff} seconds",
                    )
