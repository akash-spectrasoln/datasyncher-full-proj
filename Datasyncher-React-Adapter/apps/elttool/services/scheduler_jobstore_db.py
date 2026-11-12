"""SQLAlchemy engine options and retry helpers for APScheduler's PostgreSQL job store."""

from __future__ import annotations

import logging
from typing import Callable, TypeVar

from django.conf import settings
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

T = TypeVar("T")


def scheduler_jobstore_engine_options() -> dict:
    """
    Align APScheduler's job-store pool with Django kubernetes DB settings:
    pool_pre_ping, pool_recycle, connect timeout, and TCP keepalives.
    """
    db = settings.DATABASES.get("default", {})
    opts = db.get("OPTIONS", {})
    connect_args = {
        "connect_timeout": int(opts.get("connect_timeout", 10)),
        "keepalives": int(opts.get("keepalives", 1)),
        "keepalives_idle": int(opts.get("keepalives_idle", 30)),
        "keepalives_interval": int(opts.get("keepalives_interval", 10)),
        "keepalives_count": int(opts.get("keepalives_count", 5)),
    }
    conn_max_age = db.get("CONN_MAX_AGE")
    if conn_max_age is None:
        pool_recycle = 300
    else:
        pool_recycle = max(int(conn_max_age), 60)

    return {
        "pool_pre_ping": True,
        "pool_recycle": pool_recycle,
        "connect_args": connect_args,
    }


def dispose_scheduler_jobstore_engine(scheduler) -> None:
    """Drop pooled connections so the next job-store access opens a fresh socket."""
    try:
        store = scheduler._jobstores.get("default")
        engine = getattr(store, "engine", None)
        if engine is not None:
            engine.dispose()
            logger.info("Disposed APScheduler SQLAlchemy job store engine")
    except Exception:
        logger.exception("Failed to dispose APScheduler job store engine")


def with_jobstore_db_retry(scheduler, operation: Callable[[], T], *, context: str) -> T:
    """Run a job-store operation; on stale SSL/DB sockets, dispose pool and retry once."""
    try:
        return operation()
    except OperationalError as exc:
        logger.warning(
            "APScheduler job store DB error (%s): %s — disposing pool and retrying once",
            context,
            exc,
        )
        dispose_scheduler_jobstore_engine(scheduler)
        return operation()
