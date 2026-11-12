"""Resolve GCP project / GCS bucket for unary GetDownscopedToken."""

from __future__ import annotations

import os
from typing import Tuple


def bucket_from_url(url: str) -> str:
    text = (url or "").strip()
    for prefix in ("gs://", "gcs://"):
        if text.lower().startswith(prefix):
            return text[len(prefix) :].split("/", 1)[0].strip()
    return ""


def resolve_gcp_token_target() -> Tuple[str, str, str]:
    """Return (project_id, bucket_name, object_prefix) from env.

    Preferred names: PROXY_AGENT_GCP_PROJECT / PROXY_AGENT_GCS_BUCKET.
    Batch secrets already ship GCP_PROJECT_ID / GCS_BUCKET_NAME / GCS_BUCKET_URL.
    """
    project_id = (
        os.environ.get("PROXY_AGENT_GCP_PROJECT")
        or os.environ.get("GCP_PROJECT_ID")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or ""
    ).strip()
    bucket_name = (
        os.environ.get("PROXY_AGENT_GCS_BUCKET")
        or os.environ.get("GCS_BUCKET_NAME")
        or bucket_from_url(os.environ.get("GCS_BUCKET_URL") or "")
        or ""
    ).strip()
    object_prefix = (os.environ.get("PROXY_AGENT_GCS_OBJECT_PREFIX") or "").strip()
    return project_id, bucket_name, object_prefix
