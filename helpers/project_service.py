"""
project_service.py — PROJECTS CRUD service.
Exception mapping: PermissionError→403 | LookupError→404 | ValueError→400 | else→500
"""

import base64
import json
import uuid
from typing import Any, Dict, List, Optional

from helpers.constants import (
    FC_PROJECTS,
    FGDB_PATH,
    FIELD_DESCRIPTION,
    FIELD_EXTENT,
    FIELD_GRAPHICS,
    FIELD_MAP_STATE,
    FIELD_MAX_LENGTHS,
    FIELD_NAME,
    FIELD_OWNER,
    FIELD_PERMISSIONS,
    FIELD_PROJECT_ID,
    FIELD_SHARED,
    FIELD_THUMBNAIL,
    FIELD_WEBMAP_ID,
    INSERT_FIELDS,
    MSG_ACCESS_DENIED,
    MSG_INTERNAL_ERROR,
    MSG_PROJECT_CREATED,
    MSG_PROJECT_DELETED,
    MSG_PROJECT_UPDATED,
    PERMISSION_EDIT,
    PERMISSION_ENTRY_DELIMITER,
    PERMISSION_ROLE_DELIMITER,
    PERMISSION_VIEW,
    SELECT_FIELDS,
    SHARED_FALSE,
    SHARED_TRUE,
    UPDATE_FIELDS,
)
from helpers.project_model import Project
from helpers.utils import (
    ArcPyMessageHandler,
    ResponseModel,
    build_where_clause,
    delete_rows,
    fetch_all,
    fetch_one,
    get_logger,
    insert_row,
    row_exists,
    update_rows,
    validate_fgdb_exists,
    validate_feature_class_exists,
    validate_required_fields,
)

logger = get_logger(__name__)
logger.addHandler(ArcPyMessageHandler())


# ---------------------------------------------------------------------------
# BLOB helpers
# ---------------------------------------------------------------------------

def _b64_to_blob(b64_str: Optional[str]) -> Optional[bytearray]:
    """Decode a Base64 string to a bytearray for ArcPy BLOB cursor writes."""
    if not b64_str:
        return None
    return bytearray(base64.b64decode(b64_str))


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _parse_json(field_name: str, raw_value: str) -> Any:
    if not raw_value or not raw_value.strip():
        raise ValueError(f"Field '{field_name}' contains invalid JSON: value is empty.")
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Field '{field_name}' contains invalid JSON: {exc}") from exc


def _validate_extent_json(raw_value: str) -> None:
    parsed = _parse_json("EXTENT", raw_value)
    if not isinstance(parsed, dict):
        raise ValueError("Field 'EXTENT' must be a JSON object.")
    missing = {"xmin", "xmax", "ymin", "ymax"} - parsed.keys()
    if missing:
        raise ValueError(f"Field 'EXTENT' is missing required keys: {sorted(missing)}")
    for key in ("xmin", "xmax", "ymin", "ymax"):
        if not isinstance(parsed[key], (int, float)):
            raise ValueError(f"Field 'EXTENT' key '{key}' must be a numeric value.")


def _validate_map_state_json(raw_value: str) -> None:
    if not isinstance(_parse_json("MAP_STATE", raw_value), list):
        raise ValueError("Field 'MAP_STATE' must be a JSON array.")


def _validate_graphics_json(raw_value: str) -> None:
    if not isinstance(_parse_json("GRAPHICS", raw_value), list):
        raise ValueError("Field 'GRAPHICS' must be a JSON array.")


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

