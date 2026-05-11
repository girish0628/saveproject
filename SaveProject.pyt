# -*- coding: utf-8 -*-
"""SaveProject.pyt — ArcGIS Python Toolbox wiring the five CRUD tools."""

import sys
import os

# Evict stale cached modules on every toolbox refresh.
_stale = [k for k in sys.modules if k.startswith(("project_api", "helpers"))]
for _mod in _stale:
    del sys.modules[_mod]

_PYT_DIR = os.path.dirname(os.path.abspath(__file__))
if _PYT_DIR not in sys.path:
    sys.path.insert(0, _PYT_DIR)

from project_api.get_all_projects  import GetAllProjectsTool
from project_api.create_project    import CreateProjectTool
from project_api.get_project_by_id import GetProjectByIdTool
from project_api.update_project    import UpdateProjectTool
from project_api.delete_project    import DeleteProjectTool


class Toolbox:
    def __init__(self) -> None:
        self.label       = "Save Project API"
        self.alias       = "SaveProjectAPI"
        self.description = "CRUD toolbox for the PROJECTS feature class in SavedProject.gdb."
        self.tools       = [
            GetAllProjectsTool,
            CreateProjectTool,
            GetProjectByIdTool,
            UpdateProjectTool,
            DeleteProjectTool,
        ]
