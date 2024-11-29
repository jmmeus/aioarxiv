import unittest
import asyncio
from typing import Optional, Any
import aioarxiv
from aioarxiv.decorators import refcount_context


@refcount_context
class MockAsyncContextManager:
    def __init__(self):
        self.enter_count = 0
        self.exit_count = 0
        self.should_fail_enter = False
        self.should_fail_exit = False

    async def __aenter__(self):
        self.enter_count += 1
        if self.should_fail_enter:
            raise ValueError("Mock enter failure")
        return self

    async def __aexit__(
        self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]
    ) -> Optional[bool]:
        self.exit_count += 1
        if self.should_fail_exit:
            raise ValueError("Mock exit failure")
        return None


class TestRefCountDecorator(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_context_entries(self):
        """Test multiple concurrent entries only call __aenter__ once"""
        manager = MockAsyncContextManager()

        async def use_context():
            async with manager:
                await asyncio.sleep(0.1)  # Simulate some work

        # Run three concurrent context entries
        await asyncio.gather(use_context(), use_context(), use_context())

        # Verify counts and internal state
        self.assertEqual(manager.enter_count, 1, "Expected single __aenter__ call")
        self.assertEqual(manager.exit_count, 1, "Expected single __aexit__ call")
        self.assertEqual(
            object.__getattribute__(manager, "_refcount_context_count"),
            0,
            "Reference count should be 0 after all contexts exit",
        )
        self.assertIsNone(
            object.__getattribute__(manager, "_refcount_context_value"),
            "Context value should be None after exit",
        )

    async def test_error_handling(self):
        """Test proper cleanup when errors occur during enter/exit"""
        manager = MockAsyncContextManager()
        manager.should_fail_enter = True

        # Test error during enter
        with self.assertRaises(ValueError) as cm:
            async with manager:
                pass
        self.assertEqual(str(cm.exception), "Mock enter failure")

        # Verify cleanup after enter failure
        self.assertEqual(
            object.__getattribute__(manager, "_refcount_context_count"),
            0,
            "Reference count should be 0 after enter failure",
        )
        self.assertIsNone(
            object.__getattribute__(manager, "_refcount_context_value"),
            "Context value should be None after enter failure",
        )

        # Reset and test error during exit
        manager.should_fail_enter = False
        manager.should_fail_exit = True

        with self.assertRaises(ValueError) as cm:
            async with manager:
                pass
        self.assertEqual(str(cm.exception), "Mock exit failure")

        # Verify cleanup after exit failure
        self.assertEqual(
            object.__getattribute__(manager, "_refcount_context_count"),
            0,
            "Reference count should be 0 after exit failure",
        )
        self.assertIsNone(
            object.__getattribute__(manager, "_refcount_context_value"),
            "Context value should be None after exit failure",
        )

    async def test_live_refcount_arxiv(self):
        """Test reference counting with live arXiv API calls"""
        client = aioarxiv.Client()
        result_ids = []

        async def get_results(client: aioarxiv.Client):
            async with client:
                search = aioarxiv.Search("quantum computing", max_results=2)
                results = [r async for r in client.results(search)]
                result_ids.extend([r.get_short_id() for r in results])
                return results

        # Perform concurrent requests with the same client
        results = await asyncio.gather(get_results(client), get_results(client))

        # Verify we got results from both requests
        self.assertEqual(len(results), 2, "Should have results from both concurrent requests")
        for result_list in results:
            self.assertTrue(len(result_list) > 0, "Each request should return results")
            self.assertLessEqual(len(result_list), 2, "Each request should respect max_results=2")

        # Verify client internal state is clean after all operations
        self.assertEqual(
            object.__getattribute__(client, "_refcount_context_count"),
            0,
            "Reference count should be 0 after all contexts exit",
        )
        self.assertIsNone(
            object.__getattribute__(client, "_refcount_context_value"),
            "Context value should be None after all contexts exit",
        )

    async def test_nested_contexts(self):
        """Test nested context manager usage patterns"""
        manager = MockAsyncContextManager()

        async with manager:
            self.assertEqual(manager.enter_count, 1)
            self.assertEqual(object.__getattribute__(manager, "_refcount_context_count"), 1)

            async with manager:
                self.assertEqual(manager.enter_count, 1)
                self.assertEqual(object.__getattribute__(manager, "_refcount_context_count"), 2)

                async with manager:
                    self.assertEqual(manager.enter_count, 1)
                    self.assertEqual(object.__getattribute__(manager, "_refcount_context_count"), 3)

        # Verify final state
        self.assertEqual(manager.enter_count, 1, "Expected single __aenter__ call")
        self.assertEqual(manager.exit_count, 1, "Expected single __aexit__ call")
        self.assertEqual(
            object.__getattribute__(manager, "_refcount_context_count"),
            0,
            "Reference count should be 0 after all contexts exit",
        )
        self.assertIsNone(
            object.__getattribute__(manager, "_refcount_context_value"),
            "Context value should be None after all contexts exit",
        )
