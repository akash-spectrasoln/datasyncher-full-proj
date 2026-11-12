"""Resolve SAP proxy agent gRPC hub host:port for migration-function clients."""

from __future__ import annotations

from sap_proxy_agent.client.grpc_targets import hub_target as grpc_server_target

__all__ = ["grpc_server_target"]
