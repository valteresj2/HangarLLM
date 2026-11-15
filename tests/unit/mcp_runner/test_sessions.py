from typing import Final

import anyio
import pytest

from hangarllm.mcp_runner.sessions import _pump


@pytest.mark.asyncio
async def test_a_session_ends_when_the_gateway_side_closes_even_if_the_server_keeps_running():
    """A stdio server often ignores stdin closing, so waiting for its stdout would keep the sandbox forever."""
    gateway_in, gateway_out = anyio.create_memory_object_stream[object](10)
    server_in, server_out = anyio.create_memory_object_stream[object](10)
    server_stdout_in, server_stdout_out = anyio.create_memory_object_stream[object](10)
    gateway_reply_in, _gateway_reply_out = anyio.create_memory_object_stream[object](10)

    await gateway_in.send("tools/list")
    await gateway_in.aclose()
    with anyio.fail_after(2):
        async with anyio.create_task_group() as session:
            session.start_soon(_pump, gateway_out, server_in, session.cancel_scope)
            session.start_soon(_pump, server_stdout_out, gateway_reply_in, session.cancel_scope)

    forwarded: Final = server_out.receive_nowait()
    server_stdout_in.close()
    assert forwarded == "tools/list"


@pytest.mark.asyncio
async def test_unreadable_messages_are_dropped_and_the_rest_forwarded():
    source_in, source_out = anyio.create_memory_object_stream[object](10)
    sink_in, sink_out = anyio.create_memory_object_stream[object](10)
    await source_in.send(ValueError("bad json"))
    await source_in.send("ping")
    await source_in.aclose()

    with anyio.CancelScope() as scope:
        await _pump(source_out, sink_in, scope)

    assert sink_out.receive_nowait() == "ping"
    with pytest.raises(anyio.WouldBlock):
        sink_out.receive_nowait()
