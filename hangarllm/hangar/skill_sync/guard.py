"""Keep Git-managed skills read-only in the hub so the repository stays the single source of truth."""

from typing import Final


async def git_source_managing(name: str) -> str | None:
    from hangarllm.proxy.proxy_server import prisma_client

    if prisma_client is None:
        return None
    try:
        row: Final = await prisma_client.db.hangarllm_skillgitsource.find_first(where={"managed_skills": {"has": name}})
    except Exception as error:  # noqa: BLE001  # soft guard: the next sync re-applies the repository version anyway
        from hangarllm._logging import verbose_proxy_logger

        verbose_proxy_logger.debug("Git-managed skill lookup failed for %s: %s", name, error)
        return None
    return None if row is None else row.name


def managed_message(source_name: str) -> str:
    return (
        f"This skill is managed by the GitHub source '{source_name}'. "
        "Change it in the repository and the next sync will apply it."
    )
