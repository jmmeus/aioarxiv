# aioarxiv

[![GitHub Workflow Status (branch)](https://img.shields.io/github/actions/workflow/status/jmmeus/aioarxiv/python-package.yml?branch=master)](https://github.com/jmmeus/aioarxiv/actions?query=branch%3Amaster) [![Full package documentation](https://img.shields.io/badge/docs-hosted-brightgreen)](https://jmmeus.github.io/aioarxiv/aioarxiv.html)

**Asynchronous Python wrapper for the arXiv API**

> **Credit**: Based on the original synchronous [`arxiv.py`](https://github.com/lukasschwab/arxiv.py) by Lukas Schwab

[arXiv](https://arxiv.org/), maintained by the Cornell University Library, provides open access to 1,000,000+ scholarly articles in Physics, Mathematics, Computer Science, Quantitative Biology, Quantitative Finance, and Statistics.

## Features

- Fully asynchronous API interactions
- Efficient, non-blocking arXiv searches
- Support for downloading PDFs and source files
- Access to arXiv's RSS feed
- Flexible search and client configuration

## Installation

### From Git Repository

```bash
$ pip install git+https://github.com/jmmeus/aioarxiv.git
```

### Local Installation

```bash
$ git clone https://github.com/jmmeus/aioarxiv.git
$ cd aioarxiv
$ pip install .
```

## Usage

### Basic Search

```python
import asyncio
import aioarxiv

async def main():
    # Search for the 10 most recent articles matching the keyword "quantum"
    search = aioarxiv.SearchQuery(
        query="quantum",
        max_results=10,
        sort_by=aioarxiv.SortCriterion.SubmittedDate
    )

    # Initialize the asynchronous API client and fetch results asynchronously
    async with aioarxiv.Client() as client:
        results = client.results(search)

        # Results is an AsyncGenerator, we iterate through the elements
        async for result in results:
            print(result.title)
        # ... or exhaust it into a list
        all_results = [r async for r in results]
        print([r.title for r in all_results])

        # Alternatively, we can access the first element using the 
        # `async_iterator.__anext__()` magic method
        first_result = await results.__anext__()
        # ... or for Python >= 3.10 we can use the builtin anext method
        first_result = await anext(results)
        print(first_result.title)

asyncio.run(main())
```

### Advanced Search and Client Configuration

```python
import asyncio
import aioarxiv

async def main():
    # Configure async client with custom parameters
    client = aioarxiv.Client(
        page_size=1000,  # Number of results per page
        delay_seconds=10.0,  # Delay between API requests
        num_retries=5  # Number of retry attempts for failed requests
    )

    async with client as _client:
        # Advanced query searching by author and title
        search = aioarxiv.SearchQuery(query="au:del_maestro AND ti:checkerboard")
        results = _client.results(search)
        first_result = await results.__anext__()
        print(first_result)

        # Search by specific paper ID
        search_by_id = aioarxiv.SearchQuery(id_list=["1605.08386v1"])
        results = _client.results(search_by_id)
        paper = await results.__anext__()
        print(paper.title)

        # Iterate through all results
        search = aioarxiv.SearchQuery(query="quantum", max_results=100)
        async for result in _client.results(search):
            print(result.title)

asyncio.run(main())
```

### Downloading Papers

```python
import asyncio
import aioarxiv

async def main():
    # Initialize the asynchronous API client
    client = aioarxiv.Client()

    # Download a paper by ID
    search = aioarxiv.SearchQuery(id_list=["1605.08386v1"])
    async with client as _client:
        results = _client.results(search)
        paper = await results.__anext__()

        # Download PDF asynchronously
        await paper.download_pdf()
        
        # Download with custom filename and directory
        await paper.download_pdf(
            dirpath="./downloads", 
            filename="quantum-paper.pdf"
        )

        # Download source archive
        await paper.download_source(filename="paper-source.tar.gz")

asyncio.run(main())
```

### RSS Feed Access

The RSS feed provides a faster alternative to sorting results by publication date, though it comes with some trade-offs:
- Limited to newly published papers of only the previous full day (max 2000)
- Contains less metadata per result (e.g. no published/updated timestamps)
- Depends on feed update frequency (once a day at midnight eastern time), making a regular search more reliable for finding the newest papers
- Still supports core functionality like PDF and source downloads

```python
import asyncio
import aioarxiv

async def main():
    client = aioarxiv.Client()

    async with client as _client:
        # Get the most recent entries from the RSS feed using RSSQuery
        feed_query = aioarxiv.RSSQuery(query="astro-ph")
        feed_results = _client.results(feed_query)
        
        # Iterate through feed entries
        async for entry in feed_results:
            # Contains largely the same metadata as search results
            # Also includes announcement type info to filter for
            # only new (not updated or cross-posted) entries
            if entry.announce_type == aioarxiv.AnnounceType.New:
                # Print only info for new publications
                print(entry.entry_id, entry.title, entry.authors)

        # Limit the number of results
        limited_feed = aioarxiv.RSSQuery(query="astro-ph", max_results=5)
        feed_entries = [entry async for entry in _client.results(limited_feed)]

        # Get first entry using anext
        first_entry = await anext(feed_results)
        print(first_entry.title)
        
        # Download PDF and source files just like you would search results
        await first_entry.download_pdf(
            dirpath="./downloads",
            filename="latest-quantum-paper.pdf"
        )
        await first_entry.download_source()

asyncio.run(main())
```

## Logging

Configure logging to inspect network behavior and API interactions:

```python
import logging
import aioarxiv

logging.basicConfig(level=logging.DEBUG)
```

## Types

- `Client`: Configurable async client for fetching results from both arXiv API and RSS feeds
- `BaseQuery`: Base class for queries, not intended to be instantiated by the user
- `SearchQuery`: Defines search parameters for arXiv database queries
- `RSSQuery`: Defines parameters for RSS feed queries
- `BaseResult`: Base class for results, not intended to be instantiated by the user
- `SearchResult`: Represents paper metadata from arXiv API searches with download methods. The meaning of the underlying raw data is documented in the [arXiv API User Manual: Details of Atom Results Returned](https://arxiv.org/help/api/user-manual#_details_of_atom_results_returned)
- `RSSResult`: Represents RSS feed paper metadata with download methods. The meaning of the underlying raw data is documented in the [arXiv info: RSS feed Specifications](https://info.arxiv.org/help/rss_specifications.html)

## Contributing

Contributions are welcome! Please open issues and submit pull requests on the GitHub repository.

## Acknowledgements

This package is an asynchronous reimplementation of the original [`arxiv.py`](https://github.com/lukasschwab/arxiv.py) by Lukas Schwab, designed to provide async capabilities for arXiv API interactions.