"""PUT /api/projects/{id} — updates mutable fields of a project (owner only)."""

import sys
import os

_TOOL_DIR     = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_TOOL_DIR, ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import arcpy

from helpers.constants import (
    FIELD_DESCRIPTION, FIELD_EXTENT, FIELD_GRAPHICS, FIELD_MAP_STATE,
    FIELD_NAME, FIELD_PERMISSIONS, FIELD_SHARED, FIELD_THUMBNAIL,
)
from helpers.project_service import ProjectService
from helpers.utils import get_logger, ResponseModel

logger = get_logger(__name__)


def run(parameters: list, messages: object) -> ResponseModel:
    try:
        user_email = _get_str(parameters, 0)
        project_id = _get_str(parameters, 1)
        if not user_email:
            arcpy.AddError("Parameter 'userEmail' is required.")
            return ResponseModel.error("userEmail is required.", 400)
        if not project_id:
            arcpy.AddError("Parameter 'projectId' is required.")
            return ResponseModel.error("projectId is required.", 400)

        name        = _get_str(parameters, 2)
        description = _get_str(parameters, 3)
        extent      = _get_str(parameters, 4)
        map_state   = _get_str(parameters, 5)
        graphics    = _get_str(parameters, 6)
        permissions = _get_str(parameters, 7)
        thumbnail   = _get_str(parameters, 8)
        shared_raw  = _get_str(parameters, 9)

        data: dict = {}
        if name:        data[FIELD_NAME]        = name
        if description: data[FIELD_DESCRIPTION] = description
        if extent:      data[FIELD_EXTENT]       = extent
        if map_state:   data[FIELD_MAP_STATE]    = map_state
        if graphics:    data[FIELD_GRAPHICS]     = graphics
        if permissions: data[FIELD_PERMISSIONS]  = permissions
        if thumbnail:   data[FIELD_THUMBNAIL]    = thumbnail
        if shared_raw:  data[FIELD_SHARED]       = shared_raw

        if not data:
            arcpy.AddWarning("No update fields provided.")
            return ResponseModel.error("No updatable fields provided.", 400)

        response = ProjectService(user_email=user_email).update_project(project_id, data)
        _emit(response)
        return response
    except Exception as exc:
        logger.exception("Unhandled error in UpdateProject.")
        arcpy.AddError(f"Internal error: {exc}")
        return ResponseModel.error(str(exc))


def _get_str(parameters: list, index: int) -> str:
    try:
        val = parameters[index].valueAsText
        return val.strip() if val else ""
    except (IndexError, AttributeError):
        return ""


def _emit(response: ResponseModel) -> None:
    payload = response.to_json()
    arcpy.AddMessage(payload) if response.success else arcpy.AddError(payload)


class UpdateProjectTool:
    def __init__(self) -> None:
        self.label             = "Update Project"
        self.description       = "Updates mutable fields of a project. Owner only."
        self.canRunInBackground = False

    def getParameterInfo(self) -> list:
        def _req(display, name):
            return arcpy.Parameter(displayName=display, name=name,
                                   datatype="GPString", parameterType="Required", direction="Input")
        def _opt(display, name):
            return arcpy.Parameter(displayName=display, name=name,
                                   datatype="GPString", parameterType="Optional", direction="Input")
        p_shared = arcpy.Parameter(displayName="Shared", name="shared",
                                   datatype="GPBoolean", parameterType="Optional", direction="Input")
        p_result = arcpy.Parameter(displayName="Result (JSON)", name="result",
                                   datatype="GPString", parameterType="Derived", direction="Output")
        return [
            _req("User Email",               "userEmail"),
            _req("Project ID",               "projectId"),
            _opt("Project Name",             "name"),
            _opt("Description",              "description"),
            _opt("Extent (JSON)",            "extent"),
            _opt("Map State (JSON array)",   "mapState"),
            _opt("Graphics (GeoJSON array)", "graphics"),
            _opt("Permissions",              "permissions"),
            _opt("Thumbnail (Base64)",       "thumbnail"),
            p_shared,
            p_result,
        ]

    def isLicensed(self) -> bool:  return True
    def updateParameters(self, parameters): pass

    def updateMessages(self, parameters):
        n = parameters[2]
        if n.altered and n.valueAsText == "":
            n.setErrorMessage("Name cannot be blank when provided for update.")

    def execute(self, parameters, messages):
        response = run(parameters, messages)
        parameters[10].value = response.to_json()

    def postExecute(self, parameters): pass
