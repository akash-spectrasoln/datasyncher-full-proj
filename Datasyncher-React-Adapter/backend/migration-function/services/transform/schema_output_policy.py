"""Output column policy for DB vs file-based transform destinations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

import pandas as pd

from services.transform.executor import validate_output_schema


def expected_columns_from_resolved(resolved: Dict[str, Any]) -> List[str]:
    """Target column names the warehouse load expects from mapping resolution."""
    expected: List[str] = []
    seen: set[str] = set()
    for row in resolved.get("rows") or []:
        name = row.get("tgt_fieldname")
        if not name or name in seen:
            continue
        seen.add(name)
        expected.append(str(name))
    for name in resolved.get("script_columns") or []:
        if name and name not in seen:
            seen.add(name)
            expected.append(str(name))
    return expected


def schema_mismatch_errors(
    df: pd.DataFrame,
    expected_columns: List[str],
    *,
    strict_order: bool = True,
) -> List[Dict[str, Any]]:
    """Turn output-schema issues into validation errors for database destinations."""
    if not expected_columns:
        return []
    issues = validate_output_schema(df, expected_columns)
    if not strict_order:
        issues = [i for i in issues if i.get("type") != "order"]
    errors: List[Dict[str, Any]] = []
    for issue in issues:
        issue_type = issue.get("type") or ""
        raw_msg = issue.get("message") or "Output schema does not match mapping."
        if issue_type == "extra":
            errors.append(
                {
                    "path": "script:schema",
                    "type": "extra_columns",
                    "message": (
                        "Destination is a database: the routine added columns that are "
                        "not declared in mapping. "
                        f"{raw_msg} "
                        "Add targets on the Mapping step or use a file-based destination."
                    ),
                }
            )
        elif issue_type == "missing":
            errors.append(
                {
                    "path": "script:schema",
                    "type": "missing_columns",
                    "message": (
                        "Destination is a database: the routine must output every mapped "
                        f"target column. {raw_msg}"
                    ),
                }
            )
        elif issue_type == "order":
            errors.append(
                {
                    "path": "script:schema",
                    "type": "column_order",
                    "message": (
                        "Destination is a database: column order must match the mapping. "
                        f"{raw_msg}"
                    ),
                }
            )
        else:
            errors.append(
                {
                    "path": "script:schema",
                    "type": issue_type or "schema",
                    "message": raw_msg,
                }
            )
    return errors


def script_schema_change_errors(
    before: pd.DataFrame,
    after: pd.DataFrame,
    declared_script_columns: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """Fail when a routine adds/removes columns not allowed for database destinations."""
    declared = {str(name) for name in (declared_script_columns or set())}
    before_cols = {str(column) for column in before.columns}
    after_cols = {str(column) for column in after.columns}
    added = sorted(after_cols - before_cols)
    removed = sorted(before_cols - after_cols)
    errors: List[Dict[str, Any]] = []
    undeclared_added = [name for name in added if name not in declared]
    if undeclared_added:
        joined = ", ".join(undeclared_added)
        errors.append(
            {
                "path": "script:schema",
                "type": "extra_columns",
                "message": (
                    "Destination is a database: the routine created columns that are "
                    f"not declared in mapping: {joined}. "
                    "Add them on the Mapping step or use a file-based destination."
                ),
            }
        )
    if removed:
        joined = ", ".join(removed)
        errors.append(
            {
                "path": "script:schema",
                "type": "removed_columns",
                "message": (
                    "Destination is a database: the routine must not drop source "
                    f"columns. Removed: {joined}."
                ),
            }
        )
    return errors


def script_output_locked_schema_errors(
    output_columns: List[str],
    expected_columns: List[str],
) -> List[Dict[str, Any]]:
    """For source-side routines where output must match a fixed destination field list."""
    return schema_mismatch_errors_from_column_lists(
        output_columns, expected_columns
    )


def schema_mismatch_errors_from_column_lists(
    output_columns: List[str],
    expected_columns: List[str],
    *,
    strict_order: bool = True,
) -> List[Dict[str, Any]]:
    """Compare column name lists without a DataFrame."""
    if not expected_columns:
        return []
    frame = pd.DataFrame(columns=[str(c) for c in output_columns])
    return schema_mismatch_errors(frame, expected_columns, strict_order=strict_order)
