"""Stop an in-flight pipeline run: DB terminal state, Celery revoke, Redis cleanup, fleet teardown."""

from __future__ import annotations

import logging
import os
from typing import Iterable, Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.elttool.models import Log, MigrationRecord, PipelineRun, SourceTableSelection

logger = logging.getLogger(__name__)

_FLOW_REVOKED_MESSAGE = "Flow revoked"

_ACTIVE_LOAD_STATUSES = ("in_progress", "pending", "started", "running", "queued")

_REVOCABLE_RUN_STATUSES = ("queued", "running")


def _collect_run_job_names(run_id: int, nodes_meta: dict) -> set[str]:
    names: set[str] = {f"pipeline_run_{run_id}"}
    prefix = f"pipeline_run_{run_id}"
    for job_name in MigrationRecord.objects.filter(
        job_name__startswith=prefix,
    ).values_list("job_name", flat=True).distinct():
        if job_name:
            names.add(str(job_name))
    for entry in (nodes_meta or {}).values():
        if not isinstance(entry, dict):
            continue
        job = entry.get("pipeline_job_name")
        if job:
            names.add(str(job))
    return names


def _pipeline_run_tables_by_connection(
    pipeline,
    participating_node_ids: list[int],
    *,
    from_migration_rows: dict[int, set[str]] | None = None,
) -> dict[int, set[str]]:
    """All batch table names on participating nodes (+ any tables seen on migration rows)."""
    from apps.elttool.models import PipelineNode

    by_conn: dict[int, set[str]] = {}
    if from_migration_rows:
        for cid, names in from_migration_rows.items():
            by_conn.setdefault(int(cid), set()).update(names)

    if not participating_node_ids:
        return by_conn

    for node in (
        PipelineNode.objects.filter(
            pipeline_id=pipeline.id,
            id__in=participating_node_ids,
        )
        .select_related("batch", "connection")
        .iterator()
    ):
        cid = node.connection_id
        batch = node.batch
        if not cid or not batch:
            continue
        by_conn.setdefault(int(cid), set()).update(
            batch.tables.values_list("table_name", flat=True),
        )
    return by_conn


def _release_tables_after_pipeline_revoke(
    job_prefix: str,
    tables_by_connection: dict[int, set[str]],
    *,
    now,
) -> None:
    """Clear refresh/reload locks so the next pipeline run does not skip these tables."""
    for connection_id, tables in tables_by_connection.items():
        if not tables:
            continue
        table_list = list(tables)
        MigrationRecord.objects.filter(
            connection_id=connection_id,
            table_name__in=table_list,
            job_name__startswith=job_prefix,
            status__in=_ACTIVE_LOAD_STATUSES,
        ).update(status="revoked", updated_at=now)

        for table in table_list:
            other_active = MigrationRecord.objects.filter(
                connection_id=connection_id,
                table_name=table,
                status__in=_ACTIVE_LOAD_STATUSES,
            ).exclude(job_name__startswith=job_prefix)
            if other_active.exists():
                continue
            SourceTableSelection.objects.filter(
                connection_id=connection_id,
                table=table,
                status="in_progress",
            ).update(status=None)


def _purge_job_orchestration_redis(r, job_names: Iterable[str]) -> None:
    pending_prefix = os.getenv(
        "CELERY_FANOUT_PENDING_KEY_PREFIX", "celery:fanout-pending:"
    )
    inflight_prefix = os.getenv(
        "CELERY_FANOUT_INFLIGHT_KEY_PREFIX", "celery:fanout-inflight:"
    )
    for job_name in job_names:
        if not job_name:
            continue
        for key in (
            f"celery:finalizer-ctx:{job_name}",
            f"{pending_prefix}{job_name}",
            f"{inflight_prefix}{job_name}",
            f"celery:fanout-pending:{job_name}",
            f"celery:fanout-inflight:{job_name}",
            f"celery:job-execution-config:{job_name}",
        ):
            try:
                r.delete(key)
            except Exception:
                logger.exception("PIPELINE_REVOKE_REDIS_DELETE_FAILED | key=%s", key)


