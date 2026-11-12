"""Unary GCP token broker env resolution."""

from sap_proxy_agent.unary.gcp_token_env import resolve_gcp_token_target


def test_resolve_prefers_proxy_agent_env(monkeypatch):
    monkeypatch.setenv("PROXY_AGENT_GCP_PROJECT", "proxy-proj")
    monkeypatch.setenv("PROXY_AGENT_GCS_BUCKET", "proxy-bucket")
    monkeypatch.setenv("PROXY_AGENT_GCS_OBJECT_PREFIX", "pref/")
    monkeypatch.setenv("GCP_PROJECT_ID", "ignored")
    monkeypatch.setenv("GCS_BUCKET_NAME", "ignored")
    assert resolve_gcp_token_target() == ("proxy-proj", "proxy-bucket", "pref/")


def test_resolve_falls_back_to_batch_secret_keys(monkeypatch):
    monkeypatch.delenv("PROXY_AGENT_GCP_PROJECT", raising=False)
    monkeypatch.delenv("PROXY_AGENT_GCS_BUCKET", raising=False)
    monkeypatch.delenv("PROXY_AGENT_GCS_OBJECT_PREFIX", raising=False)
    monkeypatch.setenv("GCP_PROJECT_ID", "datasyncher-batch")
    monkeypatch.setenv("GCS_BUCKET_NAME", "meta_data_bucket_ds_batch")
    assert resolve_gcp_token_target() == (
        "datasyncher-batch",
        "meta_data_bucket_ds_batch",
        "",
    )


def test_resolve_bucket_from_gcs_url(monkeypatch):
    monkeypatch.delenv("PROXY_AGENT_GCP_PROJECT", raising=False)
    monkeypatch.delenv("PROXY_AGENT_GCS_BUCKET", raising=False)
    monkeypatch.delenv("GCS_BUCKET_NAME", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj")
    monkeypatch.setenv("GCS_BUCKET_URL", "gcs://meta_data_bucket_ds_batch/")
    assert resolve_gcp_token_target() == (
        "proj",
        "meta_data_bucket_ds_batch",
        "",
    )


def test_resolve_missing_project_and_bucket(monkeypatch):
    for key in (
        "PROXY_AGENT_GCP_PROJECT",
        "PROXY_AGENT_GCS_BUCKET",
        "GCP_PROJECT_ID",
        "GOOGLE_CLOUD_PROJECT",
        "GCS_BUCKET_NAME",
        "GCS_BUCKET_URL",
        "PROXY_AGENT_GCS_OBJECT_PREFIX",
    ):
        monkeypatch.delenv(key, raising=False)
    assert resolve_gcp_token_target() == ("", "", "")
