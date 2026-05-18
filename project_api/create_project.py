"""POST /api/projects — creates a new project in the PROJECTS feature class."""

import sys
import os
import json as _json

_TOOL_DIR     = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_TOOL_DIR, ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import arcpy

from helpers.constants import (
    FIELD_DESCRIPTION, FIELD_EXTENT, FIELD_GRAPHICS, FIELD_MAP_STATE,
    FIELD_NAME, FIELD_PERMISSIONS, FIELD_SHARED, FIELD_THUMBNAIL, FIELD_WEBMAP_ID,
)
from helpers.project_service import ProjectService
from helpers.utils import get_logger, ResponseModel

logger = get_logger(__name__)


def run(parameters: list, messages: object) -> ResponseModel:
    try:
        user_email = _get_str(parameters, 0)
        if not user_email:
            arcpy.AddError("Parameter 'userEmail' is required.")
            return ResponseModel.error("userEmail is required.", 400)

        name        = _get_str(parameters, 1)
        webmap_id   = _get_str(parameters, 2)
        description = _get_str(parameters, 3)
        extent      = _get_str(parameters, 4)
        map_state   = _get_str(parameters, 5)
        graphics    = _get_str(parameters, 6)
        permissions = _get_str(parameters, 7)
        thumbnail   = _get_str(parameters, 8)
        shared_raw  = _get_str(parameters, 9)

        data = {FIELD_NAME: name, FIELD_WEBMAP_ID: webmap_id}
        if description:  data[FIELD_DESCRIPTION] = description
        if extent:       data[FIELD_EXTENT]       = extent
        if map_state:    data[FIELD_MAP_STATE]    = map_state
        if graphics:     data[FIELD_GRAPHICS]     = graphics
        if permissions:  data[FIELD_PERMISSIONS]  = permissions
        if thumbnail:    data[FIELD_THUMBNAIL]    = thumbnail
        if shared_raw:   data[FIELD_SHARED]       = shared_raw

        portal_url, token = _get_portal_context()
        response = ProjectService(user_email=user_email, portal_url=portal_url, token=token).create_project(data)
        _emit(response)
        return response
    except Exception as exc:
        logger.exception("Unhandled error in CreateProject.")
        arcpy.AddError(f"Internal error: {exc}")
        return ResponseModel.error(str(exc))


def _get_str(parameters: list, index: int) -> str:
    try:
        val = parameters[index].valueAsText
        return val.strip() if val else ""
    except (IndexError, AttributeError):
        return ""


def _get_portal_context():
    portal_url = arcpy.GetActivePortalURL() or ""
    token_info = arcpy.GetSigninToken() or {}
    token = token_info.get("token", "") if isinstance(token_info, dict) else ""
    return portal_url, token


def _emit(response: ResponseModel) -> None:
    payload = response.to_json()
    arcpy.AddMessage(payload) if response.success else arcpy.AddError(payload)


class CreateProjectTool:
    def __init__(self) -> None:
        self.label             = "Create Project"
        self.description       = "Creates a new project in the PROJECTS feature class."
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
        p_shared.value = False
        p_result = arcpy.Parameter(displayName="Result (JSON)", name="result",
                                   datatype="GPString", parameterType="Derived", direction="Output")
        p_thumbnail_out = arcpy.Parameter(displayName="Thumbnail (Base64)", name="thumbnailBase64",
                                          datatype="GPString", parameterType="Derived", direction="Output")
        return [
            _req("User Email",               "userEmail"),
            _req("Project Name",             "name"),
            _req("WebMap ID",                "webmapId"),
            _opt("Description",              "description"),
            _opt("Extent (JSON)",            "extent"),
            _opt("Map State (JSON array)",   "mapState"),
            _opt("Graphics (GeoJSON array)", "graphics"),
            _opt("Permissions",              "permissions"),
            _opt("Thumbnail (Base64)",       "thumbnail"),
            p_shared,
            p_result,
            p_thumbnail_out,
        ]

    def isLicensed(self) -> bool:  return True
    def updateParameters(self, parameters): pass

    def updateMessages(self, parameters):
        n = parameters[1]
        if n.altered and not n.valueAsText:
            n.setErrorMessage("Project Name is required.")
        w = parameters[2]
        if w.altered and not w.valueAsText:
            w.setErrorMessage("WebMap ID is required.")
        e = parameters[4]
        if e.altered and e.valueAsText:
            try:
                parsed = _json.loads(e.valueAsText)
                for key in ("xmin", "xmax", "ymin", "ymax"):
                    if key not in parsed:
                        e.setErrorMessage(f"Extent JSON is missing key: '{key}'")
                        break
            except Exception:
                e.setErrorMessage("Extent must be valid JSON.")

    def execute(self, parameters, messages):
        response = run(parameters, messages)
        arcpy.SetParameterAsText(10, response.to_json())
        if response.success and isinstance(response.data, dict):
            arcpy.SetParameterAsText(11, response.data.get("thumbnail") or "")

    def postExecute(self, parameters): pass
