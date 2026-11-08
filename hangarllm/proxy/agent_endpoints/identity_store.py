import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Final

from hangarllm._internal_context import with_service_target
from hangarllm.proxy.agent_endpoints.managed_identity import classify_agent_subject
from hangarllm.proxy.common_utils.user_api_key_cache import UserApiKeyCache, get_management_object_ttl
from hangarllm.repositories.table_repositories import (
    AgentIdentityRepository,
    AgentsRepository,
    RetiredAgentIdentityRepository,
    RetiredAgentRepository,
    VerifiedSubjectRepository,
)
from hangarllm.types.agents import AgentResponse
from hangarllm.types.proxy.agent_identity import (
    AgentIdentityFailure,
    ManagedAgentContext,
    MicrosoftInteractiveSubject,
    VerifiedHumanSubject,
)

_AGENT_IDENTITIES_TARGET: Final = "agent_identities"

if TYPE_CHECKING:
    from prisma.models import HangarLLM_VerifiedSubject
    from prisma.types import (
        HangarLLM_AgentIdentityUpdateManyMutationInput,
        HangarLLM_AgentIdentityWhereInput,
        HangarLLM_AgentIdentityWhereUniqueInput,
        HangarLLM_AgentsTableInclude,
        HangarLLM_AgentsTableWhereUniqueInput,
        HangarLLM_RetiredAgentWhereUniqueInput,
        HangarLLM_VerifiedSubjectCreateInput,
        HangarLLM_VerifiedSubjectUpsertInput,
        HangarLLM_VerifiedSubjectWhereUniqueInput,
    )


