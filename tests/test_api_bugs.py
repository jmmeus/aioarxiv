"""
Tests for work-arounds to known arXiv API bugs.
"""

import aioarxiv
import unittest


class TestAPIBugs(unittest.IsolatedAsyncioTestCase):
    async def test_missing_title(self):
        """
        Papers with the title "0" do not have a title element in the Atom feed.

        It's unclear whether other falsey titles (e.g. "False", "null", or empty
        titles) are allowed by arXiv and are impacted by this bug. This may also
        surface for other expected fields (e.g. author names).

        + GitHub issue: https://github.com/lukasschwab/arxiv.py/issues/71
        + Bug report: https://groups.google.com/u/1/g/arxiv-api/c/ORENISrc5gc
        """
        paper_without_title = "2104.12255v1"
        try:
            async with aioarxiv.Client() as arxivclient:
                results = [
                    r
                    async for r in arxivclient.results(
                        aioarxiv.SearchQuery(id_list=[paper_without_title])
                    )
                ]
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0].get_short_id(), paper_without_title)
        except AttributeError:
            self.fail("got AttributeError fetching paper without title")