def _parse_permissions(raw: Optional[str]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not raw or not raw.strip():
        return result
    for entry in raw.split(PERMISSION_ENTRY_DELIMITER):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(PERMISSION_ROLE_DELIMITER, maxsplit=1)
        if len(parts) != 2:
            logger.warning("Skipping malformed permission entry: %r", entry)
            continue
        email, role = parts[0].strip().lower(), parts[1].strip().upper()
        if role not in (PERMISSION_EDIT, PERMISSION_VIEW):
            logger.warning("Unknown permission role '%s' for '%s'; skipped.", role, email)
            continue
        result[email] = role
    return result


def _has_view_access(raw: Optional[str], user_email: str) -> bool:
    return _parse_permissions(raw).get(user_email.lower()) in (PERMISSION_EDIT, PERMISSION_VIEW)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class ProjectValidator:
    """Static validation methods for the Save_Project domain."""

    @staticmethod
    def validate_fgdb() -> None:
        validate_fgdb_exists(FGDB_PATH)
        validate_feature_class_exists(FC_PROJECTS)
        validate_required_fields(FC_PROJECTS, SELECT_FIELDS)

    @staticmethod
    def _require(value: Optional[str], field_name: str) -> None:
        if not value or not str(value).strip():
            raise ValueError(f"Required field missing or empty: '{field_name}'")

    @staticmethod
    def _check_len(value: Optional[str], field_name: str) -> None:
        if value is None:
            return
        max_len = FIELD_MAX_LENGTHS.get(field_name, 4000)
        actual  = len(str(value))
        if actual > max_len:
            raise ValueError(f"Field '{field_name}' exceeds max length {max_len} (actual: {actual})")

    @staticmethod
    def validate_shared_flag(value: Any) -> None:
        if value is not None and str(value) not in ("0", "1", "True", "False", "true", "false"):
            raise ValueError(f"SHARED must be 0 or 1; received: {value!r}")

    @staticmethod
    def validate_permissions_string(raw: Optional[str]) -> None:
        if not raw or not raw.strip():
            return
        for entry in raw.split(PERMISSION_ENTRY_DELIMITER):
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split(PERMISSION_ROLE_DELIMITER, maxsplit=1)
            if len(parts) != 2:
                raise ValueError(f"PERMISSIONS entry '{entry}' must follow 'email:ROLE' format.")
            role = parts[1].strip().upper()
            if role not in (PERMISSION_EDIT, PERMISSION_VIEW):
                raise ValueError(f"Unknown role '{role}' in '{entry}'. Allowed: EDIT, VIEW.")

    @staticmethod
    def validate_no_duplicate_project_id(project_id: str) -> None:
        if row_exists(FC_PROJECTS, build_where_clause(FIELD_PROJECT_ID, project_id)):
            raise ValueError(f"PROJECT_ID '{project_id}' already exists.")

    @staticmethod
    def validate_project_exists(project_id: str) -> None:
        if not row_exists(FC_PROJECTS, build_where_clause(FIELD_PROJECT_ID, project_id)):
            raise LookupError(f"Project '{project_id}' not found.")

    @staticmethod
    def validate_is_owner(project_owner: str, requesting_user: str) -> None:
        if project_owner.lower() != requesting_user.lower():
            logger.warning("Permission denied: '%s' tried to modify project owned by '%s'.",
                           requesting_user, project_owner)
            raise PermissionError("Only the project owner can perform this action.")

    @staticmethod
    def validate_create_payload(data: Dict[str, Any]) -> None:
        ProjectValidator._require(data.get(FIELD_NAME),      FIELD_NAME)
        ProjectValidator._require(data.get(FIELD_WEBMAP_ID), FIELD_WEBMAP_ID)
        ProjectValidator._require(data.get(FIELD_OWNER),     FIELD_OWNER)
        for fname in (FIELD_NAME, FIELD_WEBMAP_ID, FIELD_OWNER):
            ProjectValidator._check_len(data.get(fname), fname)
        if data.get(FIELD_DESCRIPTION):
            ProjectValidator._check_len(data[FIELD_DESCRIPTION], FIELD_DESCRIPTION)
        if data.get(FIELD_EXTENT):
            _validate_extent_json(data[FIELD_EXTENT])
            ProjectValidator._check_len(data[FIELD_EXTENT], FIELD_EXTENT)
        if data.get(FIELD_MAP_STATE):
            _validate_map_state_json(data[FIELD_MAP_STATE])
            ProjectValidator._check_len(data[FIELD_MAP_STATE], FIELD_MAP_STATE)
        if data.get(FIELD_GRAPHICS):
            _validate_graphics_json(data[FIELD_GRAPHICS])
            ProjectValidator._check_len(data[FIELD_GRAPHICS], FIELD_GRAPHICS)
        if data.get(FIELD_PERMISSIONS):
            ProjectValidator.validate_permissions_string(data[FIELD_PERMISSIONS])
            ProjectValidator._check_len(data[FIELD_PERMISSIONS], FIELD_PERMISSIONS)
        if FIELD_SHARED in data:
            ProjectValidator.validate_shared_flag(data[FIELD_SHARED])

    @staticmethod
    def validate_update_payload(data: Dict[str, Any]) -> None:
        if FIELD_NAME in data:
            ProjectValidator._require(data[FIELD_NAME], FIELD_NAME)
            ProjectValidator._check_len(data[FIELD_NAME], FIELD_NAME)
        if data.get(FIELD_WEBMAP_ID):
            ProjectValidator._check_len(data[FIELD_WEBMAP_ID], FIELD_WEBMAP_ID)
        if data.get(FIELD_EXTENT):
            _validate_extent_json(data[FIELD_EXTENT])
            ProjectValidator._check_len(data[FIELD_EXTENT], FIELD_EXTENT)
        if data.get(FIELD_MAP_STATE):
            _validate_map_state_json(data[FIELD_MAP_STATE])
            ProjectValidator._check_len(data[FIELD_MAP_STATE], FIELD_MAP_STATE)
        if data.get(FIELD_GRAPHICS):
            _validate_graphics_json(data[FIELD_GRAPHICS])
            ProjectValidator._check_len(data[FIELD_GRAPHICS], FIELD_GRAPHICS)
        if data.get(FIELD_PERMISSIONS):
            ProjectValidator.validate_permissions_string(data[FIELD_PERMISSIONS])
            ProjectValidator._check_len(data[FIELD_PERMISSIONS], FIELD_PERMISSIONS)
        if FIELD_SHARED in data:
            ProjectValidator.validate_shared_flag(data[FIELD_SHARED])


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ProjectService:
    """CRUD service for the PROJECTS feature class. One instance per tool call."""

    def __init__(self, user_email: str) -> None:
        if not user_email or not user_email.strip():
            raise ValueError("user_email must not be empty.")
        self._user_email: str = user_email.strip().lower()
        logger.info("ProjectService initialised for user: %s", self._user_email)

    def _row_to_project(self, row: Dict[str, Any]) -> Project:
        return Project.from_row(row)

    def _can_access(self, project: Project) -> bool:
        return (
            project.owner.lower() == self._user_email
            or project.is_shared()
            or _has_view_access(project.permissions, self._user_email)
        )

    def _assert_owner(self, project: Project) -> None:
        ProjectValidator.validate_is_owner(project.owner, self._user_email)

    # GET /api/projects
    def get_all_projects(self) -> ResponseModel:
        logger.info("get_all_projects called by '%s'", self._user_email)
        try:
            ProjectValidator.validate_fgdb()
            all_rows: List[Dict[str, Any]] = fetch_all(FC_PROJECTS, SELECT_FIELDS)
            accessible = [
                self._row_to_project(row).to_dict()
                for row in all_rows
                if self._can_access(self._row_to_project(row))
            ]
            logger.info("get_all_projects: %d / %d accessible to '%s'.",
                        len(accessible), len(all_rows), self._user_email)
            return ResponseModel.ok(message=f"{len(accessible)} project(s) found.", data=accessible)
        except PermissionError as exc:
            return ResponseModel.error(str(exc), 403)
        except LookupError as exc:
            return ResponseModel.error(str(exc), 404)
        except ValueError as exc:
            return ResponseModel.error(str(exc), 400)
        except Exception as exc:
            logger.exception("Unexpected error in get_all_projects.")
            return ResponseModel.error(f"{MSG_INTERNAL_ERROR}: {exc}", 500)

    # POST /api/projects
    def create_project(self, data: Dict[str, Any]) -> ResponseModel:
        logger.info("create_project called by '%s'", self._user_email)
        try:
            ProjectValidator.validate_fgdb()
            data[FIELD_OWNER] = self._user_email
            ProjectValidator.validate_create_payload(data)

            project_id: str = str(uuid.uuid4()).upper()
            ProjectValidator.validate_no_duplicate_project_id(project_id)

            raw_shared = data.get(FIELD_SHARED, 0)
            shared_int = SHARED_TRUE if str(raw_shared) in ("1", "True", "true") else SHARED_FALSE

            insert_row(FC_PROJECTS, INSERT_FIELDS, [
                project_id,
                data.get(FIELD_NAME),
                data.get(FIELD_DESCRIPTION),
                data.get(FIELD_WEBMAP_ID),
                data.get(FIELD_EXTENT),
                data.get(FIELD_MAP_STATE),
                data.get(FIELD_GRAPHICS),
                data.get(FIELD_PERMISSIONS),
                _b64_to_blob(data.get(FIELD_THUMBNAIL)),
                shared_int,
                self._user_email,
            ])
            logger.info("Project '%s' created by '%s'.", project_id, self._user_email)

            where = build_where_clause(FIELD_PROJECT_ID, project_id)
            row   = fetch_one(FC_PROJECTS, SELECT_FIELDS, where)
            return ResponseModel.created(
                message=MSG_PROJECT_CREATED,
                data=Project.from_row(row).to_dict() if row else {"PROJECT_ID": project_id},
            )
        except PermissionError as exc:
            return ResponseModel.error(str(exc), 403)
        except LookupError as exc:
            return ResponseModel.error(str(exc), 404)
        except ValueError as exc:
            return ResponseModel.error(str(exc), 400)
        except Exception as exc:
            logger.exception("Unexpected error in create_project.")
            return ResponseModel.error(f"{MSG_INTERNAL_ERROR}: {exc}", 500)

    # GET /api/projects/{id}
    def get_project_by_id(self, project_id: str) -> ResponseModel:
        logger.info("get_project_by_id: id='%s' by '%s'", project_id, self._user_email)
        try:
            ProjectValidator.validate_fgdb()
            where = build_where_clause(FIELD_PROJECT_ID, project_id)
            row   = fetch_one(FC_PROJECTS, SELECT_FIELDS, where)
            if not row:
                raise LookupError(f"Project '{project_id}' not found.")
            project = self._row_to_project(row)
            if not self._can_access(project):
                raise PermissionError(MSG_ACCESS_DENIED)
            return ResponseModel.ok(message="Project loaded successfully.", data=project.to_dict())
        except PermissionError as exc:
            return ResponseModel.error(str(exc), 403)
        except LookupError as exc:
            return ResponseModel.error(str(exc), 404)
        except ValueError as exc:
            return ResponseModel.error(str(exc), 400)
        except Exception as exc:
            logger.exception("Unexpected error in get_project_by_id.")
            return ResponseModel.error(f"{MSG_INTERNAL_ERROR}: {exc}", 500)

    # PUT /api/projects/{id}
    def update_project(self, project_id: str, data: Dict[str, Any]) -> ResponseModel:
        logger.info("update_project: id='%s' by '%s'", project_id, self._user_email)
        try:
            ProjectValidator.validate_fgdb()
            ProjectValidator.validate_project_exists(project_id)

            where   = build_where_clause(FIELD_PROJECT_ID, project_id)
            row     = fetch_one(FC_PROJECTS, SELECT_FIELDS, where)
            project = self._row_to_project(row)
            self._assert_owner(project)
            ProjectValidator.validate_update_payload(data)

            def _resolve(f: str, cur: Any) -> Any:
                return data[f] if f in data else cur

            raw_shared = data.get(FIELD_SHARED, project.shared)
            shared_int = SHARED_TRUE if str(raw_shared) in ("1", "True", "true") else SHARED_FALSE

            updated = update_rows(FC_PROJECTS, UPDATE_FIELDS, [
                _resolve(FIELD_NAME,        project.name),
                _resolve(FIELD_DESCRIPTION, project.description),
                _resolve(FIELD_MAP_STATE,   project.map_state),
                _resolve(FIELD_GRAPHICS,    project.graphics),
                _b64_to_blob(_resolve(FIELD_THUMBNAIL, project.thumbnail)),
                _resolve(FIELD_EXTENT,      project.extent),
                _resolve(FIELD_PERMISSIONS, project.permissions),
                shared_int,
            ], where)

            if updated == 0:
                raise LookupError(f"Project '{project_id}' not found.")

            logger.info("Project '%s' updated by '%s'. %d row(s).", project_id, self._user_email, updated)
            refreshed = fetch_one(FC_PROJECTS, SELECT_FIELDS, where)
            return ResponseModel.ok(
                message=MSG_PROJECT_UPDATED,
                data=Project.from_row(refreshed).to_dict() if refreshed else {},
            )
        except PermissionError as exc:
            return ResponseModel.error(str(exc), 403)
        except LookupError as exc:
            return ResponseModel.error(str(exc), 404)
        except ValueError as exc:
            return ResponseModel.error(str(exc), 400)
        except Exception as exc:
            logger.exception("Unexpected error in update_project.")
            return ResponseModel.error(f"{MSG_INTERNAL_ERROR}: {exc}", 500)

    # DELETE /api/projects/{id}
    def delete_project(self, project_id: str) -> ResponseModel:
        logger.info("delete_project: id='%s' by '%s'", project_id, self._user_email)
        try:
            ProjectValidator.validate_fgdb()
            ProjectValidator.validate_project_exists(project_id)

            where   = build_where_clause(FIELD_PROJECT_ID, project_id)
            row     = fetch_one(FC_PROJECTS, SELECT_FIELDS, where)
            project = self._row_to_project(row)
            self._assert_owner(project)

            deleted = delete_rows(FC_PROJECTS, where)
            if deleted == 0:
                raise LookupError(f"Project '{project_id}' not found.")

            logger.info("Project '%s' deleted by '%s'.", project_id, self._user_email)
            return ResponseModel.ok(message=MSG_PROJECT_DELETED)
        except PermissionError as exc:
            return ResponseModel.error(str(exc), 403)
        except LookupError as exc:
            return ResponseModel.error(str(exc), 404)
        except ValueError as exc:
            return ResponseModel.error(str(exc), 400)
        except Exception as exc:
            logger.exception("Unexpected error in delete_project.")
            return ResponseModel.error(f"{MSG_INTERNAL_ERROR}: {exc}", 500)
