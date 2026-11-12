"""Proxy agent credential shaping matches the on-prem agent contract."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("grpc", MagicMock())
sys.modules.setdefault("services.sap.source", MagicMock())
sys.modules.setdefault("sap_proxy_agent.generated", MagicMock())
sys.modules.setdefault("sap_proxy_agent.generated.service_pb2", MagicMock())
sys.modules.setdefault("sap_proxy_agent.generated.service_pb2_grpc", MagicMock())
sys.modules.setdefault("sap_proxy_agent.client.channel_factory", MagicMock())

_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sap_proxy_agent.client.dataynchor_client import (  # noqa: E402
    _as_string_struct_dict,
    _struct_from_mapping,
)
from services.sap.proxy import (  # noqa: E402
    _get_proxy_credentials,
    _normalize_agent_destination_config,
    _proxy_sts_update_details,
    _resolve_agent_destination_type,
)


def test_django_dest_model_names_resolve_to_hub_types():
    assert _resolve_agent_destination_type("AzureDataLakeStorage", {}) == "adls"
    assert _resolve_agent_destination_type("ADLS Gen2", {}) == "adls"
    assert _resolve_agent_destination_type("Snowflake", {}) == "snowflake"
    assert (
        _resolve_agent_destination_type(
            "",
            {"tenant_id": "tid", "storage_account_name": "stacct"},
        )
        == "adls"
    )
    assert (
        _resolve_agent_destination_type(
            "",
            {"account": "xy123", "user": "loader", "warehouse": "WH"},
        )
        == "snowflake"
    )


def test_adls_destination_uses_agent_uppercase_keys_only():
    shaped = _normalize_agent_destination_config(
        "adls",
        {
            "tenant_id": "tid",
            "client_id": "cid",
            "client_secret": "secret",
            "storage_account_name": "stacct",
            "container_name": "container",
            "authentication_type": "service_principal",
        },
    )
    assert shaped == {
        "TENANT_ID": "tid",
        "CLIENT_ID": "cid",
        "CLIENT_SECRET": "secret",
        "CONTAINER_NAME": "container",
        "STORAGE_ACCOUNT_NAME": "stacct",
    }


def test_snowflake_destination_maps_user_to_username_and_defaults_role():
    shaped = _normalize_agent_destination_config(
        "snowflake",
        {
            "account": "EJUEBFT-XE51383",
            "user": "loader@example.com",
            "password": "secret",
            "warehouse": "WH",
            "database": "DB",
            "schema": "SAP",
            "authentication_type": "password",
            "public_key": "unused",
        },
    )
    assert shaped == {
        "account": "EJUEBFT-XE51383",
        "username": "loader@example.com",
        "password": "secret",
        "warehouse": "WH",
        "database": "DB",
        "schema": "SAP",
        "role": "ACCOUNTADMIN",
    }
    assert "user" not in shaped
    assert "authentication_type" not in shaped


def test_snowflake_destination_keeps_private_key_and_passphrase():
    shaped = _normalize_agent_destination_config(
        "snowflake",
        {
            "account": "acct",
            "username": "loader",
            "warehouse": "WH",
            "database": "DB",
            "schema": "SAP",
            "role": "LOADER",
            "private_key": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
            "passphrase": "pw",
        },
    )
    assert shaped["username"] == "loader"
    assert shaped["role"] == "LOADER"
    assert "private_key" in shaped
    assert shaped["passphrase"] == "pw"


def test_proxy_source_credentials_are_host_port_username_password():
    agent_id, host, port, username, password = _get_proxy_credentials(
        {
            "proxy_agent": "C013",
            "host": "ecvsdx.evidentx.com",
            "port": "44300",
            "username": "VINOD",
            "password": "secret",
            "connection_method": "proxy",
            "destination_schema": "SAP",
        }
    )
    assert agent_id == "C013"
    assert host == "ecvsdx.evidentx.com"
    assert port == 44300
    assert username == "VINOD"
    assert password == "secret"


def test_sts_details_include_agent_required_keys_as_strings():
    sts = _proxy_sts_update_details(
        job_name="test01",
        migration_session_id=1234,
        connection_id=129,
        cmp_id=121,
        user_id=12,
        session=34,
        log_id=67,
    )
    assert sts == {
        "job_name": "test01",
        "migration_session_id": "1234",
        "connection_id": "129",
        "cmp_id": "121",
        "user_id": "12",
        "session": "34",
        "log_id": "67",
    }
    assert all(isinstance(value, str) for value in sts.values())


def test_sts_strings_survive_protobuf_struct_as_strings_not_floats():
    from google.protobuf.json_format import MessageToDict
    from google.protobuf.struct_pb2 import Struct

    sts = _proxy_sts_update_details(
        job_name="test01",
        migration_session_id=1234,
        connection_id=129,
    )
    struct = Struct()
    struct.update(sts)
    roundtrip = MessageToDict(struct, preserving_proto_field_name=True)
    assert roundtrip["migration_session_id"] == "1234"
    assert roundtrip["connection_id"] == "129"
    assert isinstance(roundtrip["migration_session_id"], str)

    as_ints = Struct()
    as_ints.update({"migration_session_id": 1234})
    broken = MessageToDict(as_ints, preserving_proto_field_name=True)
    assert broken["migration_session_id"] == 1234.0


def test_destination_values_are_all_strings():
    shaped = _normalize_agent_destination_config(
        "snowflake",
        {
            "account": "acct",
            "user": "loader",
            "password": "secret",
            "warehouse": "WH",
            "database": "DB",
            "schema": "SAP",
        },
    )
    assert all(isinstance(value, str) for value in shaped.values())
    assert shaped["username"] == "loader"


def test_grpc_struct_payload_coerces_ints_to_strings_before_send():
    from google.protobuf.json_format import MessageToDict

    dest = _normalize_agent_destination_config(
        "adls",
        {
            "tenant_id": "tid",
            "client_id": "cid",
            "client_secret": "secret",
            "storage_account_name": "stacct",
            "container_name": "container",
        },
    )
    sts = _proxy_sts_update_details(
        job_name="job",
        migration_session_id=1426,
        connection_id=129,
        cmp_id=121,
        user_id=12,
        session=34,
        log_id=67,
    )
    leaked_ints = {"TENANT_ID": dest["TENANT_ID"], "file_rec_count": 10000}

    stringified = _as_string_struct_dict({**dest, **sts, **leaked_ints})
    assert stringified["migration_session_id"] == "1426"
    assert stringified["file_rec_count"] == "10000"
    assert all(isinstance(value, str) for value in stringified.values())

    roundtrip = MessageToDict(
        _struct_from_mapping({**dest, **sts, **leaked_ints}),
        preserving_proto_field_name=True,
    )
    assert roundtrip["migration_session_id"] == "1426"
    assert roundtrip["connection_id"] == "129"
    assert roundtrip["TENANT_ID"] == "tid"
    assert roundtrip["file_rec_count"] == "10000"
    for key, value in roundtrip.items():
        assert isinstance(value, str), f"{key}={value!r} is {type(value)}"
        assert _struct_from_mapping({key: value}).fields[key].WhichOneof("kind") == (
            "string_value"
        )


def test_snowflake_maps_destination_schema_and_django_dest_type_name():
    shaped = _normalize_agent_destination_config(
        "Snowflake",
        {
            "account": "acct",
            "user": "loader",
            "password": "secret",
            "warehouse": "WH",
            "database": "DB",
            "destination_schema": "SAP",
        },
    )
    assert shaped["username"] == "loader"
    assert shaped["schema"] == "SAP"
    assert "user" not in shaped
    assert "destination_schema" not in shaped


def test_adls_maps_when_django_dest_type_is_azure_data_lake_storage():
    shaped = _normalize_agent_destination_config(
        "AzureDataLakeStorage",
        {
            "tenant_id": "tid",
            "client_id": "cid",
            "client_secret": "secret",
            "account_name": "stacct",
            "container_name": "container",
        },
    )
    assert shaped["STORAGE_ACCOUNT_NAME"] == "stacct"
    assert shaped["TENANT_ID"] == "tid"
    assert "tenant_id" not in shaped
    assert "account_name" not in shaped

