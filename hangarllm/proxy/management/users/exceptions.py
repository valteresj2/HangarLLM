from hangarllm.proxy.list_api.common import PROBLEM_TYPE_BASE, ManagementProblem
from hangarllm.types.proxy.management_endpoints.management_v1 import ProblemDetail


def current_user_not_found() -> ManagementProblem:
    return ManagementProblem(
        ProblemDetail(
            type=f"{PROBLEM_TYPE_BASE}user-not-found",
            title="User not found",
            status=404,
            detail="The key used for this request is not bound to a user.",
        )
    )
