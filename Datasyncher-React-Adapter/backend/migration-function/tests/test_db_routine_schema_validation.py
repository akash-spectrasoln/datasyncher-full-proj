"""Database destination schema checks for transform validate."""

from unittest.mock import patch

import pandas as pd

from routers.entity_transform_router import ValidateRequest, validate_transform
from routers.source_script_router import SourceScriptValidateRequest, validate_source_script_route
from services.transform.schema_output_policy import (
    expected_columns_from_resolved,
    schema_mismatch_errors,
    schema_mismatch_errors_from_column_lists,
)


SAMPLE_MAPPING = {
    "source": {
        "objectname": "ENT",
        "fields": [{"fieldname": "A", "datatype": "CHAR", "length": 10}],
    },
    "target": {
        "objectname": "ENT",
        "fields": [{"fieldname": "TGT_A", "datatype": "CHAR", "length": 10}],
    },
    "field_mapping": [{"src_fieldnames": ["A"], "tgt_fieldname": "TGT_A"}],
    "transformation": {"type": "PYTHON", "entry_point": "transform"},
}

EXTRA_COLUMN_SCRIPT = (
    "import pandas as pd\n\n"
    "def transform(df):\n"
    "    df = df.copy()\n"
    "    df['PLAYER_CATEGORY'] = 'Other Player'\n"
    "    return df\n"
)

IN_PLACE_SCRIPT = (
    "def transform(df):\n"
    "    df = df.copy()\n"
    "    df['A'] = 'Y'\n"
    "    return df\n"
)


def test_expected_columns_from_resolved_includes_script_columns():
    resolved = {
        "rows": [{"tgt_fieldname": "TGT_A"}],
        "script_columns": ["DECLARED_SCRIPT_COL"],
    }
    assert expected_columns_from_resolved(resolved) == ["TGT_A", "DECLARED_SCRIPT_COL"]


def test_schema_mismatch_errors_extra_column_message():
    frame = pd.DataFrame(columns=["A", "B", "NEW"])
    errors = schema_mismatch_errors(frame, ["A", "B"])
    assert len(errors) == 1
    assert errors[0]["path"] == "script:schema"
    assert "NEW" in errors[0]["message"] or "Extra" in errors[0]["message"]


def test_validate_transform_db_rejects_undeclared_column():
    req = ValidateRequest(
        connection_id=1,
        table_name="ENT",
        mapping_json=SAMPLE_MAPPING,
        script_text=EXTRA_COLUMN_SCRIPT,
        entry_point="transform",
        table_fields={"A": {"type": "CHAR"}},
        destination_is_file_based=False,
    )
    result = validate_transform(req)
    assert result["valid"] is False
    assert any(
        (error.get("path") or "").startswith("script")
        for error in result.get("errors") or []
    )


def test_validate_transform_file_based_allows_extra_column_ast_only():
    req = ValidateRequest(
        connection_id=1,
        table_name="ENT",
        mapping_json=SAMPLE_MAPPING,
        script_text=EXTRA_COLUMN_SCRIPT,
        entry_point="transform",
        table_fields={"A": {"type": "CHAR"}},
        destination_is_file_based=True,
    )
    result = validate_transform(req)
    assert not any(
        error.get("path") == "script:schema" for error in result.get("errors") or []
    )


def test_validate_transform_db_allows_in_place_value_change():
    req = ValidateRequest(
        connection_id=1,
        table_name="ENT",
        mapping_json=SAMPLE_MAPPING,
        script_text=IN_PLACE_SCRIPT,
        entry_point="transform",
        table_fields={"A": {"type": "CHAR"}},
        destination_is_file_based=False,
    )
    result = validate_transform(req)
    assert not any(
        error.get("path") == "script:schema" for error in result.get("errors") or []
    )


def test_schema_mismatch_errors_from_column_lists():
    errors = schema_mismatch_errors_from_column_lists(
        ["A", "B", "PLAYER_CATEGORY"], ["A", "B"]
    )
    assert errors
    assert errors[0]["type"] == "extra_columns"


@patch("routers.source_script_router._snowflake_script_output_columns")
def test_source_validate_db_rejects_extra_output_column(mock_snowflake):
    mock_snowflake.return_value = (["A", "B"], ["A", "B", "PLAYER_CATEGORY"])
    request = SourceScriptValidateRequest(
        script_text=EXTRA_COLUMN_SCRIPT,
        entry_point="transform",
        destination_is_file_based=False,
        source_config={"account": "x"},
        table_name="BARCELONA",
        selected_fields=["A", "B"],
    )
    result = validate_source_script_route(request)
    assert result["valid"] is False
    assert any(
        error.get("path") == "script:schema" for error in result.get("errors") or []
    )


@patch("routers.source_script_router._snowflake_script_output_columns")
def test_source_validate_file_based_skips_schema_gate(mock_snowflake):
    mock_snowflake.return_value = (["A"], ["A", "NEW"])
    request = SourceScriptValidateRequest(
        script_text=EXTRA_COLUMN_SCRIPT,
        entry_point="transform",
        destination_is_file_based=True,
        source_config={"account": "x"},
        table_name="BARCELONA",
    )
    result = validate_source_script_route(request)
    mock_snowflake.assert_not_called()
    assert result["valid"] is True
