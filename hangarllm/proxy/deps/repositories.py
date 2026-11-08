from typing import Annotated, TypeAlias

from fastapi import Depends

from hangarllm.models.deployment_warning import DeploymentWarningIgnoreStore
from hangarllm.models.gateway_activity import GatewayActivityStore
from hangarllm.models.plugin_upload import PluginUploadStore
from hangarllm.models.skill_submission import SkillSubmissionStore
from hangarllm.models.user_banner import UserBannerStore
from hangarllm.proxy.deps.database import DatabaseDep
from hangarllm.repositories.deployment_warning_ignore_repository import DeploymentWarningIgnoreRepository
from hangarllm.repositories.gateway_activity_repository import GatewayActivityRepository
from hangarllm.repositories.plugin_upload_repository import PluginUploadRepository
from hangarllm.repositories.skill_submission_repository import SkillSubmissionRepository
from hangarllm.repositories.user_banner_repository import UserBannerRepository


async def get_user_banner_repository(database: DatabaseDep) -> UserBannerStore | None:
    return None if database is None else UserBannerRepository(database.prisma)


UserBannerRepositoryDep: TypeAlias = Annotated[UserBannerStore | None, Depends(get_user_banner_repository)]


async def get_deployment_warning_ignore_repository(database: DatabaseDep) -> DeploymentWarningIgnoreStore | None:
    return None if database is None else DeploymentWarningIgnoreRepository(database.prisma, use_writer=True)


DeploymentWarningIgnoreRepositoryDep: TypeAlias = Annotated[
    DeploymentWarningIgnoreStore | None, Depends(get_deployment_warning_ignore_repository)
]


async def get_gateway_activity_repository(database: DatabaseDep) -> GatewayActivityStore | None:
    return None if database is None else GatewayActivityRepository(database.prisma)


GatewayActivityRepositoryDep: TypeAlias = Annotated[
    GatewayActivityStore | None, Depends(get_gateway_activity_repository)
]


async def get_plugin_upload_repository(database: DatabaseDep) -> PluginUploadStore | None:
    return None if database is None else PluginUploadRepository(database.prisma)


PluginUploadRepositoryDep: TypeAlias = Annotated[PluginUploadStore | None, Depends(get_plugin_upload_repository)]


async def get_skill_submission_repository(database: DatabaseDep) -> SkillSubmissionStore | None:
    return None if database is None else SkillSubmissionRepository(database.prisma)


SkillSubmissionRepositoryDep: TypeAlias = Annotated[
    SkillSubmissionStore | None, Depends(get_skill_submission_repository)
]
