"""Dataclass model for a single PROJECTS feature class row."""

import base64
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, Optional


def _blob_to_b64(blob_val) -> Optional[str]:
    # ArcPy BLOB memoryview objects do not support .tobytes(); bytes() uses the
    # C buffer protocol instead and works across all ArcPy Pro versions.
    if not blob_val:
        return None
    try:
        b = bytes(blob_val)
    except (TypeError, ValueError):
        return None
    return base64.b64encode(b).decode("utf-8") if b else None


@dataclass
class Project:
    project_id:       str
    name:             str
    webmap_id:        str
    owner:            str
    description:      Optional[str]      = field(default=None)
    extent:           Optional[str]      = field(default=None)
    map_state:        Optional[str]      = field(default=None)
    graphics:         Optional[str]      = field(default=None)
    permissions:      Optional[str]      = field(default=None)
    app_name:         Optional[str]      = field(default=None)
    thumbnail:        Optional[str]      = field(default=None)
    shared:           int                = field(default=0)
    object_id:        Optional[int]      = field(default=None)
    global_id:        Optional[str]      = field(default=None)
    created_user:     Optional[str]      = field(default=None)
    create_date:      Optional[datetime] = field(default=None)
    last_edited_user: Optional[str]      = field(default=None)
    last_edited_date: Optional[datetime] = field(default=None)

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "Project":
        return cls(
            object_id        = row.get("OBJECTID"),
            project_id       = row.get("PROJECT_ID", ""),
            name             = row.get("NAME", ""),
            description      = row.get("DESCRIPTION"),
            webmap_id        = row.get("WEBMAP_ID", ""),
            extent           = row.get("EXTENT"),
            map_state        = row.get("MAP_STATE"),
            graphics         = row.get("GRAPHICS"),
            permissions      = row.get("PERMISSIONS"),
            app_name         = row.get("APP_NAME"),
            thumbnail        = _blob_to_b64(row.get("THUMBNAIL")),
            global_id        = row.get("GlobalID"),
            created_user     = row.get("created_user"),
            create_date      = row.get("created_date"),
            last_edited_user = row.get("last_edited_user"),
            last_edited_date = row.get("last_edited_date"),
            shared           = row.get("SHARED", 0),
            owner            = row.get("OWNER", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        for key in ("create_date", "last_edited_date"):
            if isinstance(d.get(key), datetime):
                d[key] = d[key].isoformat()
        return d

    def is_shared(self) -> bool:
        return self.shared == 1

    def __repr__(self) -> str:
        return f"Project(project_id={self.project_id!r}, name={self.name!r}, owner={self.owner!r})"
