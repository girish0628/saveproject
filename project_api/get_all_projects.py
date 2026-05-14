"""GET /api/projects — returns all projects accessible to the requesting user."""

import sys
import os

_TOOL_DIR     = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_TOOL_DIR, ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import arcpy

from helpers.project_service import ProjectService
from helpers.utils import get_logger, ResponseModel

logger = get_logger(__name__)


def run(parameters: list, messages: object) -> ResponseModel:
    try:
        user_email = _get_str(parameters, 0)
        if not user_email:
            arcpy.AddError("Parameter 'userEmail' is required.")
            return ResponseModel.error("userEmail is required.", 400)
        response = ProjectService(user_email=user_email).get_all_projects()
        _emit(response)
        return response
    except Exception as exc:
        logger.exception("Unhandled error in GetAllProjects.")
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


class GetAllProjectsTool:
    def __init__(self) -> None:
        self.label             = "Get All Projects"
        self.description       = "Returns all projects accessible to the requesting user."
        self.canRunInBackground = False

    def getParameterInfo(self) -> list:
        p_result = arcpy.Parameter(displayName="Result (JSON)", name="result",
                                   datatype="GPString", parameterType="Derived", direction="Output")
        return [
            arcpy.Parameter(displayName="User Email", name="userEmail",
                            datatype="GPString", parameterType="Required", direction="Input"),
            p_result,
        ]

    def isLicensed(self) -> bool:  return True
    def updateParameters(self, parameters): pass
    def updateMessages(self, parameters):   pass

    def execute(self, parameters, messages):
        response = run(parameters, messages)
        parameters[1].value = response.to_json()

    def postExecute(self, parameters): pass
