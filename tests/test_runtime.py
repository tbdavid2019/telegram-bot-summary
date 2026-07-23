import unittest
from unittest.mock import AsyncMock, patch


class RunBlockingTests(unittest.IsolatedAsyncioTestCase):
    async def test_runs_function_in_thread(self):
        from runtime import run_blocking

        with patch("runtime.asyncio.to_thread", new_callable=AsyncMock, return_value="DONE") as to_thread:
            result = await run_blocking(str.upper, "done")

        self.assertEqual("DONE", result)
        to_thread.assert_awaited_once_with(str.upper, "done")
