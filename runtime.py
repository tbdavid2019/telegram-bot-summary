"""Helpers for safely calling blocking code from async request handlers."""

import asyncio
from collections.abc import Callable
from functools import partial
from typing import Any


async def run_blocking(function: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    """Run a synchronous function in the default worker thread pool."""
    if kwargs:
        return await asyncio.to_thread(partial(function, *args, **kwargs))
    return await asyncio.to_thread(function, *args)
