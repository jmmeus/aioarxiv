"""
Tests for work-arounds to known arXiv API bugs.
"""
import unittest
from typing import Set
import aioarxiv


# ruff: noqa: F401
class TestPackage(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def get_public_classes(module: object) -> Set[str]:
        """
        Get exported classes from module namespace.
        Looks for capitalized names which typically indicate exported classes.
        """
        return {name for name in dir(module) if name[0].isupper()}

    async def test_package_exports(self):
        """Test that the package exports the expected classes."""
        expected = self.get_public_classes(aioarxiv)
        self.assertTrue(expected, "Should export non-empty set of classes; check the helper")
