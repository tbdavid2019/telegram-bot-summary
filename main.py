"""Thin compatibility shim forwarding to app.legacy."""

import asyncio

from app.legacy import *  # noqa: F401,F403
from app.legacy import main  # noqa: F401

if __name__ == "__main__":
    asyncio.run(main())
