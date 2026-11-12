"""
GCP downscoped access token for on-prem agents (GCS objectUser on a bucket prefix).

Configure via environment (no secrets in source). Preferred names:
  PROXY_AGENT_GCP_PROJECT
  PROXY_AGENT_GCS_BUCKET
  PROXY_AGENT_GCS_OBJECT_PREFIX  (optional, default "")

Batch secrets already ship GCP_PROJECT_ID / GCS_BUCKET_NAME / GCS_BUCKET_URL;
those are used when the PROXY_AGENT_* names are unset.
"""

from __future__ import annotations

import logging

import google.auth
from google.auth import downscoped
from google.auth.credentials import with_scopes_if_required
from google.auth.transport.requests import Request

from sap_proxy_agent.unary.gcp_token_env import resolve_gcp_token_target

logger = logging.getLogger(__name__)

CLOUD_PLATFORM_SCOPE = ("https://www.googleapis.com/auth/cloud-platform",)


def generate_downscoped_token() -> tuple[str, object]:
    project_id, bucket_name, object_prefix = resolve_gcp_token_target()

    if not project_id or not bucket_name:
        raise RuntimeError(
            "GCP project and GCS bucket are not configured. Set "
            "PROXY_AGENT_GCP_PROJECT and PROXY_AGENT_GCS_BUCKET, or "
            "GCP_PROJECT_ID and GCS_BUCKET_NAME."
        )

    source_credentials, _ = google.auth.default(quota_project_id=project_id)
    source_credentials = with_scopes_if_required(
        source_credentials,
        list(CLOUD_PLATFORM_SCOPE),
    )

    available_resource = f"//storage.googleapis.com/projects/_/buckets/{bucket_name}"
    available_permissions = ["inRole:roles/storage.objectUser"]
    expression = (
        "resource.name.startsWith("
        f"'projects/_/buckets/{bucket_name}/objects/{object_prefix}'"
        ")"
    )
    condition = downscoped.AvailabilityCondition(expression=expression)
    rule = downscoped.AccessBoundaryRule(
        available_resource=available_resource,
        available_permissions=available_permissions,
        availability_condition=condition,
    )
    try:
        credentials = downscoped.Credentials(
            source_credentials=source_credentials,
            credential_access_boundary=downscoped.CredentialAccessBoundary(
                rules=[rule]
            ),
        )
    except TypeError:
        credentials = downscoped.Credentials(
            source_credentials=source_credentials,
            rules=(rule,),
        )
    credentials.refresh(Request())
    logger.info(
        "Issued downscoped GCP token for bucket=%s prefix=%r",
        bucket_name,
        object_prefix,
    )
    return credentials.token, credentials.expiry
