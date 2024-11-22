# aioarxiv

**Asynchronous Python wrapper for the arXiv API**

> **Credit**: Based on the original synchronous [`arxiv.py`](https://github.com/lukasschwab/arxiv.py) by Lukas Schwab

[arXiv](https://arxiv.org/), maintained by the Cornell University Library, provides open access to 1,000,000+ scholarly articles in Physics, Mathematics, Computer Science, Quantitative Biology, Quantitative Finance, and Statistics.

## Features

- Fully asynchronous API interactions
- Efficient, non-blocking arXiv searches
- Support for downloading PDFs and source files
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
    # Initialise the asyncronous API client.
    client = aioarxiv.Client()

    # Search for the 10 most recent articles matching the keyword "quantum"
    search = aioarxiv.Search(
        query="quantum",
        max_results=10,
        sort_by=aioarxiv.SortCriterion.SubmittedDate
    )

    # Fetch results asynchronously
    async with client as _client:
        results = _client.results(search)

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

### Advanced Search

```python
import asyncio
import aioarxiv

async def main():
    # Initialise the asyncronous API client.
    client = aioarxiv.Client()

    # Advanced query searching by author and title
    search = aioarxiv.Search(query="au:del_maestro AND ti:checkerboard")

    async with client as _client:
        results = _client.results(search)
        first_result = await results.__anext__()
        print(first_result)

        # Search by specific paper ID
        search_by_id = aioarxiv.Search(id_list=["1605.08386v1"])
        results = _client.results(search_by_id)
        paper = await results.__anext__()
        print(paper.title)

asyncio.run(main())
```

### Downloading Papers

```python
import asyncio
import aioarxiv

async def main():
    # Initialise the asyncronous API client.
    client = aioarxiv.Client()

    # Download a paper by ID
    search = aioarxiv.Search(id_list=["1605.08386v1"])
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

### Custom Client Configuration

```python
import asyncio
import aioarxiv

async def main():
    # Configure async client with custom parameters
    big_slow_client = aioarxiv.Client(
        page_size=1000,
        delay_seconds=10.0,
        num_retries=5
    )

    search = aioarxiv.Search(query="quantum")
    async with big_slow_client as _client:
        async for result in _client.results(search):
            print(result.title)

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

- `Client`: Configurable async client for fetching results
- `Search`: Defines search parameters for arXiv database
- `Result`: Represents paper metadata with download methods. The meaning of the underlying raw data is documented in the [arXiv API User Manual: Details of Atom Results Returned](https://arxiv.org/help/api/user-manual#_details_of_atom_results_returned).

## Contributing

Contributions are welcome! Please open issues and submit pull requests on the GitHub repository.

## Acknowledgements

This package is an asynchronous reimplementation of the original [`arxiv.py`](https://github.com/lukasschwab/arxiv.py) by Lukas Schwab, designed to provide async capabilities for arXiv API interactions.