class AgentIdentityStore:
    @classmethod
    def from_client(cls, client: object, *, cache: UserApiKeyCache | None = None) -> "AgentIdentityStore":
        return cls(
            AgentsRepository(client, use_writer=True),
            AgentIdentityRepository(client, use_writer=True),
            VerifiedSubjectRepository(client, use_writer=True),
            RetiredAgentIdentityRepository(client, use_writer=True),
            RetiredAgentRepository(client, use_writer=True),
            cache=cache,
        )

    def __init__(
        self,
        agents: AgentsRepository,
        identities: AgentIdentityRepository,
        humans: VerifiedSubjectRepository,
        retired: RetiredAgentIdentityRepository | None = None,
        retired_agents: RetiredAgentRepository | None = None,
        *,
        cache: UserApiKeyCache | None = None,
    ) -> None:
        self.agents = agents
        self.identities = identities
        self.humans = humans
        self.retired = retired
        self.retired_agents = retired_agents
        self.cache = cache

    async def agent(self, agent_id: str) -> AgentResponse | AgentIdentityFailure | None:
        try:
            where: Final[HangarLLM_AgentsTableWhereUniqueInput] = {"agent_id": agent_id}
            include: Final[HangarLLM_AgentsTableInclude] = {
                "identity": True,
                "object_permission": True,
            }
            row: Final = await self.agents.table.find_unique(where=where, include=include)
            if row is None:
                return None
            return AgentResponse.model_validate(row.model_dump())
        except Exception:
            return AgentIdentityFailure(code="policy_unavailable", message="Agent policy could not be loaded")

    async def unbound_client(self, where: "HangarLLM_AgentIdentityWhereUniqueInput") -> AgentIdentityFailure | None:
        if self.retired is not None:
            try:
                retired: Final = await self.retired.table.find_unique(where=where)
            except Exception:
                return AgentIdentityFailure(
                    code="policy_unavailable", message="Retired agent identity could not be checked"
                )
            if retired is not None:
                return AgentIdentityFailure(message="This agent identity binding has been retired")
        return None

    @with_service_target(_AGENT_IDENTITIES_TARGET)
    async def _bound_agent_id(self, tenant_id: str, client_id: str) -> str | AgentIdentityFailure | None:
        cache_key: Final = f"agent_identity:{json.dumps((tenant_id, client_id))}"
        cached: Final[object] = await self.cache.async_get_cache(key=cache_key) if self.cache is not None else None
        if isinstance(cached, str):
            return cached
        where: Final[HangarLLM_AgentIdentityWhereUniqueInput] = {
            "provider_tenant_id_client_id": {
                "provider": "microsoft_entra",
                "tenant_id": tenant_id,
                "client_id": client_id,
            }
        }
        try:
            row: Final = await self.identities.table.find_unique(where=where)
        except Exception:
            return AgentIdentityFailure(code="policy_unavailable", message="Agent identity could not be loaded")
        if row is None:
            return await self.unbound_client(where)
        if self.cache is not None:
            await self.cache.async_set_cache(
                key=cache_key, value=row.agent_id, ttl=get_management_object_ttl(self.cache)
            )
        return row.agent_id

    async def resolve_verified_claims(
        self, claims: Mapping[str, object]
    ) -> ManagedAgentContext | AgentIdentityFailure | None:
        issuer: Final = claims.get("iss")
        tenant: Final = claims.get("tid")
        client: Final = claims.get("azp")
        if not isinstance(issuer, str) or not isinstance(tenant, str) or not isinstance(client, str):
            return None
        agent_id: Final = await self._bound_agent_id(tenant, client)
        if agent_id is None or isinstance(agent_id, AgentIdentityFailure):
            return agent_id
        agent: Final = await self.agent(agent_id)
        if isinstance(agent, AgentIdentityFailure):
            return agent
        if (
            agent is None
            or not agent.identity_managed
            or not agent.enabled
            or agent.identity is None
            or not agent.identity.active
        ):
            return AgentIdentityFailure(message="Agent is disabled or no longer bound to an identity")
        subject: Final = classify_agent_subject(agent.identity, claims, agent.execution_mode)
        if isinstance(subject, AgentIdentityFailure):
            return subject
        if subject.kind == "application":
            return ManagedAgentContext(
                agent_id=agent.agent_id,
                binding_revision=agent.identity.revision,
                mode=subject.mode,
                subject_oid=subject.oid,
            )
        proven: Final = await self.subject(issuer, tenant, claims.get("oid"))
        if isinstance(proven, AgentIdentityFailure):
            return proven
        human: Final = (
            VerifiedHumanSubject.model_validate(proven.model_dump())
            if proven is not None
            and proven.kind == "human"
            and proven.verified_via == "sso_interactive"
            and proven.user_id is not None
            else None
        )
        if human is None:
            return AgentIdentityFailure(message="The delegated user must first sign in through trusted Microsoft SSO")
        return ManagedAgentContext(
            agent_id=agent.agent_id,
            binding_revision=agent.identity.revision,
            mode=subject.mode,
            user_id=human.user_id,
            subject_oid=subject.oid,
        )

    async def subject(
        self, issuer: str, tenant_id: str, oid: object
    ) -> "HangarLLM_VerifiedSubject | AgentIdentityFailure | None":
        if not isinstance(oid, str):
            return None
        try:
            where: Final[HangarLLM_VerifiedSubjectWhereUniqueInput] = {
                "issuer_tenant_id_oid": {"issuer": issuer, "tenant_id": tenant_id, "oid": oid}
            }
            return await self.humans.table.find_unique(where=where)
        except Exception:
            return AgentIdentityFailure(code="policy_unavailable", message="Subject classification is unavailable")

    async def retired_agent(self, agent_id: str) -> bool | AgentIdentityFailure:
        if self.retired_agents is None:
            return AgentIdentityFailure(code="policy_unavailable", message="Agent history is unavailable")
        try:
            where: Final[HangarLLM_RetiredAgentWhereUniqueInput] = {"original_agent_id": agent_id}
            return await self.retired_agents.table.find_unique(where=where) is not None
        except Exception:
            return AgentIdentityFailure(code="policy_unavailable", message="Agent history is unavailable")

    async def record_authentication(self, context: ManagedAgentContext) -> AgentIdentityFailure | None:
        try:
            if context.binding_revision is None:
                return AgentIdentityFailure(message="Agent authentication requires a binding revision")
            where: Final[HangarLLM_AgentIdentityWhereInput] = {
                "agent_id": context.agent_id,
                "revision": context.binding_revision,
                "active": True,
                "agent": {"is": {"enabled": True, "identity_managed": True}},
            }
            data: Final[HangarLLM_AgentIdentityUpdateManyMutationInput] = {
                "last_authenticated_at": datetime.now(timezone.utc)
            }
            count: Final = await self.identities.table.update_many(where=where, data=data)
            if count != 1:
                return AgentIdentityFailure(message="Agent identity changed during authentication; retry")
            return None
        except Exception:
            return AgentIdentityFailure(code="policy_unavailable", message="Agent authentication could not be recorded")

    async def enroll_interactive_human(
        self,
        subject: MicrosoftInteractiveSubject,
        user_id: str,
    ) -> AgentIdentityFailure | None:
        try:
            where: Final[HangarLLM_VerifiedSubjectWhereUniqueInput] = {
                "issuer_tenant_id_oid": {"issuer": subject.issuer, "tenant_id": subject.tenant_id, "oid": subject.oid}
            }
            create_data: Final[HangarLLM_VerifiedSubjectCreateInput] = {
                "issuer": subject.issuer,
                "tenant_id": subject.tenant_id,
                "oid": subject.oid,
                "user_id": user_id,
                "verified_via": "sso_interactive",
            }
            data: Final[HangarLLM_VerifiedSubjectUpsertInput] = {"create": create_data, "update": {}}
            row: Final = await self.humans.table.upsert(where=where, data=data)
            if row.kind != "human" or row.user_id != user_id or row.verified_via != "sso_interactive":
                return AgentIdentityFailure(message="Microsoft subject is already bound to another local identity")
            return None
        except Exception:
            return AgentIdentityFailure(
                code="policy_unavailable", message="Microsoft subject enrollment is unavailable"
            )


async def resolve_managed_agent(
    claims: Mapping[str, object],
    client: object,
    *,
    cache: UserApiKeyCache | None = None,
) -> ManagedAgentContext | None:
    from hangarllm.proxy.agent_endpoints.managed_identity import raise_identity_failure

    if client is None:
        return None
    result: Final = await AgentIdentityStore.from_client(client, cache=cache).resolve_verified_claims(claims)
    if isinstance(result, AgentIdentityFailure):
        raise_identity_failure(result)
    return result
