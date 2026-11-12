"""Parse pipeline-run identifiers from MigrationRecord job names."""

from __future__ import annotations

import re

_PIPELINE_RUN_JOB = re.compile(r"^pipeline_run_(\d+)_node_\d+")


def pipeline_run_id_from_job_name(job_name: str | None) -> int | None:
    if not job_name:
        return None
    match = _PIPELINE_RUN_JOB.match(str(job_name).strip())
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None
