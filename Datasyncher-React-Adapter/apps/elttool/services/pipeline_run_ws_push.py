"""Debounced WebSocket pushes when a PipelineRun row changes."""

from __future__ import annotations

import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

_DEBOUNCE_SECONDS = 1
_DEBOUNCE_KEY = "pipeline_run_ws_debounce:{run_id}"


def pipeline_run_id_for_migration_session(migration_session_id: int) -> int | None:
    from apps.elttool.models import MigrationRecord
    from apps.elttool.services.pipeline_run_job_names import (
        pipeline_run_id_from_job_name,
    )

    job_name = (
        MigrationRecord.objects.filter(migration_session_id=migration_session_id)
        .exclude(job_name="")
        .values_list("job_name", flat=True)
        .first()
    )
    return pipeline_run_id_from_job_name(job_name)


def schedule_pipeline_run_ws_for_migration_session(migration_session_id: int) -> None:
    run_id = pipeline_run_id_for_migration_session(migration_session_id)
    if not run_id:
        return
    from apps.elttool.models import PipelineRun

    try:
        pipeline_id = (
            PipelineRun.objects.only("pipeline_id")
            .values_list("pipeline_id", flat=True)
            .get(pk=run_id)
        )
    except PipelineRun.DoesNotExist:
        return
    schedule_pipeline_run_ws_push(run_id, pipeline_id)


def schedule_pipeline_run_ws_push(
    run_id: int,
    pipeline_id: int,
    *,
    force: bool = False,
) -> None:
    """Push run detail + list summary to pipeline-run WebSocket groups.

    ``force=True`` bypasses debounce for status transitions (queued→running, terminal).
    """
    debounce_key = _DEBOUNCE_KEY.format(run_id=run_id)
    if not force and cache.get(debounce_key):
        return
    cache.set(debounce_key, "1", timeout=_DEBOUNCE_SECONDS)

    try:
        _push_pipeline_run_ws_updates(run_id, pipeline_id)
    except Exception:
        logger.exception(
            "pipeline_run_ws_push failed | run_id=%s | pipeline_id=%s",
            run_id,
            pipeline_id,
        )
        cache.delete(debounce_key)


def _push_pipeline_run_ws_updates(run_id: int, pipeline_id: int) -> None:
    from apps.elttool.models import PipelineRun
    from apps.elttool.v1.pipeline_views import (
        _build_pipeline_run_detail,
        _build_pipeline_run_summary,
        _display_latest_run_status,
        _get_pipeline_run_metadata,
        pipeline_run_for_list_latest_status,
    )
    from apps.elttool.websocket.ws_utils import (
        push_company_pipeline_status_update,
        push_pipeline_run_status_update,
        push_pipeline_runs_list_update,
    )

    run = PipelineRun.objects.select_related("pipeline", "pipeline__cmp").get(
        pk=run_id,
    )
    detail = _build_pipeline_run_detail(run, include_migration_status=True)
    summary = _build_pipeline_run_summary(
        run,
        reconcile_running=(run.status == "running"),
    )
    push_pipeline_run_status_update(run_id, detail)
    push_pipeline_runs_list_update(pipeline_id, summary)

    list_run = pipeline_run_for_list_latest_status(pipeline_id)
    if list_run and list_run.id == run_id:
        cmp_id = getattr(run.pipeline, "cmp_id", None)
        if cmp_id:
            meta = _get_pipeline_run_metadata(run)
            push_company_pipeline_status_update(
                cmp_id,
                {
                    "pipeline_id": pipeline_id,
                    "pipeline_run_id": run_id,
                    "latest_run_status": _display_latest_run_status(
                        run.status,
                        meta,
                    ),
                },
            )
