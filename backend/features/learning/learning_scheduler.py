"""Learning scheduler — runs the learning engine on a background interval.

Uses asyncio to schedule the learning cycle every LEARNING_INTERVAL_HOURS hours.
Exposes start_scheduler() and stop_scheduler() for FastAPI lifespan hooks.

The scheduler is deliberately lightweight — it runs in the same process as the
FastAPI app (no Celery / Redis required for this POC). For production, replace
with a proper task queue.
"""
from __future__ import annotations

import asyncio
import logging
import os

from features.learning.learning_engine import run_learning_cycle

logger = logging.getLogger("complaintiq.learning.scheduler")

# How often to run the learning cycle (default: every 6 hours)
_INTERVAL_HOURS = float(os.environ.get("LEARNING_INTERVAL_HOURS", "6"))
_INTERVAL_SECS  = _INTERVAL_HOURS * 3600

_task: asyncio.Task | None = None


async def _scheduler_loop() -> None:
    """Background loop: run learning cycle, then sleep."""
    logger.info("Learning scheduler started — interval=%.1fh", _INTERVAL_HOURS)
    while True:
        try:
            await asyncio.sleep(_INTERVAL_SECS)
            logger.info("Learning scheduler: triggering cycle")
            result = await run_learning_cycle()
            logger.info(
                "Learning cycle result: processed=%d signals=%d",
                result.get("processed", 0),
                len(result.get("signals", [])),
            )
        except asyncio.CancelledError:
            logger.info("Learning scheduler loop cancelled")
            break
        except Exception as exc:  # noqa: BLE001
            logger.error("Learning cycle error: %s", exc)
            # Continue running even if a cycle fails
            await asyncio.sleep(60)


def start_scheduler() -> None:
    """Start the background scheduler task. Call from FastAPI startup."""
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_scheduler_loop())
        logger.info("Learning scheduler task created")


def stop_scheduler() -> None:
    """Cancel the background scheduler task. Call from FastAPI shutdown."""
    global _task
    if _task and not _task.done():
        _task.cancel()
        logger.info("Learning scheduler task cancelled")
    _task = None


async def trigger_manual_cycle() -> dict:
    """Manually trigger a learning cycle immediately (used by the API endpoint)."""
    logger.info("Manual learning cycle triggered")
    return await run_learning_cycle()
