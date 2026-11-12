"""
Smoke-check pipeline revoke wiring (run inside Django env / batch django pod).

Usage:
  python manage.py shell < scripts/verify_pipeline_revoke.py
  # or: python scripts/verify_pipeline_revoke.py  (after django.setup)
"""
from __future__ import annotations

import os
import sys

_APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "datasyncher.settings")

import django

django.setup()

from apps.elttool.models import MigrationRecord, PipelineRun
from apps.elttool.tasks.pipeline_tasks import _TERMINAL_RUN_STATUSES
from apps.elttool.v1.pipeline_views import (
    PipelineRunRevokeView,
    _TERMINAL_PIPELINE_RUN_STATUSES,
)
from apps.elttool.v1 import urls as v1_urls
from apps.elttool.services.pipeline_run_revoke_service import (
    _ACTIVE_LOAD_STATUSES,
    _REVOCABLE_RUN_STATUSES,
)

errors: list[str] = []


def check(label: str, ok: bool) -> None:
    print(f"{'OK' if ok else 'FAIL'} | {label}")
    if not ok:
        errors.append(label)


check("'revoked' in PipelineRun.STATUS_CHOICES", "revoked" in dict(PipelineRun.STATUS_CHOICES))
check("'revoked' in MigrationRecord.STATUS_CHOICES", "revoked" in dict(MigrationRecord.STATUS_CHOICES))
check("'revoked' in _TERMINAL_RUN_STATUSES", "revoked" in _TERMINAL_RUN_STATUSES)
check("'revoked' in _TERMINAL_PIPELINE_RUN_STATUSES", "revoked" in _TERMINAL_PIPELINE_RUN_STATUSES)
check("_REVOCABLE_RUN_STATUSES", _REVOCABLE_RUN_STATUSES == ("queued", "running"))
check("revoked not active load", "revoked" not in _ACTIVE_LOAD_STATUSES)

revoke_route = any(
    getattr(p, "name", None) == "pipeline-run-revoke"
    for p in v1_urls.urlpatterns
)
check("URL pipeline-run-revoke registered", revoke_route)
check("PipelineRunRevokeView exists", PipelineRunRevokeView is not None)

print("-" * 60)
if errors:
    print("VERIFY FAILED:", "; ".join(errors))
    sys.exit(1)
print("Pipeline revoke smoke check passed.")
