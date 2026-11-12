"""Hub / bootstrap / unary gRPC targets from dev config.json or env."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_DEFAULT_HUB_PORT = "50051"
_DEFAULT_BOOTSTRAP_PORT = "50052"
_DEFAULT_UNARY_PORT = "50053"


def _config_json_path() -> Path:
    override = (os.environ.get("SAP_PROXY_AGENT_GRPC_CONFIG") or "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1] / "dev" / "config.json"


def _load_dev_config() -> dict[str, Any]:
    path = _config_json_path()
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def hub_target() -> str:
    host = (os.environ.get("PROXY_AGENT_SERVER_HOST") or "").strip()
    port = (os.environ.get("PROXY_AGENT_SERVER_PORT") or _DEFAULT_HUB_PORT).strip()
    if host:
        return f"{host}:{port}"
    cfg = _load_dev_config()
    cfg_host = (cfg.get("server_host") or "").strip()
    cfg_port = str(cfg.get("server_port") or _DEFAULT_HUB_PORT).strip()
    if cfg_host:
        return f"{cfg_host}:{cfg_port}"
    legacy = (os.environ.get("PROXY_AGENT_GRPC_TARGET") or "").strip()
    if legacy:
        return legacy
    raise RuntimeError(
        "SAP proxy gRPC hub target is not configured. "
        "Set PROXY_AGENT_SERVER_HOST and PROXY_AGENT_SERVER_PORT."
    )


def bootstrap_target() -> str:
    cfg = _load_dev_config()
    host = (os.environ.get("PROXY_AGENT_SERVER_HOST") or cfg.get("server_host") or "").strip()
    port = (
        os.environ.get("PROXY_AGENT_BOOTSTRAP_PORT")
        or cfg.get("bootstrap_port")
        or _DEFAULT_BOOTSTRAP_PORT
    )
    port = str(port).strip()
    if host:
        return f"{host}:{port}"
    raise RuntimeError("SAP proxy bootstrap target is not configured.")


def unary_target() -> str:
    cfg = _load_dev_config()
    host = (
        os.environ.get("PROXY_AGENT_UNARY_HOST")
        or cfg.get("unary_host")
        or os.environ.get("PROXY_AGENT_SERVER_HOST")
        or cfg.get("server_host")
        or ""
    ).strip()
    port = (
        os.environ.get("PROXY_AGENT_UNARY_PORT")
        or cfg.get("unary_port")
        or _DEFAULT_UNARY_PORT
    )
    port = str(port).strip()
    if host:
        return f"{host}:{port}"
    raise RuntimeError("SAP proxy unary target is not configured.")
