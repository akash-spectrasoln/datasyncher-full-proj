"""Celery dispatch for SAP OData source listing (Update Schema)."""

import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

FAST_API_DIR = Path(__file__).resolve().parents[1]
if str(FAST_API_DIR) not in sys.path:
    sys.path.insert(0, str(FAST_API_DIR))


def test_dispatch_sap_odata_listing_tables(monkeypatch):
    import importlib

    seen = {}

    def fake_discover(connection_id, credentials, job_name):
        seen["connection_id"] = connection_id
        seen["credentials"] = credentials
        seen["job_name"] = job_name
        return {
            "status_code": 200,
            "message": "Successfully discovered and registered 3 OData entities.",
        }

    real_import_module = importlib.import_module

    def fake_import_module(name):
        if name == "services.sap.client":

            class Mod:
                discover_and_populate_sap_odata_service = staticmethod(fake_discover)

            return Mod
        return real_import_module(name)

    monkeypatch.setattr("celery_worker.importlib.import_module", fake_import_module)
    from celery_worker import _dispatch_direct_connector

    result = _dispatch_direct_connector(
        "/SAPOData-listing-tables",
        {
            "connection_id": 42,
            "job_name": "sap_listing_tables_42",
            "SAPOData": {"host": "sap.example.com", "username": "user"},
        },
    )
    assert result["status_code"] == 200
    assert seen["connection_id"] == 42
    assert seen["job_name"] == "sap_listing_tables_42"
    assert seen["credentials"]["host"] == "sap.example.com"


def test_cloud_function_url_sap_odata_listing_mapped():
    app_py = Path(__file__).resolve().parents[1] / "app.py"
    text = app_py.read_text(encoding="utf-8")
    assert "'/SAPOData-listing-tables': get_api_url('SAPOData-listing-tables')" in text
    assert "'/SAPOData-listing-tables': 'sap_odata_listing'" in text


def test_sap_proxy_listing_uses_http_not_in_process_direct(monkeypatch):
    import celery_worker

    monkeypatch.setattr(celery_worker, "CELERY_DIRECT_CONNECTOR_EXECUTION", True)
    direct_calls = []

    def fake_dispatch(function_path, payload):
        direct_calls.append(function_path)
        return {"status_code": 200}

    def fake_post(url, **kwargs):
        class Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"status_code": 200, "message": "ok"}

        fake_post.last_url = url
        fake_post.last_payload = kwargs.get("json")
        return Resp()

    monkeypatch.setattr(celery_worker, "_dispatch_direct_connector", fake_dispatch)
    monkeypatch.setattr(celery_worker.requests, "post", fake_post)
    monkeypatch.setenv("INTERNAL_API_KEY", "test-internal-key")

    payload = {
        "function_path": "/SAPOData-listing-tables",
        "connection_id": 102,
        "job_name": "sap_texx_listing_tables_test",
        "SAPOData": {"connection_method": "proxy", "proxy_agent": "cust-1", "host": "sap.example.com"},
    }
    celery_worker._execute_connector(
        "http://migration-function-svc:8001/SAPOData-listing-tables",
        payload,
        {},
    )
    assert direct_calls == []
    assert fake_post.last_url.endswith("SAPOData-listing-tables")


def test_sap_direct_listing_still_uses_in_process_direct(monkeypatch):
    import celery_worker

    monkeypatch.setattr(celery_worker, "CELERY_DIRECT_CONNECTOR_EXECUTION", True)
    direct_calls = []

    def fake_dispatch(function_path, payload):
        direct_calls.append(function_path)
        return {"status_code": 200}

    monkeypatch.setattr(celery_worker, "_dispatch_direct_connector", fake_dispatch)
    monkeypatch.setattr(
        celery_worker.requests,
        "post",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("HTTP should not be used")),
    )

    payload = {
        "function_path": "/SAPOData-listing-tables",
        "SAPOData": {"connection_method": "direct", "host": "sap.example.com"},
    }
    celery_worker._execute_connector("http://unused", payload, {})
    assert direct_calls == ["/SAPOData-listing-tables"]


def test_sap_proxy_migration_uses_http_not_in_process_direct(monkeypatch):
    import celery_worker

    monkeypatch.setattr(celery_worker, "CELERY_DIRECT_CONNECTOR_EXECUTION", True)
    direct_calls = []

    def fake_dispatch(function_path, payload):
        direct_calls.append(function_path)
        return {"status": "completed"}

    def fake_post(url, **kwargs):
        class Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"status": "completed", "total_rows": 1}

        fake_post.last_url = url
        return Resp()

    monkeypatch.setattr(celery_worker, "_dispatch_direct_connector", fake_dispatch)
    monkeypatch.setattr(celery_worker.requests, "post", fake_post)
    monkeypatch.setenv("INTERNAL_API_KEY", "test-internal-key")

    payload = {
        "function_path": "/Snowflake-SAPOData-migration-yield",
        "source_config": {
            "connection_method": "proxy",
            "proxy_agent": "agent-88-6a5296269cbc2874",
            "host": "ecvsdx.evidentx.com",
            "port": 44300,
        },
        "selected_tables": ["EntityOf0FI_AR_30"],
    }
    body, code = celery_worker._execute_connector(
        "http://migration-function-svc:8001/Snowflake-SAPOData-migration-yield",
        payload,
        {},
    )
    assert direct_calls == []
    assert code == 200
    assert "Snowflake-SAPOData-migration-yield" in fake_post.last_url
