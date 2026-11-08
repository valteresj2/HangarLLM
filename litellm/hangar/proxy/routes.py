"""All HTTP routes HangarLLM adds on top of core, mounted by ``proxy_server`` as one router."""

from fastapi import APIRouter

from litellm.hangar.decisions.endpoints import router as decisions_formats_router
from litellm.hangar.emails.endpoints import router as email_router
from litellm.hangar.proxy.audit_logs import router as audit_router
from litellm.hangar.proxy.projects import router as project_router
from litellm.hangar.skill_sync.endpoints import router as skill_sync_router

router = APIRouter()
router.include_router(audit_router)
router.include_router(email_router)
router.include_router(project_router)
router.include_router(skill_sync_router)
router.include_router(decisions_formats_router)
