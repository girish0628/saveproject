"""Shared utilities: response envelope, logging factory, and ArcPy cursor helpers."""

import json
import logging
import os
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Generator, List, Optional, Tuple

try:
    import arcpy as _arcpy
    _ARCPY_AVAILABLE: bool = True
except ImportError:
    _arcpy = None  # type: ignore
    _ARCPY_AVAILABLE: bool = False


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

@dataclass
class ResponseModel:
    success:     bool
    message:     str
    data:        Optional[Any] = field(default=None)
    status_code: int           = field(default=200)

    @classmethod
    def ok(cls, message: str, data: Optional[Any] = None, status_code: int = 200) -> "ResponseModel":
        return cls(True, message, data, status_code)

    @classmethod
    def created(cls, message: str, data: Optional[Any] = None) -> "ResponseModel":
        return cls(True, message, data, 201)

    @classmethod
    def error(cls, message: str, status_code: int = 500, data: Optional[Any] = None) -> "ResponseModel":
        return cls(False, message, data, status_code)

    def to_dict(self) -> dict:
        return {"success": self.success, "message": self.message, "data": self.data, "status_code": self.status_code}

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def __repr__(self) -> str:
        return f"ResponseModel(success={self.success}, status_code={self.status_code}, message={self.message!r})"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def get_logger(name: str, log_file: Optional[str] = None, level: Optional[int] = None,
               max_bytes: int = 5 * 1024 * 1024, backup_count: int = 3) -> logging.Logger:
    """Build (or retrieve) a named logger with console + rotating-file handlers."""
    from helpers.constants import LOG_DIR, LOG_FILE, LOG_LEVEL
    _log_file = log_file or LOG_FILE
    _level    = level    or LOG_LEVEL

    lg = logging.getLogger(name)
    if lg.handlers:
        return lg

    lg.setLevel(_level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)-8s] %(name)s :: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch.setLevel(_level)
    lg.addHandler(ch)

    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        fh = RotatingFileHandler(_log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        fh.setFormatter(fmt)
        fh.setLevel(_level)
        lg.addHandler(fh)
    except (OSError, PermissionError) as exc:
        lg.warning("Could not attach file log handler: %s", exc)

    return lg


class ArcPyMessageHandler(logging.Handler):
    """Forwards log records to the ArcGIS Pro GP message panel."""

    def emit(self, record: logging.LogRecord) -> None:
        if not _ARCPY_AVAILABLE:
            return
        msg = self.format(record)
        if record.levelno >= logging.ERROR:
            _arcpy.AddError(msg)
        elif record.levelno >= logging.WARNING:
            _arcpy.AddWarning(msg)
        else:
            _arcpy.AddMessage(msg)


# ---------------------------------------------------------------------------
# ArcPy cursor helpers
# ---------------------------------------------------------------------------

_logger = get_logger(__name__)


def validate_fgdb_exists(fgdb_path: str) -> None:
    if not _arcpy.Exists(fgdb_path):
        raise FileNotFoundError(f"File Geodatabase not found: '{fgdb_path}'")


def validate_feature_class_exists(fc_path: str) -> None:
    if not _arcpy.Exists(fc_path):
        raise FileNotFoundError(f"Feature class not found: '{fc_path}'")


def validate_required_fields(fc_path: str, required_fields: List[str]) -> None:
    validate_feature_class_exists(fc_path)
    existing = [f.name.upper() for f in _arcpy.ListFields(fc_path)]
    missing  = [f for f in required_fields if f.upper() not in existing]
    if missing:
        raise ValueError(f"Missing fields in '{fc_path}': {missing}")


def get_field_names(fc_path: str) -> List[str]:
    validate_feature_class_exists(fc_path)
    return [f.name for f in _arcpy.ListFields(fc_path)]


def search_rows(fc_path: str, fields: List[str], where_clause: Optional[str] = None) -> Generator[Dict[str, Any], None, None]:
    _logger.debug("SearchCursor on '%s' | where='%s'", fc_path, where_clause)
    try:
        with _arcpy.da.SearchCursor(fc_path, fields, where_clause) as cursor:
            for row in cursor:
                yield dict(zip(fields, row))
    except Exception as exc:
        raise RuntimeError(f"SearchCursor failed on '{fc_path}': {exc}") from exc


def fetch_one(fc_path: str, fields: List[str], where_clause: str) -> Optional[Dict[str, Any]]:
    for row in search_rows(fc_path, fields, where_clause):
        return row
    return None


def fetch_all(fc_path: str, fields: List[str], where_clause: Optional[str] = None) -> List[Dict[str, Any]]:
    return list(search_rows(fc_path, fields, where_clause))


def row_exists(fc_path: str, where_clause: str) -> bool:
    return fetch_one(fc_path, ["OBJECTID"], where_clause) is not None


def insert_row(fc_path: str, fields: List[str], values: List[Any]) -> Optional[Tuple]:
    _logger.debug("InsertCursor on '%s' | fields=%s", fc_path, fields)
    try:
        with _arcpy.da.InsertCursor(fc_path, fields) as cursor:
            return cursor.insertRow(values)
    except Exception as exc:
        raise RuntimeError(f"InsertCursor failed on '{fc_path}': {exc}") from exc


def update_rows(fc_path: str, update_fields: List[str], update_values: List[Any], where_clause: str) -> int:
    _logger.debug("UpdateCursor on '%s' | where='%s'", fc_path, where_clause)
    count = 0
    try:
        with _arcpy.da.UpdateCursor(fc_path, update_fields, where_clause) as cursor:
            for _ in cursor:
                cursor.updateRow(update_values)
                count += 1
    except Exception as exc:
        raise RuntimeError(f"UpdateCursor failed on '{fc_path}': {exc}") from exc
    return count


def delete_rows(fc_path: str, where_clause: str) -> int:
    _logger.debug("DeleteCursor on '%s' | where='%s'", fc_path, where_clause)
    count = 0
    try:
        with _arcpy.da.UpdateCursor(fc_path, ["OBJECTID"], where_clause) as cursor:
            for _ in cursor:
                cursor.deleteRow()
                count += 1
    except Exception as exc:
        raise RuntimeError(f"Delete failed on '{fc_path}': {exc}") from exc
    return count


def build_where_clause(field_name: str, value: str) -> str:
    """Escape single quotes to prevent SQL injection."""
    return f"{field_name} = '{value.replace(chr(39), chr(39)*2)}'"


def build_or_where_clause(conditions: List[str]) -> str:
    return " OR ".join(f"({c})" for c in conditions)