def revoke_pipeline_run(
    run: PipelineRun,
    *,
    triggered_by_user_id: Optional[int] = None,
) -> dict:
    """
    Mark run ``revoked``, stop open loads, revoke Celery children, purge Redis, teardown fleet.

    Idempotent for runs already terminal (returns without error).
    """
    from apps.elttool.v1.pipeline_views import (
        _pipeline_run_participating_node_ids,
        _teardown_pipeline_flow_fleet,
    )
    from apps.elttool.models import PipelineNode

    run.refresh_from_db(fields=["status", "metadata", "pipeline_id", "finished_at"])
    if run.status not in _REVOCABLE_RUN_STATUSES:
        return {
            "status": "noop",
            "run_status": run.status,
            "message": "Run is not queued or running.",
        }

    run_id = run.id
    job_prefix = f"pipeline_run_{run_id}"
    meta = dict(run.metadata or {})
    nodes = dict(meta.get("nodes") or {})
    session_ids = sorted(
        {
            int(entry.get("migration_session_id"))
            for entry in nodes.values()
            if isinstance(entry, dict) and entry.get("migration_session_id")
        }
    )

    job_filter = Q(job_name__startswith=job_prefix)
    if session_ids:
        job_filter |= Q(migration_session_id__in=session_ids)

    run_mrs = list(
        MigrationRecord.objects.filter(job_name__startswith=job_prefix).values(
            "id",
            "connection_id",
            "table_name",
            "status",
            "task_id",
            "migration_session_id",
            "job_name",
        )
    )
    session_mrs = []
    if session_ids:
        session_mrs = list(
            MigrationRecord.objects.filter(
                migration_session_id__in=session_ids,
                status__in=_ACTIVE_LOAD_STATUSES,
            ).values(
                "id",
                "connection_id",
                "table_name",
                "status",
                "task_id",
                "migration_session_id",
                "job_name",
            )
        )
    mr_by_id: dict[int, dict] = {}
    for row in run_mrs + session_mrs:
        mr_by_id[row["id"]] = row
    mr_rows = list(mr_by_id.values())

    active_mr_ids = [
        row["id"]
        for row in mr_rows
        if (row.get("status") or "").lower() in _ACTIVE_LOAD_STATUSES
    ]

    connection_tables: dict[int, set[str]] = {}
    for row in mr_rows:
        if (row.get("status") or "").lower() != "completed":
            cid = row.get("connection_id")
            table = row.get("table_name")
            if cid and table:
                connection_tables.setdefault(int(cid), set()).add(str(table))

    task_ids = sorted(
        {
            str(row["task_id"]).strip()
            for row in mr_rows
            if row.get("task_id") and (row.get("status") or "").lower() in _ACTIVE_LOAD_STATUSES
        }
    )

    live_nodes = list(PipelineNode.objects.filter(pipeline_id=run.pipeline_id))
    participating_ids = _pipeline_run_participating_node_ids(
        meta,
        run.pipeline,
        live_nodes,
        run_status=run.status,
    )

    now = timezone.now()
    now_iso = now.isoformat()

    with transaction.atomic():
        if active_mr_ids:
            MigrationRecord.objects.filter(id__in=active_mr_ids).update(
                status="revoked",
                updated_at=now,
            )
            Log.objects.filter(
                migration_record_id__in=active_mr_ids,
                status="I",
            ).update(status="E", message=_FLOW_REVOKED_MESSAGE)

        tables_by_connection = _pipeline_run_tables_by_connection(
            run.pipeline,
            list(participating_ids),
            from_migration_rows=connection_tables,
        )
        _release_tables_after_pipeline_revoke(
            job_prefix,
            tables_by_connection,
            now=now,
        )

        participating_keys = {str(nid) for nid in participating_ids}
        for node_id in participating_ids:
            key = str(node_id)
            entry = dict(nodes.get(key) or {})
            if (entry.get("status") or "").lower() == "completed":
                continue
            entry["status"] = "revoked"
            entry["error"] = _FLOW_REVOKED_MESSAGE
            entry["finished_at"] = entry.get("finished_at") or now_iso
            nodes[key] = entry
        for key, entry in list(nodes.items()):
            if not isinstance(entry, dict) or key not in participating_keys:
                continue
            if (entry.get("status") or "").lower() == "completed":
                continue
            entry = dict(entry)
            entry["status"] = "revoked"
            entry["error"] = _FLOW_REVOKED_MESSAGE
            entry["finished_at"] = entry.get("finished_at") or now_iso
            nodes[key] = entry

        meta["nodes"] = nodes
        meta["error"] = None
        meta["failure_pending"] = False
        meta["waiting_for_capacity"] = False
        meta["current_node_id"] = None
        meta["current_node_ids"] = []
        if triggered_by_user_id is not None:
            meta["revoked_by_user_id"] = triggered_by_user_id
        meta["revoked_at"] = now_iso

        run.status = "revoked"
        run.finished_at = now
        run.metadata = meta
        run.save(update_fields=["status", "finished_at", "metadata"])

    job_names = _collect_run_job_names(run_id, nodes)
    try:
        import redis

        url = getattr(settings, "CELERY_BROKER_URL", None) or getattr(
            settings, "REDIS_URL", ""
        )
        if url:
            client = redis.from_url(url, decode_responses=True)
            _purge_job_orchestration_redis(client, job_names)
    except Exception:
        logger.exception("PIPELINE_REVOKE_REDIS_PURGE_FAILED | run=%s", run_id)

    if task_ids:
        try:
            from apps.elttool.services.celery_inspect_service import (
                get_migration_celery_app,
            )

            get_migration_celery_app().control.revoke(
                task_ids,
                terminate=True,
                signal="SIGTERM",
            )
        except Exception:
            logger.exception("PIPELINE_REVOKE_CELERY_FAILED | run=%s", run_id)

    _teardown_pipeline_flow_fleet(run_id)

    try:
        from apps.elttool.services.pipeline_notifications import (
            send_pipeline_flow_notification,
        )

        send_pipeline_flow_notification(run)
    except Exception:
        logger.exception("PIPELINE_REVOKE_NOTIFICATION_FAILED | run=%s", run_id)

    logger.info(
        "PIPELINE_RUN_REVOKED | run=%s | mrs_revoked=%s | tasks=%s",
        run_id,
        len(active_mr_ids),
        len(task_ids),
    )
    return {
        "status": "revoked",
        "run_id": run_id,
        "migration_records_revoked": len(active_mr_ids),
        "tasks_revoked": len(task_ids),
    }
