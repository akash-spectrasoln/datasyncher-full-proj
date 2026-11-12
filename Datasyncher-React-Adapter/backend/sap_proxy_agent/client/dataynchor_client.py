import grpc
from google.protobuf.json_format import MessageToDict
from google.protobuf.struct_pb2 import Struct

from sap_proxy_agent.client.channel_factory import get_channel, hub_grpc_call_timeout_seconds
from sap_proxy_agent.generated import service_pb2, service_pb2_grpc


def _as_string_struct_dict(mapping):
    """protobuf Struct stores ints as doubles (1234.0). Agent reads string values."""
    out = {}
    for key, value in dict(mapping or {}).items():
        if isinstance(value, dict):
            out[str(key)] = _as_string_struct_dict(value)
        elif isinstance(value, list):
            out[str(key)] = [
                _as_string_struct_dict(item) if isinstance(item, dict)
                else ("" if item is None else str(item))
                for item in value
            ]
        elif value is None:
            out[str(key)] = ""
        else:
            out[str(key)] = str(value)
    return out


def _struct_from_mapping(mapping):
    struct = Struct()
    struct.update(_as_string_struct_dict(mapping))
    return struct


def get_metadata(source_type, cust_id, url, source_config):
    channel = get_channel()
    stub = service_pb2_grpc.DatasynchorStub(channel)

    request = service_pb2.MetadataRequest(
        cust_id=cust_id,
        metadata_url=url,
        src_conf=source_config,
        src_type=source_type,
    )

    response = stub.Metadata(request)

    if response.error_msg:
        raise ValueError(response.error_msg)

    return MessageToDict(response.metadata_json)


def startdataload(
    cust_id,
    sources,
    source_config,
    destination_config,
    destination_type,
    details_for_sts_update,
    *,
    snowflake_sources=None,
    src_type="",
):
    channel = get_channel()
    stub = service_pb2_grpc.DatasynchorStub(channel)

    destination_config_struct = _struct_from_mapping(destination_config)
    details_for_sts_update_struct = _struct_from_mapping(details_for_sts_update)

    request_kwargs = {
        "cust_id": cust_id,
        "src_conf": source_config,
        "destination_type": destination_type,
        "destination_config": destination_config_struct,
        "details_for_sts_update": details_for_sts_update_struct,
    }
    if snowflake_sources is not None:
        request_kwargs["snowflake_sources"] = snowflake_sources
        request_kwargs["sources"] = sources or []
        request_kwargs["src_type"] = src_type or "sap-odata"
    else:
        request_kwargs["sources"] = sources or []

    request = service_pb2.DataLoadRequest(**request_kwargs)
    response = stub.StartDataLoad(request)
    return response.accepted


def AlldataSource(src_type, cust_id, data_url, source_config):
    channel = get_channel()
    stub = service_pb2_grpc.DatasynchorStub(channel)

    request = service_pb2.AllDataRequest(
        cust_id=cust_id,
        alldata_url=data_url,
        src_conf=source_config,
        src_type=src_type,
    )

    response = stub.AllDataSource(request)
    if response.error_msg:
        raise ValueError(response.error_msg)

    return MessageToDict(response)


def SourceDetail(src_type, cust_id, source_config, service_name):
    channel = get_channel()
    stub = service_pb2_grpc.DatasynchorStub(channel)

    request = service_pb2.SourceDetailRequest(
        cust_id=cust_id,
        service_name=service_name,
        src_conf=source_config,
        src_type=src_type,
    )

    response = stub.GetSourceDetail(request)
    if response.error_msg:
        raise ValueError(response.error_msg)

    return MessageToDict(response.src_details_json)


def test_sap_connection(src_type, cust_id, source_config):
    channel = get_channel()
    stub = service_pb2_grpc.DatasynchorStub(channel)

    request = service_pb2.ConnectionRequest(
        cust_id=cust_id,
        src_conf=source_config,
        src_type=src_type,
    )

    response = stub.TestSapConnection(
        request, timeout=hub_grpc_call_timeout_seconds()
    )
    if response.error_msg:
        raise ValueError(response.error_msg)

    return MessageToDict(response.conn_details_json)


def delta_load(
    cust_id,
    sources,
    source_config,
    destination_config,
    destination_type,
    details_for_sts_update,
):
    channel = get_channel()
    stub = service_pb2_grpc.DatasynchorStub(channel)
    destination_config_struct = _struct_from_mapping(destination_config)
    details_for_sts_update_struct = _struct_from_mapping(details_for_sts_update)

    request = service_pb2.TriggerDeltaRequest(
        cust_id=cust_id,
        sources=sources,
        src_conf=source_config,
        destination_type=destination_type,
        destination_config=destination_config_struct,
        details_for_sts_update=details_for_sts_update_struct,
    )

    response = stub.TriggerDelta(request)
    return response.accepted
