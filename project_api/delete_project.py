"""DELETE /api/projects/{id} — permanently removes a project (owner only)."""

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
        project_id = _get_str(parameters, 1)
        if not user_email:
            arcpy.AddError("Parameter 'userEmail' is required.")
            return ResponseModel.error("userEmail is required.", 400)
        if not project_id:
            arcpy.AddError("Parameter 'projectId' is required.")
            return ResponseModel.error("projectId is required.", 400)
        response = ProjectService(user_email=user_email).delete_project(project_id)
        _emit(response)
        return response
    except Exception as exc:
        logger.exception("Unhandled error in DeleteProject.")
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


class DeleteProjectTool:
    def __init__(self) -> None:
        self.label             = "Delete Project"
        self.description       = "Permanently deletes a project. Owner only."
        self.canRunInBackground = False

    def getParameterInfo(self) -> list:
        p_result = arcpy.Parameter(displayName="Result (JSON)", name="result",
                                   datatype="GPString", parameterType="Derived", direction="Output")
        return [
            arcpy.Parameter(displayName="User Email", name="userEmail",
                            datatype="GPString", parameterType="Required", direction="Input"),
            arcpy.Parameter(displayName="Project ID", name="projectId",
                            datatype="GPString", parameterType="Required", direction="Input"),
            p_result,
        ]

    def isLicensed(self) -> bool:  return True
    def updateParameters(self, parameters): pass

    def updateMessages(self, parameters):
        p = parameters[1]
        if p.altered and not p.valueAsText:
            p.setErrorMessage("Project ID is required.")

    def execute(self, parameters, messages):
        response = run(parameters, messages)
        parameters[2].value = response.to_json()

    def postExecute(self, parameters): pass
