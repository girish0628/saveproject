"""Project constants — field names, cursor lists, limits, messages, logging settings."""

import logging
import os
from pathlib import Path

# Paths
FGDB_PATH:   str = r"DATA\SavedProject.gdb"
FC_PROJECTS: str = r"DATA\SavedProject.gdb\PROJECTS"

# Field names
FIELD_OBJECTID:         str = "OBJECTID"
FIELD_PROJECT_ID:       str = "PROJECT_ID"
FIELD_NAME:             str = "NAME"
FIELD_DESCRIPTION:      str = "DESCRIPTION"
FIELD_WEBMAP_ID:        str = "WEBMAP_ID"
FIELD_EXTENT:           str = "EXTENT"
FIELD_MAP_STATE:        str = "MAP_STATE"
FIELD_GRAPHICS:         str = "GRAPHICS"
FIELD_PERMISSIONS:      str = "PERMISSIONS"
FIELD_THUMBNAIL:        str = "THUMBNAIL"
FIELD_GLOBAL_ID:        str = "GlobalID"
FIELD_CREATED_USER:     str = "created_user"
FIELD_CREATE_DATE:      str = "created_date"
FIELD_LAST_EDITED_USER: str = "last_edited_user"
FIELD_LAST_EDITED_DATE: str = "last_edited_date"
FIELD_SHARED:           str = "SHARED"
FIELD_OWNER:            str = "OWNER"
FIELD_APP_NAME:         str = "APP_NAME"

# Cursor field lists
INSERT_FIELDS: list = [
    FIELD_PROJECT_ID, FIELD_NAME, FIELD_DESCRIPTION, FIELD_WEBMAP_ID,
    FIELD_EXTENT, FIELD_MAP_STATE, FIELD_GRAPHICS, FIELD_PERMISSIONS,
    FIELD_THUMBNAIL, FIELD_SHARED, FIELD_OWNER, FIELD_APP_NAME,
]

SELECT_FIELDS: list = [
    FIELD_OBJECTID, FIELD_PROJECT_ID, FIELD_NAME, FIELD_DESCRIPTION,
    FIELD_WEBMAP_ID, FIELD_EXTENT, FIELD_MAP_STATE, FIELD_GRAPHICS,
    FIELD_PERMISSIONS, FIELD_THUMBNAIL, FIELD_GLOBAL_ID, FIELD_CREATED_USER,
    FIELD_CREATE_DATE, FIELD_LAST_EDITED_USER, FIELD_LAST_EDITED_DATE,
    FIELD_SHARED, FIELD_OWNER, FIELD_APP_NAME,
]

UPDATE_FIELDS: list = [
    FIELD_NAME, FIELD_DESCRIPTION, FIELD_MAP_STATE, FIELD_GRAPHICS,
    FIELD_THUMBNAIL, FIELD_EXTENT, FIELD_PERMISSIONS, FIELD_SHARED,
    FIELD_APP_NAME,
]

# Field max lengths  (THUMBNAIL is BLOB — no length limit)
FIELD_MAX_LENGTHS: dict = {
    FIELD_PROJECT_ID:        255,
    FIELD_NAME:              255,
    FIELD_DESCRIPTION:       1000,
    FIELD_WEBMAP_ID:         255,
    FIELD_EXTENT:            255,
    FIELD_MAP_STATE:         4000,
    FIELD_GRAPHICS:          4000,
    FIELD_PERMISSIONS:       4000,
    FIELD_CREATED_USER:      255,
    FIELD_LAST_EDITED_USER:  255,
    FIELD_OWNER:             255,
    FIELD_APP_NAME:          255,
}

# Permissions
PERMISSION_EDIT:            str = "EDIT"
PERMISSION_VIEW:            str = "VIEW"
PERMISSION_ENTRY_DELIMITER: str = ","
PERMISSION_ROLE_DELIMITER:  str = ":"

# SHARED values
SHARED_TRUE:  int = 1
SHARED_FALSE: int = 0

# Response messages
MSG_PROJECT_CREATED:      str = "Project created successfully."
MSG_PROJECT_UPDATED:      str = "Project updated successfully."
MSG_PROJECT_DELETED:      str = "Project deleted successfully."
MSG_PROJECT_NOT_FOUND:    str = "Project not found."
MSG_ACCESS_DENIED:        str = "Access denied. Only the project owner can perform this action."
MSG_INTERNAL_ERROR:       str = "An internal server error occurred."

# Logging settings
_BASE_DIR:        str = str(Path(__file__).resolve().parent.parent)
LOG_DIR:          str = os.path.join(_BASE_DIR, "logs")
LOG_FILE:         str = os.path.join(LOG_DIR, "project_api.log")
LOG_LEVEL:        int = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
LOG_MAX_BYTES:    int = 10 * 1024 * 1024
LOG_BACKUP_COUNT: int = 5
