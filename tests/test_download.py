import aioarxiv
import os
import shutil
import tempfile
import unittest
import aiohttp


class TestDownload(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = None
        cls.fetched_result = None
        cls.fetched_result_with_slash = None
        cls._client = None
        cls._aiohttp_session = None

    @classmethod
    async def asyncSetUp(self):
        """Async setup method that runs before each test"""
        self._client = aioarxiv.Client()
        self._aiohttp_session = aiohttp.ClientSession()

        # Fetch the test articles
        # Could use anext() here, but it's not available in Python <3.10.
        # https://docs.python.org/3/library/functions.html#anext
        async with self._client as client:
            self.fetched_result = await client.results(
                aioarxiv.Search(id_list=["1605.08386"])
            ).__anext__()
            self.fetched_result_with_slash = await client.results(
                aioarxiv.Search(id_list=["hep-ex/0406020v1"])
            ).__anext__()

        # Create temp directory
        self.temp_dir = tempfile.mkdtemp()

    @classmethod
    async def asyncTearDown(self):
        """Async teardown method that runs after each test"""
        # Clean up temp directory
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

        # Close aiohttp session
        if self._aiohttp_session and not self._aiohttp_session.closed:
            await self._aiohttp_session.close()

    async def test_download_from_query_no_session(self):
        """Test downloading PDF without providing a session"""
        await self.fetched_result.download_pdf(dirpath=self.temp_dir)
        self.assertTrue(
            os.path.exists(
                os.path.join(
                    self.temp_dir,
                    "1605.08386v1.Heat_bath_random_walks_with_Markov_bases.pdf",
                )
            )
        )

        # Regression-tests https://github.com/lukasschwab/arxiv.py/issues/117.
        await self.fetched_result_with_slash.download_pdf(dirpath=self.temp_dir)
        self.assertTrue(
            os.path.exists(
                os.path.join(
                    self.temp_dir,
                    "hep-ex_0406020v1.Sparticle_Reconstruction_at_LHC.pdf",
                )
            )
        )

    async def test_download_from_query_with_session(self):
        """Test downloading PDF with a provided session"""
        async with self._aiohttp_session as session:
            await self.fetched_result.download_pdf(dirpath=self.temp_dir, session=session)
            self.assertTrue(
                os.path.exists(
                    os.path.join(
                        self.temp_dir,
                        "1605.08386v1.Heat_bath_random_walks_with_Markov_bases.pdf",
                    )
                )
            )

            # Regression-tests https://github.com/lukasschwab/arxiv.py/issues/117.
            await self.fetched_result_with_slash.download_pdf(
                dirpath=self.temp_dir, session=session
            )
            self.assertTrue(
                os.path.exists(
                    os.path.join(
                        self.temp_dir,
                        "hep-ex_0406020v1.Sparticle_Reconstruction_at_LHC.pdf",
                    )
                )
            )

    async def test_download_tarfile_from_query_no_session(self):
        """Test downloading source tarfile without providing a session"""
        await self.fetched_result.download_source(dirpath=self.temp_dir)
        self.assertTrue(
            os.path.exists(
                os.path.join(
                    self.temp_dir,
                    "1605.08386v1.Heat_bath_random_walks_with_Markov_bases.tar.gz",
                )
            )
        )

    async def test_download_tarfile_from_query_with_session(self):
        """Test downloading source tarfile with a provided session"""
        async with self._aiohttp_session as session:
            await self.fetched_result.download_source(dirpath=self.temp_dir, session=session)
            self.assertTrue(
                os.path.exists(
                    os.path.join(
                        self.temp_dir,
                        "1605.08386v1.Heat_bath_random_walks_with_Markov_bases.tar.gz",
                    )
                )
            )

    async def test_download_with_custom_slugify_no_session(self):
        """Test downloading with custom filename without providing a session"""
        fn = "custom-filename.extension"
        await self.fetched_result.download_pdf(dirpath=self.temp_dir, filename=fn)
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, fn)))

    async def test_download_with_custom_slugify_with_session(self):
        """Test downloading with custom filename with a provided session"""
        fn = "custom-filename.extension"
        async with self._aiohttp_session as session:
            await self.fetched_result.download_pdf(
                dirpath=self.temp_dir, filename=fn, session=session
            )
            self.assertTrue(os.path.exists(os.path.join(self.temp_dir, fn)))

    async def test_session_reuse(self):
        """Test that the same session can be reused for multiple downloads"""
        async with self._aiohttp_session as session:
            # Download multiple files with the same session
            await self.fetched_result.download_pdf(dirpath=self.temp_dir, session=session)
            await self.fetched_result_with_slash.download_pdf(
                dirpath=self.temp_dir, session=session
            )
            await self.fetched_result.download_source(dirpath=self.temp_dir, session=session)
            await self.fetched_result_with_slash.download_source(
                dirpath=self.temp_dir, session=session
            )

            # Verify all files were downloaded
            self.assertTrue(
                os.path.exists(
                    os.path.join(
                        self.temp_dir,
                        "1605.08386v1.Heat_bath_random_walks_with_Markov_bases.pdf",
                    )
                )
            )
            self.assertTrue(
                os.path.exists(
                    os.path.join(
                        self.temp_dir,
                        "hep-ex_0406020v1.Sparticle_Reconstruction_at_LHC.pdf",
                    )
                )
            )
            self.assertTrue(
                os.path.exists(
                    os.path.join(
                        self.temp_dir,
                        "1605.08386v1.Heat_bath_random_walks_with_Markov_bases.tar.gz",
                    )
                )
            )
            self.assertTrue(
                os.path.exists(
                    os.path.join(
                        self.temp_dir,
                        "hep-ex_0406020v1.Sparticle_Reconstruction_at_LHC.tar.gz",
                    )
                )
            )

    async def test_session_closure_handling(self):
        """Test that the download methods properly handle session closure"""

        # Test with externally provided session that's already closed
        session = aiohttp.ClientSession()
        await session.close()

        with self.assertRaises(RuntimeError):
            await self.fetched_result.download_pdf(dirpath=self.temp_dir, session=session)

        # Test with auto-created session
        await self.fetched_result.download_pdf(
            dirpath=self.temp_dir
        )  # Should create new session internally
