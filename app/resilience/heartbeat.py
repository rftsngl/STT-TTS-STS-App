from __future__ import annotations

import asyncio
import contextlib
from typing import Awaitable, Callable


async def _wait_for_pong(
    stop_event: asyncio.Event,
    pong_event: asyncio.Event,
    timeout: float,
) -> bool:
    pong_task = asyncio.create_task(pong_event.wait())
    stop_task = asyncio.create_task(stop_event.wait())
    try:
        done, pending = await asyncio.wait(
            {pong_task, stop_task},
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if pong_task in done:
            return True
        if stop_task in done:
            return False
        return False
    finally:
        for task in (pong_task, stop_task):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


async def run_heartbeat(
    *,
    interval: float,
    timeout: float,
    stop_event: asyncio.Event,
    pong_event: asyncio.Event,
    send_ping: Callable[[], Awaitable[bool]],
    on_timeout: Callable[[], Awaitable[None]],
) -> None:
    if interval <= 0:
        return
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), interval)
            return
        except asyncio.TimeoutError:
            pass

        pong_event.clear()
        sent = await send_ping()
        if not sent:
            continue

        ok = await _wait_for_pong(stop_event, pong_event, timeout)
        if ok:
            pong_event.clear()
            continue
        if stop_event.is_set():
            return
        await on_timeout()
        return
