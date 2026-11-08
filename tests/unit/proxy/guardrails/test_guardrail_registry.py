import json
from collections.abc import Iterable, Iterator
from typing import ClassVar, Final
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from hangarllm.integrations.custom_guardrail import CustomGuardrail
from hangarllm.proxy.guardrails.guardrail_registry import (
    GuardrailRegistry,
    InMemoryGuardrailHandler,
    get_guardrail_initializer_from_hooks,
    parse_tolerant_hangarllm_params,
)
from hangarllm.types.guardrails import Guardrail, GuardrailEventHooks, HangarllmParams, LoggingOnlyScope, Mode
from hangarllm.types.utils import GenericGuardrailAPIInputs


def test_get_guardrail_initializer_from_hooks():
    initializers = get_guardrail_initializer_from_hooks()
    assert "aim" in initializers


def test_guardrail_class_registry():
    from hangarllm.proxy.guardrails.guardrail_registry import guardrail_class_registry

    assert "aim" in guardrail_class_registry
    assert "aporia" in guardrail_class_registry


def test_noma_registry_resolution():
    from hangarllm.proxy.guardrails.guardrail_hooks.noma.noma import NomaGuardrail
    from hangarllm.proxy.guardrails.guardrail_hooks.noma.noma_v2 import NomaV2Guardrail
    from hangarllm.proxy.guardrails.guardrail_registry import (
        guardrail_class_registry,
        guardrail_initializer_registry,
    )

    assert guardrail_class_registry["noma"] is NomaGuardrail
    assert guardrail_class_registry["noma_v2"] is NomaV2Guardrail
    assert "noma" in guardrail_initializer_registry
    assert "noma_v2" in guardrail_initializer_registry


@pytest.mark.parametrize(
    "configured, expected",
    [(None, True), (False, False), (True, True)],
)
def test_initialize_guardrail_run_in_parallel_preserves_constructor_default(configured, expected):
    """
    A guardrail whose constructor sets run_in_parallel=True must keep that default when
    the config omits the key; only an explicit config value may override it. The
    previous code wrote bool(None)==False on every instance, silently disabling the
    opt-in for such guardrails.
    """
    from hangarllm.proxy.guardrails import guardrail_registry as registry_module

    def _initializer(hangarllm_params, guardrail):
        return CustomGuardrail(
            guardrail_name=guardrail["guardrail_name"],
            event_hook=GuardrailEventHooks.pre_call,
            default_on=True,
            run_in_parallel=True,
        )

    registry_module.guardrail_initializer_registry["parallel_default_test"] = _initializer
    try:
        params = {"guardrail": "parallel_default_test", "mode": "pre_call"}
        if configured is not None:
            params["run_in_parallel"] = configured

        handler = InMemoryGuardrailHandler()
        result = handler.initialize_guardrail(
            guardrail={"guardrail_name": "cf-parallel-default", "hangarllm_params": params},
        )

        stored = handler.guardrail_id_to_custom_guardrail[result["guardrail_id"]]
        assert stored.run_in_parallel is expected
    finally:
        registry_module.guardrail_initializer_registry.pop("parallel_default_test", None)


def _register_noop_initializer(guardrail_type: str):
    from hangarllm.proxy.guardrails import guardrail_registry as registry_module

    def _initializer(hangarllm_params, guardrail):
        return CustomGuardrail(
            guardrail_name=guardrail["guardrail_name"],
            event_hook=GuardrailEventHooks.pre_call,
            default_on=False,
        )

    registry_module.guardrail_initializer_registry[guardrail_type] = _initializer
    return registry_module


def _config_guardrail(name: str, guardrail_type: str, guardrail_id=None) -> dict:
    guardrail = {
        "guardrail_name": name,
        "hangarllm_params": {"guardrail": guardrail_type, "mode": "pre_call"},
    }
    if guardrail_id is not None:
        guardrail["guardrail_id"] = guardrail_id
    return guardrail


def test_config_guardrail_id_is_stable_across_boots():
    """
    Config guardrails used to get a fresh uuid4 per process, so ids from a
    previous boot (or another replica) 404'd on /guardrails/{id}/info even
    though the guardrail was alive.
    """
    registry_module = _register_noop_initializer("stable_id_test")
    try:
        first_boot = InMemoryGuardrailHandler().initialize_guardrail(
            guardrail=_config_guardrail("tooling", "stable_id_test")
        )
        second_boot = InMemoryGuardrailHandler().initialize_guardrail(
            guardrail=_config_guardrail("tooling", "stable_id_test")
        )

        assert first_boot["guardrail_id"] == second_boot["guardrail_id"]
    finally:
        registry_module.guardrail_initializer_registry.pop("stable_id_test", None)


def test_explicit_config_guardrail_id_wins_over_derived_id():
    registry_module = _register_noop_initializer("explicit_id_test")
    try:
        result = InMemoryGuardrailHandler().initialize_guardrail(
            guardrail=_config_guardrail("tooling", "explicit_id_test", guardrail_id="my-explicit-id")
        )

        assert result["guardrail_id"] == "my-explicit-id"
    finally:
        registry_module.guardrail_initializer_registry.pop("explicit_id_test", None)


def test_duplicate_config_guardrail_names_get_distinct_stable_ids():
    """
    Duplicate guardrail_name entries are legitimate (load balancing across
    deployments); each occurrence must keep its own id, stable across boots.
    """
    registry_module = _register_noop_initializer("dup_name_test")
    try:
        handler = InMemoryGuardrailHandler()
        first = handler.initialize_guardrail(guardrail=_config_guardrail("dup", "dup_name_test"))
        second = handler.initialize_guardrail(guardrail=_config_guardrail("dup", "dup_name_test"))

        rebooted_handler = InMemoryGuardrailHandler()
        rebooted_first = rebooted_handler.initialize_guardrail(guardrail=_config_guardrail("dup", "dup_name_test"))
        rebooted_second = rebooted_handler.initialize_guardrail(guardrail=_config_guardrail("dup", "dup_name_test"))

        assert first["guardrail_id"] != second["guardrail_id"]
        assert first["guardrail_id"] == rebooted_first["guardrail_id"]
        assert second["guardrail_id"] == rebooted_second["guardrail_id"]
        assert len(handler.IN_MEMORY_GUARDRAILS) == 2
    finally:
        registry_module.guardrail_initializer_registry.pop("dup_name_test", None)


def test_initialize_guardrail_treats_invalid_stored_scope_as_both():
    from hangarllm.proxy.guardrails import guardrail_registry as registry_module

    guardrail_type: Final = "invalid_stored_scope_test"

    def _initializer(hangarllm_params: HangarllmParams, guardrail: Guardrail) -> CustomGuardrail:
        return CustomGuardrail(
            guardrail_name=guardrail["guardrail_name"],
            event_hook=GuardrailEventHooks(hangarllm_params.mode),
            default_on=True,
        )

    registry_module.guardrail_initializer_registry[guardrail_type] = _initializer
    try:
        handler: Final = InMemoryGuardrailHandler()
        guardrail: Final = Guardrail(
            guardrail_id="invalid-stored-scope",
            guardrail_name="invalid-stored-scope",
            hangarllm_params={
                "guardrail": guardrail_type,
                "mode": "pre_call",
                "default_on": True,
                "stream_scope": "sometimes",
            },
        )

        parsed_guardrail: Final = handler.initialize_guardrail(guardrail=guardrail, source="db")
        callback: Final = handler.guardrail_id_to_custom_guardrail["invalid-stored-scope"]

        assert parsed_guardrail["hangarllm_params"].stream_scope is None
        assert callback is not None
        assert callback.should_run_guardrail(data={}, event_type=GuardrailEventHooks.pre_call) is True
        assert callback.should_run_guardrail(data={"stream": True}, event_type=GuardrailEventHooks.pre_call) is True
    finally:
        registry_module.guardrail_initializer_registry.pop(guardrail_type, None)


def _register_mode_following_initializer(guardrail_type: str):
    """Registers like the shipped initializers do: construct, then add the instance to hangarllm's callbacks."""
    import hangarllm
    from hangarllm.proxy.guardrails import guardrail_registry as registry_module

    def _initializer(hangarllm_params, guardrail):
        callback = CustomGuardrail(
            guardrail_name=guardrail["guardrail_name"],
            supported_event_hooks=[GuardrailEventHooks.pre_call, GuardrailEventHooks.post_call],
            event_hook=GuardrailEventHooks(hangarllm_params.mode),
            default_on=True,
        )
        hangarllm.logging_callback_manager.add_hangarllm_callback(callback)
        return callback

    registry_module.guardrail_initializer_registry[guardrail_type] = _initializer
    return registry_module


def _mode_following_db_row(guardrail_id: str, mode: str, description: str = "") -> Guardrail:
    """The raw row GuardrailRegistry.update_guardrail_in_db hands back: hangarllm_params is a plain dict."""
    return Guardrail(
        guardrail_id=guardrail_id,
        guardrail_name="mode-following",
        hangarllm_params={"guardrail": "mode_following_test", "mode": mode, "default_on": True},
        guardrail_info={"description": description},
    )


def _live_instances_named(name: str) -> int:
    return sum(1 for cb_list in _all_callback_lists() for cb in cb_list if getattr(cb, "guardrail_name", None) == name)


def test_update_in_memory_guardrail_raw_db_row_mode_change_gates_at_the_new_stage():
    registry_module = _register_mode_following_initializer("mode_following_test")
    lists = _all_callback_lists()
    snapshots = [list(cb_list) for cb_list in lists]
    try:
        handler = InMemoryGuardrailHandler()
        handler.initialize_guardrail(guardrail=_mode_following_db_row("123", "pre_call"), source="db")
        original = handler.guardrail_id_to_custom_guardrail["123"]

        handler.update_in_memory_guardrail("123", _mode_following_db_row("123", "post_call"))

        replacement = handler.guardrail_id_to_custom_guardrail["123"]
        assert replacement is not original
        assert replacement.should_run_guardrail(data={}, event_type=GuardrailEventHooks.post_call) is True
        assert replacement.should_run_guardrail(data={}, event_type=GuardrailEventHooks.pre_call) is False
        assert all(original not in cb_list for cb_list in lists)
        assert _live_instances_named("mode-following") == 1
        assert handler.IN_MEMORY_GUARDRAILS["123"]["hangarllm_params"].mode == "post_call"
        assert handler.get_source("123") == "db"
    finally:
        registry_module.guardrail_initializer_registry.pop("mode_following_test", None)
        for cb_list, snapshot in zip(lists, snapshots):
            cb_list[:] = snapshot


def test_update_in_memory_guardrail_unchanged_params_keep_the_live_instance():
    registry_module = _register_mode_following_initializer("mode_following_test")
    lists = _all_callback_lists()
    snapshots = [list(cb_list) for cb_list in lists]
    try:
        handler = InMemoryGuardrailHandler()
        handler.initialize_guardrail(guardrail=_mode_following_db_row("123", "pre_call", "old"), source="db")
        original = handler.guardrail_id_to_custom_guardrail["123"]

        handler.update_in_memory_guardrail("123", _mode_following_db_row("123", "pre_call", "new"))

        assert handler.guardrail_id_to_custom_guardrail["123"] is original
        assert handler.IN_MEMORY_GUARDRAILS["123"]["guardrail_info"] == {"description": "new"}
        assert _live_instances_named("mode-following") == 1
    finally:
        registry_module.guardrail_initializer_registry.pop("mode_following_test", None)
        for cb_list, snapshot in zip(lists, snapshots):
            cb_list[:] = snapshot


def test_update_in_memory_guardrail_invalid_row_keeps_the_previous_instance_enforcing():
    registry_module = _register_mode_following_initializer("mode_following_test")
    lists = _all_callback_lists()
    snapshots = [list(cb_list) for cb_list in lists]
    try:
        handler = InMemoryGuardrailHandler()
        handler.initialize_guardrail(guardrail=_mode_following_db_row("123", "pre_call"), source="db")

        with pytest.raises(ValueError, match="not in the supported event hooks"):
            handler.update_in_memory_guardrail("123", _mode_following_db_row("123", "during_call"))

        restored = handler.guardrail_id_to_custom_guardrail["123"]
        assert restored.should_run_guardrail(data={}, event_type=GuardrailEventHooks.pre_call) is True
        assert handler.IN_MEMORY_GUARDRAILS["123"]["hangarllm_params"].mode == "pre_call"
        assert _live_instances_named("mode-following") == 1
    finally:
        registry_module.guardrail_initializer_registry.pop("mode_following_test", None)
        for cb_list, snapshot in zip(lists, snapshots):
            cb_list[:] = snapshot


def _make_guardrail(guardrail_id: str, name: str = "g") -> Guardrail:
    return Guardrail(
        guardrail_id=guardrail_id,
        guardrail_name=name,
        hangarllm_params=HangarllmParams(guardrail=name, mode="pre_call", default_on=False),
    )


def test_reconcile_db_guardrails_drops_stale_db_entries_only():
    """
    The reconcile pass must drop in-memory entries marked source='db' that are
    missing from the DB result, and never touch source='config' entries.
    Models the multi-pod case where another pod deleted a DB-backed guardrail.
    """
    handler = InMemoryGuardrailHandler()

    # Two DB-backed entries on this pod (synced from earlier polling cycles)
    handler.IN_MEMORY_GUARDRAILS["db-keep"] = _make_guardrail("db-keep")
    handler.IN_MEMORY_GUARDRAILS["db-stale"] = _make_guardrail("db-stale")
    handler._sources["db-keep"] = "db"
    handler._sources["db-stale"] = "db"

    # One config-loaded entry that must survive reconciliation
    handler.IN_MEMORY_GUARDRAILS["cfg"] = _make_guardrail("cfg")
    handler._sources["cfg"] = "config"

    # The DB now only contains db-keep — db-stale was deleted on another pod.
    removed = handler.reconcile_db_guardrails(db_guardrail_ids={"db-keep"})

    assert removed == ["db-stale"]
    assert "db-stale" not in handler.IN_MEMORY_GUARDRAILS
    assert "db-stale" not in handler._sources
    assert "db-keep" in handler.IN_MEMORY_GUARDRAILS
    assert "cfg" in handler.IN_MEMORY_GUARDRAILS
    assert handler._sources["cfg"] == "config"


def test_reconcile_does_not_drop_config_entries_missing_from_db():
    """A config-only guardrail (no DB row) must never be reconciled away."""
    handler = InMemoryGuardrailHandler()
    handler.IN_MEMORY_GUARDRAILS["cfg-only"] = _make_guardrail("cfg-only")
    handler._sources["cfg-only"] = "config"

    removed = handler.reconcile_db_guardrails(db_guardrail_ids=set())

    assert removed == []
    assert "cfg-only" in handler.IN_MEMORY_GUARDRAILS


def test_get_source_returns_marker_set_at_insert():
    handler = InMemoryGuardrailHandler()
    handler.IN_MEMORY_GUARDRAILS["a"] = _make_guardrail("a")
    handler._sources["a"] = "db"
    handler.IN_MEMORY_GUARDRAILS["b"] = _make_guardrail("b")
    handler._sources["b"] = "config"

    assert handler.get_source("a") == "db"
    assert handler.get_source("b") == "config"
    assert handler.get_source("missing") is None


def test_delete_in_memory_guardrail_clears_source_marker():
    handler = InMemoryGuardrailHandler()
    handler.IN_MEMORY_GUARDRAILS["a"] = _make_guardrail("a")
    handler._sources["a"] = "db"

    handler.delete_in_memory_guardrail("a")

    assert "a" not in handler.IN_MEMORY_GUARDRAILS
    assert "a" not in handler._sources
    assert handler.get_source("a") is None


def test_list_config_guardrails_excludes_db_sourced():
    """LIT-2529: read surfaces union DB rows with config guardrails; db-sourced
    in-memory entries would double-count (or resurrect stale ones), so exclude them."""
    handler = InMemoryGuardrailHandler()
    handler.IN_MEMORY_GUARDRAILS["cfg"] = _make_guardrail("cfg", name="config-one")
    handler._sources["cfg"] = "config"
    handler.IN_MEMORY_GUARDRAILS["db"] = _make_guardrail("db", name="db-one")
    handler._sources["db"] = "db"

    config_guardrails = handler.list_config_guardrails()

    assert [g["guardrail_id"] for g in config_guardrails] == ["cfg"]


def test_get_config_guardrail_by_id_returns_config_only():
    """LIT-2529: the detail/logs fallback must return config-owned guardrails and
    treat a db-sourced (stale) or missing id as a miss."""
    handler = InMemoryGuardrailHandler()
    handler.IN_MEMORY_GUARDRAILS["cfg"] = _make_guardrail("cfg", name="config-one")
    handler._sources["cfg"] = "config"
    handler.IN_MEMORY_GUARDRAILS["db"] = _make_guardrail("db", name="db-one")
    handler._sources["db"] = "db"

    assert handler.get_config_guardrail_by_id("cfg")["guardrail_name"] == "config-one"
    assert handler.get_config_guardrail_by_id("db") is None
    assert handler.get_config_guardrail_by_id("missing") is None


def test_initialize_guardrail_early_return_updates_source_marker():
    """
    When initialize_guardrail is called for a guardrail that already exists
    in memory, the early-return path must still honor the caller's source.
    Otherwise a racing polling tick that placed a DB entry in memory first
    would leave a later config-init call wrongly marked as 'db' (or vice
    versa), and the entry would be reconciled with the wrong classification.
    """
    handler = InMemoryGuardrailHandler()
    # Simulate a polling tick already placing the entry as DB-backed.
    handler.IN_MEMORY_GUARDRAILS["collide"] = _make_guardrail("collide", name="bedrock")
    handler._sources["collide"] = "db"

    # Config init re-visits the same id (e.g., hot-reload, or UUID collision).
    g = Guardrail(
        guardrail_id="collide",
        guardrail_name="bedrock",
        hangarllm_params=HangarllmParams(guardrail="bedrock", mode="pre_call", default_on=False),
    )
    handler.initialize_guardrail(guardrail=g, source="config")

    assert handler.get_source("collide") == "config"

    # And the symmetric direction: db sync should override an entry left
    # marked as 'config' from a stale init path.
    handler.initialize_guardrail(guardrail=g, source="db")
    assert handler.get_source("collide") == "db"


def test_sync_guardrail_from_db_marks_source_db_when_unchanged():
    """
    sync_guardrail_from_db must enforce source='db' even when params are
    unchanged, so a config entry whose UUID happens to collide with a later
    DB row gets re-tagged correctly.
    """
    handler = InMemoryGuardrailHandler()
    g = _make_guardrail("collide")
    handler.IN_MEMORY_GUARDRAILS["collide"] = g
    handler._sources["collide"] = "config"

    handler.sync_guardrail_from_db(g)

    assert handler.get_source("collide") == "db"


def test_sync_guardrail_from_db_reject_flag_keeps_callback_order_on_noop_update():
    """
    The PUT endpoint syncs the whole object with reject_invalid_logging_only_scope=True.
    That strictness must not force a teardown + re-append of an unchanged guardrail:
    initialize_guardrail appends the rebuilt callback at the END of hangarllm.callbacks,
    so a description-only PUT would reorder guardrails and change which one wins
    between a BLOCK and a MASK guardrail over the same content.
    """
    import hangarllm

    registry_module = _register_mode_following_initializer("mode_following_test")
    lists = _all_callback_lists()
    snapshots = [list(cb_list) for cb_list in lists]
    sentinel: Final = CustomGuardrail(
        guardrail_name="order-sentinel",
        supported_event_hooks=[GuardrailEventHooks.pre_call],
        event_hook=GuardrailEventHooks.pre_call,
    )
    try:
        handler = InMemoryGuardrailHandler()
        handler.initialize_guardrail(guardrail=_mode_following_db_row("123", "pre_call"), source="db")
        original = handler.guardrail_id_to_custom_guardrail["123"]
        assert original is not None
        hangarllm.callbacks.append(sentinel)
        index_before = hangarllm.callbacks.index(original)

        handler.sync_guardrail_from_db(
            guardrail=_mode_following_db_row("123", "pre_call", "description-only edit"),
            reject_invalid_logging_only_scope=True,
        )

        assert handler.guardrail_id_to_custom_guardrail["123"] is original
        assert hangarllm.callbacks.index(original) == index_before
        assert _live_instances_named("mode-following") == 1
    finally:
        registry_module.guardrail_initializer_registry.pop("mode_following_test", None)
        for cb_list, snapshot in zip(lists, snapshots):
            cb_list[:] = snapshot


def test_sync_guardrail_from_db_reject_flag_still_rejects_invalid_unchanged_scope():
    """
    A PUT sends the whole object, so an unchanged row that already carries an
    invalid logging_only_scope (tolerated at load) must still be rejected on the
    strict sync path, without rebuilding the live callback.
    """
    registry_module = _register_mode_following_initializer("mode_following_test")
    lists = _all_callback_lists()
    snapshots = [list(cb_list) for cb_list in lists]
    row: Final = Guardrail(
        guardrail_id="123",
        guardrail_name="mode-following",
        hangarllm_params={
            "guardrail": "mode_following_test",
            "mode": "pre_call",
            "default_on": True,
            "logging_only_scope": "input",
        },
        guardrail_info={},
    )
    try:
        handler = InMemoryGuardrailHandler()
        handler.initialize_guardrail(guardrail=row, source="db")
        original = handler.guardrail_id_to_custom_guardrail["123"]
        assert original is not None
        assert original.logging_only_scope is None  # tolerated at load

        with pytest.raises(ValueError, match="logging_only_scope is set"):
            handler.sync_guardrail_from_db(guardrail=row, reject_invalid_logging_only_scope=True)

        # Rejected without touching the live instance.
        assert handler.guardrail_id_to_custom_guardrail["123"] is original
        assert _live_instances_named("mode-following") == 1
    finally:
        registry_module.guardrail_initializer_registry.pop("mode_following_test", None)
        for cb_list, snapshot in zip(lists, snapshots):
            cb_list[:] = snapshot


@pytest.fixture
def rotation_handler() -> Iterator[InMemoryGuardrailHandler]:
    registry_module = _register_mode_following_initializer("rotation_test")
    lists = _all_callback_lists()
    snapshots = [list(cb_list) for cb_list in lists]
    try:
        yield InMemoryGuardrailHandler()
    finally:
        registry_module.guardrail_initializer_registry.pop("rotation_test", None)
        for cb_list, snapshot in zip(lists, snapshots):
            cb_list[:] = snapshot


def _rotation_row(hangarllm_params: dict[str, object] | HangarllmParams) -> Guardrail:
    return Guardrail(guardrail_id="rotated", guardrail_name="mode-following", hangarllm_params=hangarllm_params)


_LOADED_PARAMS = {"guardrail": "rotation_test", "mode": "pre_call", "default_on": True, "api_key": "gk-loaded"}


def test_sync_guardrail_from_db_keeps_the_loaded_guardrail_when_db_params_do_not_decrypt(rotation_handler):
    rotation_handler.initialize_guardrail(guardrail=_rotation_row(dict(_LOADED_PARAMS)), source="db")
    live_instance = rotation_handler.guardrail_id_to_custom_guardrail["rotated"]

    rotation_handler.sync_guardrail_from_db(
        _rotation_row({**_LOADED_PARAMS, "api_key": "hangarllm_enc::sealed-under-the-new-key"})
    )

    assert rotation_handler.guardrail_id_to_custom_guardrail["rotated"] is live_instance
    assert rotation_handler.IN_MEMORY_GUARDRAILS["rotated"]["hangarllm_params"].api_key == "gk-loaded"


def test_sync_guardrail_from_db_applies_other_edits_and_keeps_the_loaded_value_that_does_not_decrypt(
    rotation_handler,
):
    rotation_handler.initialize_guardrail(guardrail=_rotation_row(dict(_LOADED_PARAMS)), source="db")

    rotation_handler.sync_guardrail_from_db(
        _rotation_row({**_LOADED_PARAMS, "mode": "post_call", "api_key": "hangarllm_enc::sealed-under-the-new-key"})
    )

    synced_params = rotation_handler.IN_MEMORY_GUARDRAILS["rotated"]["hangarllm_params"]
    assert synced_params.mode == "post_call"
    assert synced_params.api_key == "gk-loaded"
    live_instance = rotation_handler.guardrail_id_to_custom_guardrail["rotated"]
    assert live_instance.should_run_guardrail(data={}, event_type=GuardrailEventHooks.post_call) is True


def test_sync_guardrail_from_db_keeps_the_loaded_guardrail_when_an_undecryptable_param_has_no_loaded_value(
    rotation_handler,
):
    loaded_params = {key: value for key, value in _LOADED_PARAMS.items() if key != "api_key"}
    rotation_handler.initialize_guardrail(guardrail=_rotation_row(dict(loaded_params)), source="db")
    live_instance = rotation_handler.guardrail_id_to_custom_guardrail["rotated"]

    rotation_handler.sync_guardrail_from_db(
        _rotation_row({**loaded_params, "mode": "post_call", "api_key": "hangarllm_enc::sealed-under-the-new-key"})
    )

    assert rotation_handler.guardrail_id_to_custom_guardrail["rotated"] is live_instance
    synced_params = rotation_handler.IN_MEMORY_GUARDRAILS["rotated"]["hangarllm_params"]
    assert synced_params.mode == "pre_call"
    assert synced_params.api_key is None


def test_sync_guardrail_from_db_keeps_the_loaded_value_when_a_patch_passes_hangarllm_params_as_a_model(
    rotation_handler,
):
    rotation_handler.initialize_guardrail(guardrail=_rotation_row(dict(_LOADED_PARAMS)), source="db")

    rotation_handler.sync_guardrail_from_db(
        _rotation_row(HangarllmParams(**{**_LOADED_PARAMS, "default_on": False, "api_key": "hangarllm_enc::sealed"}))
    )

    synced_params = rotation_handler.IN_MEMORY_GUARDRAILS["rotated"]["hangarllm_params"]
    assert synced_params.default_on is False
    assert synced_params.api_key == "gk-loaded"


def test_sync_guardrail_from_db_applies_an_edit_to_a_guardrail_loaded_with_an_undecryptable_value(
    rotation_handler,
):
    stale_params = {**_LOADED_PARAMS, "api_key": "hangarllm_enc::stale"}
    rotation_handler.initialize_guardrail(guardrail=_rotation_row(dict(stale_params)), source="db")

    rotation_handler.sync_guardrail_from_db(_rotation_row({**stale_params, "mode": "post_call", "default_on": False}))

    synced_params = rotation_handler.IN_MEMORY_GUARDRAILS["rotated"]["hangarllm_params"]
    assert synced_params.mode == "post_call"
    assert synced_params.default_on is False
    assert synced_params.api_key == "hangarllm_enc::stale"


def _db_hangarllm_params() -> dict:
    """
    Shape produced by GuardrailRegistry.get_all_guardrails_from_db: hangarllm_params
    is a raw dict (not a HangarllmParams), holding only the keys originally stored,
    a non-schema extra key, and plain-string enum values.
    """
    return {
        "guardrail": "hangarllm_content_filter",
        "mode": "pre_call",
        "default_on": True,
        "version": 2,
        "blocked_words": [{"keyword": "secret", "action": "BLOCK"}],
    }


def test_unchanged_db_params_do_not_register_as_changed():
    """
    A DB poll returns hangarllm_params as a raw dict while the in-memory copy is a
    HangarllmParams whose model_dump() fills every field default and coerces enums.
    The two shapes must compare equal when the config is identical; otherwise
    every poll cycle re-initializes the guardrail indefinitely.
    """
    handler = InMemoryGuardrailHandler()
    raw = _db_hangarllm_params()
    gid = "11111111-1111-1111-1111-111111111111"
    handler.IN_MEMORY_GUARDRAILS[gid] = Guardrail(
        guardrail_id=gid,
        guardrail_name="cf",
        hangarllm_params=HangarllmParams(**raw),
    )

    new = Guardrail(guardrail_id=gid, guardrail_name="cf", hangarllm_params=dict(raw))
    assert handler._has_guardrail_params_changed(gid, new) is False


def test_db_poll_does_not_reinitialize_config_guardrail_without_default_on():
    handler = InMemoryGuardrailHandler()
    guardrail_id: Final = "config-default-on-guardrail"
    guardrail_name: Final = "config-default-on-guardrail"
    params: Final = {
        "guardrail": "hangarllm_content_filter",
        "mode": "pre_call",
        "logging_only_scope": "Input",
        "blocked_words": [{"keyword": "synthetic blocked phrase", "action": "BLOCK"}],
    }
    callback_lists: Final = _all_callback_lists()
    callback_snapshots: Final = [list(callback_list) for callback_list in callback_lists]

    try:
        existing: Final = handler.initialize_guardrail(
            guardrail=Guardrail(
                guardrail_id=guardrail_id,
                guardrail_name=guardrail_name,
                hangarllm_params=params,
            ),
            source="config",
        )
        assert existing is not None
        assert existing["hangarllm_params"].default_on is False
        assert existing["hangarllm_params"].logging_only_scope is None

        synced: Final = handler.sync_guardrail_from_db(
            Guardrail(
                guardrail_id=guardrail_id,
                guardrail_name=guardrail_name,
                hangarllm_params=params,
            )
        )

        assert synced is existing
        assert handler.IN_MEMORY_GUARDRAILS[guardrail_id] is existing
        assert handler._sources[guardrail_id] == "db"
    finally:
        handler.delete_in_memory_guardrail(guardrail_id)
        for callback_list, snapshot in zip(callback_lists, callback_snapshots):
            callback_list[:] = snapshot


def test_changed_db_params_register_as_changed():
    """Normalizing both sides must still surface a genuine config change."""
    handler = InMemoryGuardrailHandler()
    raw = _db_hangarllm_params()
    gid = "22222222-2222-2222-2222-222222222222"
    handler.IN_MEMORY_GUARDRAILS[gid] = Guardrail(
        guardrail_id=gid,
        guardrail_name="cf",
        hangarllm_params=HangarllmParams(**raw),
    )

    changed = {**raw, "blocked_words": [{"keyword": "different", "action": "BLOCK"}]}
    new = Guardrail(guardrail_id=gid, guardrail_name="cf", hangarllm_params=changed)
    assert handler._has_guardrail_params_changed(gid, new) is True


def test_unnormalizable_db_params_register_as_changed_without_raising():
    """
    A DB row whose hangarllm_params fail HangarllmParams validation must not crash the
    poll loop. The comparison falls back to treating the guardrail as changed so it
    re-initializes (and surfaces the bad row in logs) rather than propagating the
    validation error up through the polling cycle.
    """
    handler = InMemoryGuardrailHandler()
    raw = _db_hangarllm_params()
    gid = "55555555-5555-5555-5555-555555555555"
    handler.IN_MEMORY_GUARDRAILS[gid] = Guardrail(
        guardrail_id=gid,
        guardrail_name="cf",
        hangarllm_params=HangarllmParams(**raw),
    )

    malformed = {**raw, "default_on": "not-a-bool-xyz"}
    new = Guardrail(guardrail_id=gid, guardrail_name="cf", hangarllm_params=malformed)
    assert handler._has_guardrail_params_changed(gid, new) is True


def test_invalid_scope_literal_db_params_compare_equal_after_normalization():
    handler = InMemoryGuardrailHandler()
    raw = _db_hangarllm_params()
    gid = "77777777-7777-7777-7777-777777777777"
    handler.IN_MEMORY_GUARDRAILS[gid] = Guardrail(
        guardrail_id=gid,
        guardrail_name="cf",
        hangarllm_params=HangarllmParams(**{**raw, "logging_only_scope": None}),
    )
    new = Guardrail(
        guardrail_id=gid,
        guardrail_name="cf",
        hangarllm_params={**raw, "logging_only_scope": "Input"},
    )

    assert handler._has_guardrail_params_changed(gid, new) is False


def _all_callback_lists():
    import hangarllm

    return [
        hangarllm.callbacks,
        hangarllm.success_callback,
        hangarllm.failure_callback,
        hangarllm._async_success_callback,
        hangarllm._async_failure_callback,
    ]


def test_delete_in_memory_guardrail_removes_callback_from_all_lists():
    """
    Request handling promotes guardrail callbacks from hangarllm.callbacks into the
    success/failure/async lists. delete_in_memory_guardrail must purge the callback
    from every list, otherwise a re-initialized guardrail leaves its old instance
    stranded in those lists and instances accumulate.
    """
    handler = InMemoryGuardrailHandler()
    callback = CustomGuardrail(
        guardrail_name="cf-delete",
        default_on=True,
        event_hook=GuardrailEventHooks.pre_call,
    )
    gid = "33333333-3333-3333-3333-333333333333"
    handler.IN_MEMORY_GUARDRAILS[gid] = _make_guardrail(gid, "cf-delete")
    handler._sources[gid] = "db"
    handler.guardrail_id_to_custom_guardrail[gid] = callback

    lists = _all_callback_lists()
    snapshots = [list(cb_list) for cb_list in lists]
    try:
        for cb_list in lists:
            cb_list.append(callback)

        handler.delete_in_memory_guardrail(gid)

        for cb_list in lists:
            assert callback not in cb_list
    finally:
        for cb_list, snapshot in zip(lists, snapshots):
            cb_list[:] = snapshot


def test_repeated_db_sync_does_not_accumulate_runner_instances():
    """
    End-to-end regression for the OOM: across repeated DB polls (with the config
    genuinely changing each cycle to force re-initialization), exactly one live
    guardrail instance must exist across all callback lists. On the unfixed code
    the stale instance lingers in the success/failure lists and the distinct count
    climbs above one.
    """
    import hangarllm

    handler = InMemoryGuardrailHandler()
    gid = "44444444-4444-4444-4444-444444444444"
    name = "cf-accum"

    def db_guardrail(word: str) -> Guardrail:
        params = {
            **_db_hangarllm_params(),
            "blocked_words": [{"keyword": word, "action": "BLOCK"}],
        }
        return Guardrail(guardrail_id=gid, guardrail_name=name, hangarllm_params=params)

    def promote_into_request_lists() -> None:
        manager = hangarllm.logging_callback_manager
        for callback in list(hangarllm.callbacks):
            manager.add_hangarllm_success_callback(callback)
            manager.add_hangarllm_failure_callback(callback)
            manager.add_hangarllm_async_success_callback(callback)
            manager.add_hangarllm_async_failure_callback(callback)

    def distinct_runner_instances() -> int:
        seen = set()
        for callback in hangarllm.logging_callback_manager.get_all_callbacks():
            if isinstance(callback, CustomGuardrail) and getattr(callback, "guardrail_name", None) == name:
                seen.add(id(callback))
        return len(seen)

    lists = _all_callback_lists()
    snapshots = [list(cb_list) for cb_list in lists]
    try:
        for cycle in range(5):
            handler.sync_guardrail_from_db(db_guardrail(f"word-{cycle}"))
            promote_into_request_lists()

        assert distinct_runner_instances() == 1
    finally:
        for cb_list, snapshot in zip(lists, snapshots):
            cb_list[:] = snapshot


PRESIDIO_SIBLINGS_GID = "55555555-5555-5555-5555-555555555555"
PRESIDIO_SIBLINGS_NAME = "presidio-siblings"


def _presidio_db_guardrail(pii_entities_config: dict[str, str]) -> Guardrail:
    return Guardrail(
        guardrail_id=PRESIDIO_SIBLINGS_GID,
        guardrail_name=PRESIDIO_SIBLINGS_NAME,
        hangarllm_params={
            "guardrail": "presidio",
            "mode": "pre_call",
            "default_on": True,
            "output_parse_pii": True,
            "presidio_filter_scope": "both",
            "presidio_analyzer_api_base": "https://fakelink.com/v1/presidio/analyze",
            "presidio_anonymizer_api_base": "https://fakelink.com/v1/presidio/anonymize",
            "pii_entities_config": pii_entities_config,
        },
    )


def _presidio_callbacks_in(cb_list: Iterable[object]) -> list[CustomGuardrail]:
    return [
        callback
        for callback in cb_list
        if isinstance(callback, CustomGuardrail) and getattr(callback, "guardrail_name", None) == PRESIDIO_SIBLINGS_NAME
    ]


def test_presidio_siblings_are_tracked_and_deleted_together():
    """
    A presidio guardrail scoped to both stages registers the pre_call primary plus
    the post_call unmask and mask-output siblings. Deleting the guardrail must remove
    all three from every callback list, not just the primary.
    """
    import hangarllm

    handler = InMemoryGuardrailHandler()
    lists = _all_callback_lists()
    snapshots = [list(cb_list) for cb_list in lists]
    try:
        handler.initialize_guardrail(_presidio_db_guardrail({"EMAIL_ADDRESS": "MASK"}))

        registered = _presidio_callbacks_in(hangarllm.callbacks)
        assert len(registered) == 3
        primary = handler.guardrail_id_to_custom_guardrail[PRESIDIO_SIBLINGS_GID]
        siblings = handler.guardrail_id_to_sibling_callbacks[PRESIDIO_SIBLINGS_GID]
        assert primary is registered[0]
        assert siblings == tuple(registered[1:])
        assert not primary.should_run_guardrail({}, GuardrailEventHooks.post_call)
        assert all(sibling.should_run_guardrail({}, GuardrailEventHooks.post_call) for sibling in siblings)

        for cb_list in lists[1:]:
            cb_list.extend(registered)

        handler.delete_in_memory_guardrail(PRESIDIO_SIBLINGS_GID)

        for cb_list in lists:
            assert _presidio_callbacks_in(cb_list) == []
        assert PRESIDIO_SIBLINGS_GID not in handler.guardrail_id_to_custom_guardrail
        assert PRESIDIO_SIBLINGS_GID not in handler.guardrail_id_to_sibling_callbacks
    finally:
        for cb_list, snapshot in zip(lists, snapshots):
            cb_list[:] = snapshot


def test_update_in_memory_guardrail_rebuilds_presidio_siblings_and_keeps_their_stage():
    import hangarllm

    handler = InMemoryGuardrailHandler()
    lists = _all_callback_lists()
    snapshots = [list(cb_list) for cb_list in lists]
    try:
        handler.initialize_guardrail(_presidio_db_guardrail({"EMAIL_ADDRESS": "MASK", "IP_ADDRESS": "MASK"}))
        tracked = _presidio_callbacks_in(hangarllm.callbacks)
        roles_before = [
            (callback.apply_to_output, callback.output_parse_pii, callback.event_hook) for callback in tracked
        ]
        assert [
            callback for callback in tracked if callback.should_run_guardrail({}, GuardrailEventHooks.pre_call)
        ] == tracked[:1]
        assert [
            callback for callback in tracked if callback.should_run_guardrail({}, GuardrailEventHooks.post_call)
        ] == tracked[1:]

        updated = Guardrail(
            guardrail_id=PRESIDIO_SIBLINGS_GID,
            guardrail_name=PRESIDIO_SIBLINGS_NAME,
            hangarllm_params=HangarllmParams(
                guardrail="presidio",
                mode="pre_call",
                default_on=True,
                output_parse_pii=True,
                presidio_filter_scope="both",
                presidio_analyzer_api_base="https://fakelink.com/v1/presidio/analyze",
                presidio_anonymizer_api_base="https://fakelink.com/v1/presidio/anonymize",
                pii_entities_config={"EMAIL_ADDRESS": "MASK"},
            ),
        )
        handler.update_in_memory_guardrail(guardrail_id=PRESIDIO_SIBLINGS_GID, guardrail=updated)

        rebuilt = _presidio_callbacks_in(hangarllm.callbacks)
        assert len(rebuilt) == 3
        assert [callback.pii_entities_config for callback in rebuilt] == [{"EMAIL_ADDRESS": "MASK"}] * 3
        assert [
            (callback.apply_to_output, callback.output_parse_pii, callback.event_hook) for callback in rebuilt
        ] == roles_before
        assert not any(previous in rebuilt for previous in tracked)
        assert handler.guardrail_id_to_custom_guardrail[PRESIDIO_SIBLINGS_GID] is rebuilt[0]
        assert handler.guardrail_id_to_sibling_callbacks[PRESIDIO_SIBLINGS_GID] == tuple(rebuilt[1:])
    finally:
        for cb_list, snapshot in zip(lists, snapshots):
            cb_list[:] = snapshot


def test_repeated_db_sync_replaces_presidio_siblings_instead_of_leaking_stale_ones():
    """
    The callback manager dedupes custom loggers by their scalar attributes, so a
    leaked post_call sibling blocks the re-initialized sibling from registering and
    keeps serving the previous entity config. After every DB re-sync, each callback
    list must hold exactly the three current instances, all on the latest config.
    """
    import hangarllm

    handler = InMemoryGuardrailHandler()
    lists = _all_callback_lists()
    snapshots = [list(cb_list) for cb_list in lists]
    try:
        entity_configs = [{"EMAIL_ADDRESS": "MASK"}, {"EMAIL_ADDRESS": "MASK", "IP_ADDRESS": "MASK"}]
        for cycle in range(4):
            latest = entity_configs[cycle % 2]
            handler.sync_guardrail_from_db(_presidio_db_guardrail(latest))
            for cb_list in lists[1:]:
                cb_list.extend(_presidio_callbacks_in(hangarllm.callbacks))

            for cb_list in lists:
                current = _presidio_callbacks_in(cb_list)
                assert len({id(callback) for callback in current}) == 3
                assert all(callback.pii_entities_config == latest for callback in current)
    finally:
        for cb_list, snapshot in zip(lists, snapshots):
            cb_list[:] = snapshot


def _judge_guardrail(guardrail_id: str) -> Guardrail:
    return Guardrail(
        guardrail_id=guardrail_id,
        guardrail_name="quality-judge",
        hangarllm_params={
            "guardrail": "llm_as_a_judge",
            "mode": "post_call",
            "judge_model": "my-judge-alias",
            "overall_threshold": 80,
            "on_failure": "log",
            "criteria": [{"name": "helpfulness", "weight": 100, "description": "helpful?"}],
        },
    )


def test_db_synced_judge_guardrail_uses_lazy_router_provider():
    """A judge guardrail created/synced through a DB path must resolve the active
    Router lazily at call time (issue: UI-created guardrails failed open because the
    Router was captured at construction; a guardrail created before the Router
    existed captured None and never recovered). Asserting the default provider is
    wired guarantees the instance reads the live global rather than a stale value."""
    from hangarllm.proxy.guardrails.guardrail_hooks.llm_as_a_judge import (
        LLMAsAJudgeGuardrail,
        _default_router_provider,
    )

    handler = InMemoryGuardrailHandler()

    lists = _all_callback_lists()
    snapshots = [list(cb_list) for cb_list in lists]
    try:
        handler.sync_guardrail_from_db(_judge_guardrail("judge-db"))

        instance = handler.guardrail_id_to_custom_guardrail["judge-db"]
        assert isinstance(instance, LLMAsAJudgeGuardrail)
        assert instance._router_provider is _default_router_provider
    finally:
        for cb_list, snapshot in zip(lists, snapshots):
            cb_list[:] = snapshot


def test_reinitialized_judge_guardrail_uses_lazy_router_provider():
    from hangarllm.proxy.guardrails.guardrail_hooks.llm_as_a_judge import (
        LLMAsAJudgeGuardrail,
        _default_router_provider,
    )

    handler = InMemoryGuardrailHandler()

    lists = _all_callback_lists()
    snapshots = [list(cb_list) for cb_list in lists]
    try:
        handler.reinitialize_guardrail(_judge_guardrail("judge-reinit"), source="db")

        instance = handler.guardrail_id_to_custom_guardrail["judge-reinit"]
        assert isinstance(instance, LLMAsAJudgeGuardrail)
        assert instance._router_provider is _default_router_provider
    finally:
        for cb_list, snapshot in zip(lists, snapshots):
            cb_list[:] = snapshot


def _lakera_guardrail(guardrail_id: str, **hangarllm_params_overrides) -> Guardrail:
    params = {"guardrail": "lakera_v2", "mode": "pre_call", "on_flagged": "block", **hangarllm_params_overrides}
    return Guardrail(
        guardrail_id=guardrail_id,
        guardrail_name="lakera-test",
        hangarllm_params=HangarllmParams(**params),
    )


class TestReinitializeGuardrailRestoresOnFailure:
    """Maintainer finding on valteresj2/HangarLLM#34940: reinitialize_guardrail deletes
    the old in-memory instance and its callback registration before attempting to
    construct the new one. initialize_guardrail's own ValueError/TypeError
    propagate uncaught, so a rejected hot-reload (e.g. PATCH /guardrails/{id}
    with an invalid on_flagged combination) previously left the guardrail
    deleted entirely, not merely "still enforcing the old config", while the
    DB/API kept reporting the new config as live."""

    def test_invalid_update_restores_previous_instance(self):
        handler = InMemoryGuardrailHandler()
        lists = _all_callback_lists()
        snapshots = [list(cb_list) for cb_list in lists]
        try:
            handler.reinitialize_guardrail(_lakera_guardrail("lakera-restore", on_flagged="block"), source="db")

            with pytest.raises(ValueError, match="requires payload=True and breakdown=True"):
                handler.reinitialize_guardrail(
                    _lakera_guardrail("lakera-restore", on_flagged="inject_system_message", payload=False),
                    source="db",
                )

            assert "lakera-restore" in handler.IN_MEMORY_GUARDRAILS, "a rejected update must not delete the guardrail"
            restored_instance = handler.guardrail_id_to_custom_guardrail["lakera-restore"]
            assert restored_instance.on_flagged == "block"
        finally:
            for cb_list, snapshot in zip(lists, snapshots):
                cb_list[:] = snapshot

    def test_invalid_update_leaves_dict_metadata_matching_the_restored_instance(self):
        """IN_MEMORY_GUARDRAILS's own dict entry (what /guardrails/list-style
        reads would see) must reflect the restored config too, not the
        rejected one -- otherwise admin-facing reads and the live callback
        instance disagree about what's actually configured."""
        handler = InMemoryGuardrailHandler()
        lists = _all_callback_lists()
        snapshots = [list(cb_list) for cb_list in lists]
        try:
            handler.reinitialize_guardrail(_lakera_guardrail("lakera-restore-meta", on_flagged="block"), source="db")

            with pytest.raises(ValueError, match="requires payload=True and breakdown=True"):
                handler.reinitialize_guardrail(
                    _lakera_guardrail("lakera-restore-meta", on_flagged="inject_system_message", breakdown=False),
                    source="db",
                )

            assert handler.IN_MEMORY_GUARDRAILS["lakera-restore-meta"]["hangarllm_params"].on_flagged == "block"
        finally:
            for cb_list, snapshot in zip(lists, snapshots):
                cb_list[:] = snapshot


class TestScanOnlyToolResultsInitRefusal:
    """A guardrail whose role filtering never scans tool results must be rejected at
    initialization when configured with scan_only_tool_results, instead of booting a
    proxy that silently scans nothing on every request."""

    def _initialize(self, name: str, params: dict):
        lists = _all_callback_lists()
        snapshots = [list(cb_list) for cb_list in lists]
        try:
            return InMemoryGuardrailHandler().initialize_guardrail(
                guardrail={"guardrail_name": name, "hangarllm_params": params},
            )
        finally:
            for cb_list, snapshot in zip(lists, snapshots):
                cb_list[:] = snapshot

    def test_panw_prisma_airs_with_scan_only_tool_results_is_rejected(self):
        with pytest.raises(ValueError, match="never scans tool results"):
            self._initialize(
                "panw-scan-only-combo",
                {
                    "guardrail": "panw_prisma_airs",
                    "mode": "pre_call",
                    "api_key": "test-key",
                    "profile_name": "test-profile",
                    "scan_only_tool_results": True,
                },
            )

    def test_bedrock_latest_role_with_scan_only_tool_results_is_rejected(self):
        with pytest.raises(ValueError, match="never scans tool results"):
            self._initialize(
                "bedrock-latest-role-scan-only-combo",
                {
                    "guardrail": "bedrock",
                    "mode": "pre_call",
                    "guardrailIdentifier": "gr-1",
                    "guardrailVersion": "1",
                    "experimental_use_latest_role_message_only": True,
                    "scan_only_tool_results": True,
                },
            )

    def test_bedrock_without_latest_role_accepts_scan_only_tool_results(self):
        result = self._initialize(
            "bedrock-scan-only-ok",
            {
                "guardrail": "bedrock",
                "mode": "pre_call",
                "guardrailIdentifier": "gr-1",
                "guardrailVersion": "1",
                "scan_only_tool_results": True,
            },
        )
        assert result is not None

    def test_prompt_security_default_tool_filtering_rejects_scan_only_tool_results(self, monkeypatch):
        monkeypatch.delenv("PROMPT_SECURITY_CHECK_TOOL_RESULTS", raising=False)
        with pytest.raises(ValueError, match="never scans tool results"):
            self._initialize(
                "prompt-security-scan-only-combo",
                {
                    "guardrail": "prompt_security",
                    "mode": "pre_call",
                    "api_key": "test-key",
                    "api_base": "https://ps.example.com",
                    "scan_only_tool_results": True,
                },
            )

    def test_prompt_security_check_tool_results_accepts_scan_only_tool_results(self, monkeypatch):
        monkeypatch.setenv("PROMPT_SECURITY_CHECK_TOOL_RESULTS", "true")
        result = self._initialize(
            "prompt-security-scan-only-ok",
            {
                "guardrail": "prompt_security",
                "mode": "pre_call",
                "api_key": "test-key",
                "api_base": "https://ps.example.com",
                "scan_only_tool_results": True,
            },
        )
        assert result is not None

    def test_skip_tool_message_with_scan_only_tool_results_is_rejected(self):
        with pytest.raises(ValueError, match="skip_tool_message_in_guardrail are enabled together"):
            self._initialize(
                "bedrock-skip-tool-scan-only-combo",
                {
                    "guardrail": "bedrock",
                    "mode": "pre_call",
                    "guardrailIdentifier": "gr-1",
                    "guardrailVersion": "1",
                    "skip_tool_message_in_guardrail": True,
                    "scan_only_tool_results": True,
                },
            )


class _LoggingOnlyScopeSupportedGuardrail(CustomGuardrail):
    async def apply_guardrail(
        self,
        inputs: GenericGuardrailAPIInputs,
        request_data: dict[str, object],
        input_type: str,
        logging_obj: object | None = None,
    ) -> GenericGuardrailAPIInputs:
        return inputs


class _LoggingOnlyScopeUnsupportedGuardrail(_LoggingOnlyScopeSupportedGuardrail):
    async def async_logging_hook(
        self,
        kwargs: dict[str, object],
        result: object,
        call_type: str,
    ) -> tuple[dict[str, object], object]:
        return kwargs, result


class _LoggingOnlyScopeNativeGuardrail(_LoggingOnlyScopeSupportedGuardrail):
    use_native_lifecycle_hooks: ClassVar[bool] = True


def _invalid_scope_content_filter_guardrail() -> Guardrail:
    return Guardrail(
        guardrail_id="invalid-scope-content-filter-test",
        guardrail_name="invalid-scope-content-filter",
        hangarllm_params={
            "guardrail": "hangarllm_content_filter",
            "mode": "pre_call",
            "logging_only_scope": "Input",
            "blocked_words": [{"keyword": "pineapple", "action": "BLOCK"}],
        },
    )


class TestLoggingOnlyScopeValidation:
    @pytest.mark.parametrize(
        ("scope", "expected_scope"),
        (("input", "input"), ("Input", None)),
    )
    def test_tolerant_parser_preserves_default_on_constructor_coercion(
        self, scope: str, expected_scope: str | None
    ) -> None:
        params: Final = {
            "guardrail": "hangarllm_content_filter",
            "mode": "pre_call",
            "logging_only_scope": scope,
            "blocked_words": [{"keyword": "synthetic blocked phrase", "action": "BLOCK"}],
        }

        parsed: Final = parse_tolerant_hangarllm_params(params, "test-content-filter")
        expected: Final = HangarllmParams(**{**params, "logging_only_scope": expected_scope}).model_dump()

        assert parsed.default_on is False
        assert parsed.model_dump() == expected

    def _initialize(
        self,
        mode: str | list[str] | Mode,
        scope: LoggingOnlyScope | None,
        callback_type: type[CustomGuardrail] = _LoggingOnlyScopeSupportedGuardrail,
        reject_invalid_logging_only_scope: bool = False,
        assert_registered: bool = False,
        continue_on_input_failure: bool | None = None,
    ) -> CustomGuardrail:
        import hangarllm
        from hangarllm.proxy.guardrails import guardrail_registry as registry_module

        guardrail_type: Final = "logging_only_scope_test"
        created_callbacks: Final[list[CustomGuardrail]] = []

        def _initializer(hangarllm_params: HangarllmParams, guardrail: Guardrail) -> CustomGuardrail:
            supported_event_hooks: Final = (
                [GuardrailEventHooks.logging_only] if callback_type.use_native_lifecycle_hooks else None
            )
            callback: Final = callback_type(
                guardrail_name=guardrail["guardrail_name"],
                event_hook=hangarllm_params.mode,
                default_on=True,
                supported_event_hooks=supported_event_hooks,
            )
            hangarllm.logging_callback_manager.add_hangarllm_callback(callback)
            created_callbacks.append(callback)
            return callback

        registry_module.guardrail_initializer_registry[guardrail_type] = _initializer
        lists: Final = _all_callback_lists()
        snapshots: Final = [list(callback_list) for callback_list in lists]
        try:
            handler: Final = InMemoryGuardrailHandler()
            result: Final = handler.initialize_guardrail(
                guardrail={
                    "guardrail_name": "logging-only-scope-guardrail",
                    "hangarllm_params": {
                        "guardrail": guardrail_type,
                        "mode": mode,
                        "logging_only_scope": scope,
                        "logging_only_continue_on_input_failure": continue_on_input_failure,
                    },
                },
                reject_invalid_logging_only_scope=reject_invalid_logging_only_scope,
            )
            assert result is not None
            callback: Final = handler.guardrail_id_to_custom_guardrail[result["guardrail_id"]]
            assert callback is not None
            if assert_registered:
                assert callback in lists[0]
            return callback
        except ValueError:
            callback: Final = created_callbacks[0]
            assert all(callback not in callback_list for callback_list in lists)
            raise
        finally:
            for callback_list, snapshot in zip(lists, snapshots):
                callback_list[:] = snapshot
            registry_module.guardrail_initializer_registry.pop(guardrail_type, None)

    def test_scope_without_logging_only_mode_is_ignored_at_load(self) -> None:
        callback: Final = self._initialize(mode="pre_call", scope="input", assert_registered=True)

        assert callback.logging_only_scope is None
        assert callback.should_run_guardrail(data={}, event_type=GuardrailEventHooks.pre_call) is True

    def test_scope_without_logging_only_mode_is_rejected_for_api_writes(self) -> None:
        with pytest.raises(ValueError, match="logging_only_scope is set") as exc_info:
            self._initialize(mode="pre_call", scope="input", reject_invalid_logging_only_scope=True)

        assert str(exc_info.value) == (
            "Guardrail logging-only-scope-guardrail: logging_only_scope is set, but mode does not include "
            "logging_only, so it would never apply. Add logging_only to mode or remove logging_only_scope."
        )

    @pytest.mark.parametrize(
        "mode",
        (
            "logging_only",
            ["pre_call", "logging_only"],
            Mode(tags={"audit": "logging_only"}, default="pre_call"),
        ),
    )
    def test_scope_accepts_logging_only_in_supported_mode_forms(self, mode: str | list[str] | Mode) -> None:
        callback: Final = self._initialize(mode=mode, scope="input")

        assert callback.logging_only_scope == "input"

    def test_directional_scope_is_ignored_at_load_when_guardrail_owns_logging_hook(self) -> None:
        callback: Final = self._initialize(
            mode="logging_only",
            scope="input",
            callback_type=_LoggingOnlyScopeUnsupportedGuardrail,
            assert_registered=True,
        )

        assert callback.logging_only_scope is None

    def test_directional_scope_rejected_for_api_writes_when_guardrail_owns_logging_hook(self) -> None:
        with pytest.raises(ValueError, match="logging_only_scope='input' is not supported") as exc_info:
            self._initialize(
                mode="logging_only",
                scope="input",
                callback_type=_LoggingOnlyScopeUnsupportedGuardrail,
                reject_invalid_logging_only_scope=True,
            )

        assert str(exc_info.value) == (
            "Guardrail logging-only-scope-guardrail: logging_only_scope='input' is not supported by this "
            "guardrail, whose logging_only hook scans on its own. Remove logging_only_scope."
        )

    def test_continue_flag_accepted_when_guardrail_owns_logging_hook(self) -> None:
        callback: Final = self._initialize(
            mode="logging_only",
            scope=None,
            continue_on_input_failure=True,
            callback_type=_LoggingOnlyScopeUnsupportedGuardrail,
        )

        assert callback.logging_only_scope is None
        assert callback.logging_only_continue_on_input_failure is True

    def test_output_scope_accepted_for_native_lifecycle_guardrail(self) -> None:
        callback: Final = self._initialize(
            mode="logging_only",
            scope="output",
            callback_type=_LoggingOnlyScopeNativeGuardrail,
        )

        assert callback.logging_only_scope == "output"

    @pytest.mark.parametrize("scope", ("request", "both"))
    def test_invalid_scope_fails_hangarllm_params_validation(self, scope: str) -> None:
        with pytest.raises(ValidationError):
            HangarllmParams(guardrail="test", mode="logging_only", logging_only_scope=scope)

    def test_invalid_scope_literal_keeps_content_filter_registered_and_blocking(self) -> None:
        import hangarllm
        from hangarllm.proxy.guardrails.guardrail_hooks.hangarllm_content_filter.content_filter import (
            ContentFilterGuardrail,
        )

        handler: Final = InMemoryGuardrailHandler()
        callback_lists: Final = _all_callback_lists()
        callback_snapshots: Final = [list(callback_list) for callback_list in callback_lists]
        guardrail: Final = _invalid_scope_content_filter_guardrail()

        try:
            result: Final = handler.initialize_guardrail(guardrail=guardrail, source="config")
            assert result is not None
            callback: Final = handler.guardrail_id_to_custom_guardrail[result["guardrail_id"]]
            assert isinstance(callback, ContentFilterGuardrail)
            assert callback in hangarllm.callbacks
            assert callback.logging_only_scope is None
            assert callback.event_hook == GuardrailEventHooks.pre_call
            assert callback._check_blocked_words("pineapple") is not None
        finally:
            handler.delete_in_memory_guardrail(guardrail["guardrail_id"])
            for callback_list, snapshot in zip(callback_lists, callback_snapshots):
                callback_list[:] = snapshot

    def test_invalid_scope_literal_is_rejected_for_strict_initialization_without_callback_leakage(self) -> None:
        handler: Final = InMemoryGuardrailHandler()
        callback_lists: Final = _all_callback_lists()
        callback_snapshots: Final = [list(callback_list) for callback_list in callback_lists]

        with pytest.raises(ValueError, match="logging_only_scope"):
            handler.initialize_guardrail(
                guardrail=_invalid_scope_content_filter_guardrail(),
                source="config",
                reject_invalid_logging_only_scope=True,
            )

        assert all(callback_list == snapshot for callback_list, snapshot in zip(callback_lists, callback_snapshots))

    @pytest.mark.parametrize(
        ("scope", "continue_on_input_failure", "expected_direction", "expected_continue"),
        (
            (None, None, None, False),
            (None, True, None, True),
            (None, False, None, False),
            ("input", True, "input", False),
            ("output", True, "output", False),
            ("input", None, "input", False),
        ),
    )
    def test_logging_only_settings_table(
        self,
        scope: LoggingOnlyScope | None,
        continue_on_input_failure: bool | None,
        expected_direction: str | None,
        expected_continue: bool,
    ) -> None:
        callback: Final = self._initialize(
            mode="logging_only",
            scope=scope,
            continue_on_input_failure=continue_on_input_failure,
        )

        assert callback.logging_only_scope == expected_direction
        assert callback.logging_only_continue_on_input_failure is expected_continue

    def test_continue_flag_without_logging_only_mode_is_ignored_at_load(self) -> None:
        callback: Final = self._initialize(
            mode="pre_call", continue_on_input_failure=True, scope=None, assert_registered=True
        )

        assert callback.logging_only_scope is None
        assert callback.logging_only_continue_on_input_failure is False
        assert callback.should_run_guardrail(data={}, event_type=GuardrailEventHooks.pre_call) is True

    def test_continue_flag_without_logging_only_mode_is_rejected_for_api_writes(self) -> None:
        with pytest.raises(ValueError, match="logging_only_continue_on_input_failure is set") as exc_info:
            self._initialize(
                mode="pre_call",
                scope=None,
                continue_on_input_failure=True,
                reject_invalid_logging_only_scope=True,
            )

        assert str(exc_info.value) == (
            "Guardrail logging-only-scope-guardrail: logging_only_continue_on_input_failure is set, but mode "
            "does not include logging_only, so it would never apply. Add logging_only to mode or remove "
            "logging_only_continue_on_input_failure."
        )

    def test_continue_flag_is_accepted_when_guardrail_owns_logging_hook(self) -> None:
        callback: Final = self._initialize(
            mode="logging_only",
            scope=None,
            continue_on_input_failure=True,
            callback_type=_LoggingOnlyScopeUnsupportedGuardrail,
        )

        assert callback.logging_only_scope is None
        assert callback.logging_only_continue_on_input_failure is True

    def test_invalid_continue_flag_is_tolerated_by_parse_tolerant(self) -> None:
        params: Final = {
            "guardrail": "hangarllm_content_filter",
            "mode": "logging_only",
            "logging_only_continue_on_input_failure": "banana",
        }

        parsed: Final = parse_tolerant_hangarllm_params(params, "invalid-flag-test")

        assert parsed.logging_only_continue_on_input_failure is None

    def test_invalid_continue_flag_raises_without_tolerance(self) -> None:
        with pytest.raises(ValidationError):
            HangarllmParams(
                guardrail="test", mode="logging_only", logging_only_continue_on_input_failure="banana"
            )

    def test_invalid_scope_literal_does_not_tolerate_other_hangarllm_params_errors(self) -> None:
        with pytest.raises(ValidationError):
            parse_tolerant_hangarllm_params(
                {
                    "guardrail": "hangarllm_content_filter",
                    "mode": "pre_call",
                    "logging_only_scope": "Input",
                    "default_on": "not-a-bool",
                },
                "invalid-scope-content-filter",
            )


@pytest.mark.asyncio
async def test_update_guardrail_in_db_raises_when_row_missing():
    prisma_client = MagicMock()
    prisma_client.db.hangarllm_guardrailstable.update = AsyncMock(return_value=None)

    with pytest.raises(
        Exception,
        match=r"^Error updating guardrail in DB: Guardrail not found, passed guardrail_id=missing-guardrail$",
    ):
        await GuardrailRegistry().update_guardrail_in_db(
            guardrail_id="missing-guardrail",
            guardrail=Guardrail(
                guardrail_name="missing-guardrail",
                hangarllm_params=HangarllmParams(guardrail="bedrock", mode="pre_call"),
            ),
            prisma_client=prisma_client,
        )


@pytest.mark.asyncio
async def test_update_guardrail_in_db_persists_raw_sparse_params_verbatim():
    """
    After a rejected PATCH, the endpoint rolls back by writing the stored row's
    raw hangarllm_params through update_guardrail_in_db. A raw dict must be
    persisted exactly as stored — a legacy 4-key row stays a 4-key row — instead
    of being round-tripped through HangarllmParams.model_dump(), which materializes
    every field default and rewrites a row the admin never wrote.
    """
    prisma_client = MagicMock()
    prisma_client.db.hangarllm_guardrailstable.update = AsyncMock(
        return_value={"guardrail_id": "legacy-row", "guardrail_name": "legacy-one"}
    )
    legacy_params: Final = {
        "guardrail": "hangarllm_content_filter",
        "mode": "pre_call",
        "guardrail_name": "legacy-one",
        "blocked_words": [{"keyword": "x", "action": "BLOCK"}],
    }

    await GuardrailRegistry().update_guardrail_in_db(
        guardrail_id="legacy-row",
        guardrail=Guardrail(
            guardrail_id="legacy-row",
            guardrail_name="legacy-one",
            hangarllm_params=legacy_params,
            guardrail_info={},
        ),
        prisma_client=prisma_client,
    )

    persisted: Final = prisma_client.db.hangarllm_guardrailstable.update.call_args.kwargs["data"]
    assert json.loads(persisted["hangarllm_params"]) == legacy_params


def test_reinitialize_guardrail_restores_previous_on_failure():
    """A reinitialization whose new params make the guardrail constructor raise must
    restore the previous instance instead of leaving the guardrail silently removed:
    an enforcing guardrail must never fail open because an update was bad."""
    from hangarllm.proxy.guardrails import guardrail_registry as registry_module

    def _initializer(hangarllm_params, guardrail):
        if hangarllm_params.api_key == "boom":
            raise ValueError("invalid updated params")
        return CustomGuardrail(
            guardrail_name=guardrail["guardrail_name"],
            event_hook=GuardrailEventHooks.pre_call,
            default_on=True,
        )

    registry_module.guardrail_initializer_registry["restore_test"] = _initializer
    try:
        handler = InMemoryGuardrailHandler()
        created = handler.initialize_guardrail(
            guardrail={
                "guardrail_name": "restore-me",
                "hangarllm_params": {"guardrail": "restore_test", "mode": "pre_call", "api_key": "ok"},
            },
        )
        guardrail_id = created["guardrail_id"]
        original_instance = handler.guardrail_id_to_custom_guardrail[guardrail_id]

        with pytest.raises(ValueError, match="invalid updated params"):
            handler.reinitialize_guardrail(
                guardrail={
                    "guardrail_id": guardrail_id,
                    "guardrail_name": "restore-me",
                    "hangarllm_params": {"guardrail": "restore_test", "mode": "pre_call", "api_key": "boom"},
                },
            )

        assert guardrail_id in handler.IN_MEMORY_GUARDRAILS
        restored = handler.guardrail_id_to_custom_guardrail[guardrail_id]
        assert restored is not None and restored is not original_instance
        assert restored.guardrail_name == "restore-me"
    finally:
        registry_module.guardrail_initializer_registry.pop("restore_test", None)


def test_reinitialize_guardrail_raises_value_error_for_non_value_error_init_failures():
    """Regression for the LIT-6479 fix's 422 path: a constructor failure that is not
    already a ValueError/TypeError (re.error from an invalid regex has neither in its
    MRO) must still surface as ValueError, so the PUT/PATCH endpoints' rollback+422
    catch is exhaustive instead of warn-and-200 persisting a broken config."""
    import re

    from hangarllm.proxy.guardrails import guardrail_registry as registry_module

    def _initializer(hangarllm_params, guardrail):
        if hangarllm_params.api_key == "bad-regex":
            re.compile("([")
        return CustomGuardrail(
            guardrail_name=guardrail["guardrail_name"],
            event_hook=GuardrailEventHooks.pre_call,
            default_on=True,
        )

    registry_module.guardrail_initializer_registry["regex_test"] = _initializer
    try:
        handler = InMemoryGuardrailHandler()
        created = handler.initialize_guardrail(
            guardrail={
                "guardrail_name": "regex-me",
                "hangarllm_params": {"guardrail": "regex_test", "mode": "pre_call", "api_key": "ok"},
            },
        )
        guardrail_id = created["guardrail_id"]

        with pytest.raises(ValueError, match="Guardrail initialization failed") as excinfo:
            handler.reinitialize_guardrail(
                guardrail={
                    "guardrail_id": guardrail_id,
                    "guardrail_name": "regex-me",
                    "hangarllm_params": {"guardrail": "regex_test", "mode": "pre_call", "api_key": "bad-regex"},
                },
            )

        assert isinstance(excinfo.value.__cause__, re.error)
        assert guardrail_id in handler.IN_MEMORY_GUARDRAILS
        restored = handler.guardrail_id_to_custom_guardrail[guardrail_id]
        assert restored is not None and restored.guardrail_name == "regex-me"
    finally:
        registry_module.guardrail_initializer_registry.pop("regex_test", None)


def test_sync_guardrail_from_db_applies_db_dict_params_to_live_instance():
    """
    Regression for PUT /guardrails/{id}: the DB row arrives with hangarllm_params as
    a plain jsonb dict, and the in-place update_in_memory_guardrail cast it to
    HangarllmParams without constructing one, so vars() raised and the running proxy
    kept enforcing the stale config forever. The PUT endpoint now routes through
    sync_guardrail_from_db, which must rebuild the live instance from the dict:
    new blocked words compiled in, old ones gone, and the event hook re-derived
    from mode (the base-class setattr path wrote self.mode while dispatch reads
    self.event_hook, so only a full re-init applies a mode change).
    """
    from hangarllm.proxy.guardrails.guardrail_hooks.hangarllm_content_filter.content_filter import (
        ContentFilterGuardrail,
    )

    handler = InMemoryGuardrailHandler()
    gid = "66666666-6666-6666-6666-666666666666"

    def db_guardrail(word: str, mode: str) -> Guardrail:
        return Guardrail(
            guardrail_id=gid,
            guardrail_name="cf-put-sync",
            hangarllm_params={
                "guardrail": "hangarllm_content_filter",
                "mode": mode,
                "default_on": True,
                "blocked_words": [{"keyword": word, "action": "BLOCK"}],
            },
        )

    lists = _all_callback_lists()
    snapshots = [list(cb_list) for cb_list in lists]
    try:
        handler.sync_guardrail_from_db(db_guardrail("foobarblock", "pre_call"))
        handler.sync_guardrail_from_db(db_guardrail("quxnewblock", "during_call"))

        instance = handler.guardrail_id_to_custom_guardrail[gid]
        assert isinstance(instance, ContentFilterGuardrail)
        assert instance._check_blocked_words("hello QUXNEWBLOCK") is not None
        assert instance._check_blocked_words("hello FOOBARBLOCK") is None
        assert instance.event_hook == GuardrailEventHooks.during_call
        assert instance.should_run_guardrail(data={}, event_type=GuardrailEventHooks.during_call) is True
    finally:
        for cb_list, snapshot in zip(lists, snapshots):
            cb_list[:] = snapshot


def test_configure_callback_scoping_copies_stream_scope_when_constructor_omits_it():
    from hangarllm.proxy.guardrails.guardrail_registry import _configure_callback_scoping

    class _CtorWithoutStreamScope(CustomGuardrail):
        def __init__(self) -> None:
            super().__init__(
                guardrail_name="scoped",
                event_hook=GuardrailEventHooks.post_call,
                default_on=True,
            )

    instance = _CtorWithoutStreamScope()
    params = HangarllmParams(guardrail="bedrock", mode="post_call", stream_scope="streaming")
    _configure_callback_scoping(instance, "scoped", params)

    assert instance.stream_scope_default == "streaming"
    assert instance.should_run_guardrail({"stream": True}, GuardrailEventHooks.post_call) is True
    assert instance.should_run_guardrail({"stream": False}, GuardrailEventHooks.post_call) is False


def test_configure_callback_scoping_tolerates_a_custom_logger_callback():
    from hangarllm.integrations.custom_logger import CustomLogger
    from hangarllm.proxy.guardrails.guardrail_registry import _configure_callback_scoping

    callback: Final = CustomLogger()
    _configure_callback_scoping(callback, "logger-backed", HangarllmParams(guardrail="custom", mode="pre_call"))  # pyright: ignore[reportArgumentType]  # module-path guardrails may be plain CustomLogger
    assert "stream_scope_by_hook" not in vars(callback)


_ENCRYPTED_PREFIX = "hangarllm_enc::"


class _Row(dict[str, object]):
    def __getattr__(self, name: str) -> object:
        return self[name]


def _stored_params(create_or_update_mock: AsyncMock) -> dict[str, object]:
    import json

    return json.loads(create_or_update_mock.call_args.kwargs["data"]["hangarllm_params"])


@pytest.mark.asyncio
async def test_add_guardrail_to_db_encrypts_sensitive_params_at_rest(monkeypatch):
    monkeypatch.setenv("HANGARLLM_SALT_KEY", "sk-salt-guardrail-test")
    prisma_client = MagicMock()
    prisma_client.db.hangarllm_guardrailstable.create = AsyncMock(return_value=_Row(guardrail_id="g-1"))

    await GuardrailRegistry().add_guardrail_to_db(
        guardrail=Guardrail(
            guardrail_name="vendor",
            hangarllm_params=HangarllmParams(
                guardrail="generic_guardrail_api",
                mode="pre_call",
                api_key="vendor-secret-key",
                api_base="http://vendor.example",
                aws_secret_access_key="aws-secret",
                custom_headers={"Authorization": "Bearer header-secret", "x-tenant": "t1"},
            ),
        ),
        prisma_client=prisma_client,
    )

    stored = _stored_params(prisma_client.db.hangarllm_guardrailstable.create)
    for leaked in ("vendor-secret-key", "aws-secret", "header-secret"):
        assert leaked not in str(stored)
    assert stored["api_key"].startswith(_ENCRYPTED_PREFIX)
    assert stored["aws_secret_access_key"].startswith(_ENCRYPTED_PREFIX)
    assert stored["custom_headers"]["Authorization"].startswith(_ENCRYPTED_PREFIX)
    assert stored["custom_headers"]["x-tenant"] == "t1"
    assert stored["guardrail"] == "generic_guardrail_api"
    assert stored["mode"] == "pre_call"
    assert stored["api_base"] == "http://vendor.example"


@pytest.mark.asyncio
async def test_get_all_guardrails_from_db_decrypts_new_rows_and_reads_legacy_plaintext(monkeypatch):
    from hangarllm.proxy.guardrails.guardrail_registry import encrypt_guardrail_hangarllm_params

    monkeypatch.setenv("HANGARLLM_SALT_KEY", "sk-salt-guardrail-test")
    encrypted_row = _Row(
        guardrail_id="g-new",
        guardrail_name="new",
        hangarllm_params=encrypt_guardrail_hangarllm_params(
            {"guardrail": "generic_guardrail_api", "mode": "pre_call", "api_key": "new-key"}
        ),
    )
    legacy_row = _Row(
        guardrail_id="g-legacy",
        guardrail_name="legacy",
        hangarllm_params={"guardrail": "generic_guardrail_api", "mode": "pre_call", "api_key": "legacy-key"},
    )
    prisma_client = MagicMock()
    prisma_client.db.hangarllm_guardrailstable.find_many = AsyncMock(return_value=[encrypted_row, legacy_row])

    guardrails = await GuardrailRegistry.get_all_guardrails_from_db(prisma_client=prisma_client)

    assert [g["hangarllm_params"]["api_key"] for g in guardrails] == ["new-key", "legacy-key"]


@pytest.mark.asyncio
async def test_update_guardrail_in_db_encrypts_and_returns_decrypted_row(monkeypatch):
    monkeypatch.setenv("HANGARLLM_SALT_KEY", "sk-salt-guardrail-test")
    prisma_client = MagicMock()

    async def _update(where, data):
        import json

        return _Row(
            guardrail_id=where["guardrail_id"],
            guardrail_name="vendor",
            hangarllm_params=json.loads(data["hangarllm_params"]),
        )

    prisma_client.db.hangarllm_guardrailstable.update = AsyncMock(side_effect=_update)

    result = await GuardrailRegistry().update_guardrail_in_db(
        guardrail_id="g-1",
        guardrail=Guardrail(
            guardrail_name="vendor",
            hangarllm_params={"guardrail": "generic_guardrail_api", "mode": "pre_call", "api_key": "rotated-key"},
        ),
        prisma_client=prisma_client,
    )

    assert _stored_params(prisma_client.db.hangarllm_guardrailstable.update)["api_key"].startswith(_ENCRYPTED_PREFIX)
    assert result["hangarllm_params"]["api_key"] == "rotated-key"


def test_encrypt_guardrail_hangarllm_params_does_not_double_encrypt(monkeypatch):
    from hangarllm.proxy.guardrails.guardrail_registry import (
        decrypt_guardrail_hangarllm_params,
        encrypt_guardrail_hangarllm_params,
    )

    monkeypatch.setenv("HANGARLLM_SALT_KEY", "sk-salt-guardrail-test")
    params = {
        "api_key": "k",
        "default_on": True,
        "auth_token": None,
        "extra_headers": [{"x-api-key": "list-secret", "x-tenant": "t1"}],
    }
    encrypted = encrypt_guardrail_hangarllm_params(params)

    assert encrypted["extra_headers"][0]["x-api-key"].startswith(_ENCRYPTED_PREFIX)
    assert encrypted["extra_headers"][0]["x-tenant"] == "t1"
    assert encrypt_guardrail_hangarllm_params(encrypted) == encrypted
    assert decrypt_guardrail_hangarllm_params(encrypted) == params


@pytest.mark.asyncio
async def test_rotate_guardrail_params_master_key_reencrypts_under_the_new_key(monkeypatch):
    from hangarllm.proxy.guardrails.guardrail_registry import (
        decrypt_guardrail_hangarllm_params,
        encrypt_guardrail_hangarllm_params,
    )

    monkeypatch.delenv("HANGARLLM_SALT_KEY", raising=False)
    monkeypatch.setattr("hangarllm.proxy.proxy_server.master_key", "sk-old-master")
    stored = encrypt_guardrail_hangarllm_params({"guardrail": "bedrock", "mode": "pre_call", "api_key": "vendor-key"})
    prisma_client = MagicMock()
    prisma_client.db.hangarllm_guardrailstable.find_many = AsyncMock(
        return_value=[_Row(guardrail_id="g-1", updated_at="2026-09-28T00:00:00Z", hangarllm_params=stored)]
    )
    prisma_client.db.hangarllm_guardrailstable.update_many = AsyncMock(return_value=1)

    rows_updated = await GuardrailRegistry.rotate_guardrail_params_master_key(
        prisma_client=prisma_client, new_master_key="sk-new-master"
    )

    rotated = _stored_params(prisma_client.db.hangarllm_guardrailstable.update_many)
    assert rows_updated == 1
    assert prisma_client.db.hangarllm_guardrailstable.update_many.call_args.kwargs["where"] == {
        "guardrail_id": "g-1",
        "updated_at": "2026-09-28T00:00:00Z",
    }
    assert rotated["api_key"] != stored["api_key"]
    monkeypatch.setattr("hangarllm.proxy.proxy_server.master_key", "sk-new-master")
    assert decrypt_guardrail_hangarllm_params(rotated)["api_key"] == "vendor-key"


@pytest.mark.asyncio
async def test_rotate_guardrail_params_keeps_salt_key_encryption_when_salt_key_is_set(monkeypatch):
    from hangarllm.proxy.guardrails.guardrail_registry import (
        decrypt_guardrail_hangarllm_params,
        encrypt_guardrail_hangarllm_params,
    )

    monkeypatch.setenv("HANGARLLM_SALT_KEY", "sk-salt-guardrail-test")
    stored = encrypt_guardrail_hangarllm_params({"guardrail": "bedrock", "api_key": "vendor-key"})
    prisma_client = MagicMock()
    prisma_client.db.hangarllm_guardrailstable.find_many = AsyncMock(
        return_value=[_Row(guardrail_id="g-1", updated_at="t1", hangarllm_params=stored)]
    )
    prisma_client.db.hangarllm_guardrailstable.update_many = AsyncMock(return_value=1)

    await GuardrailRegistry.rotate_guardrail_params_master_key(prisma_client=prisma_client, new_master_key="sk-new")

    rotated = _stored_params(prisma_client.db.hangarllm_guardrailstable.update_many)
    assert decrypt_guardrail_hangarllm_params(rotated)["api_key"] == "vendor-key"


@pytest.mark.asyncio
async def test_rotate_guardrail_params_retries_a_row_edited_during_rotation(monkeypatch):
    from hangarllm.proxy.guardrails.guardrail_registry import (
        decrypt_guardrail_hangarllm_params,
        encrypt_guardrail_hangarllm_params,
    )

    monkeypatch.delenv("HANGARLLM_SALT_KEY", raising=False)
    monkeypatch.setattr("hangarllm.proxy.proxy_server.master_key", "sk-old-master")
    snapshot = _Row(
        guardrail_id="g-1", updated_at="t1", hangarllm_params=encrypt_guardrail_hangarllm_params({"api_key": "old-key"})
    )
    edited = _Row(
        guardrail_id="g-1", updated_at="t2", hangarllm_params=encrypt_guardrail_hangarllm_params({"api_key": "edited-key"})
    )
    prisma_client = MagicMock()
    prisma_client.db.hangarllm_guardrailstable.find_many = AsyncMock(return_value=[snapshot])
    prisma_client.db.hangarllm_guardrailstable.find_unique = AsyncMock(return_value=edited)
    prisma_client.db.hangarllm_guardrailstable.update_many = AsyncMock(side_effect=[0, 1])

    rows_updated = await GuardrailRegistry.rotate_guardrail_params_master_key(
        prisma_client=prisma_client, new_master_key="sk-new-master"
    )

    last_call = prisma_client.db.hangarllm_guardrailstable.update_many.call_args
    assert rows_updated == 1
    assert last_call.kwargs["where"] == {"guardrail_id": "g-1", "updated_at": "t2"}
    monkeypatch.setattr("hangarllm.proxy.proxy_server.master_key", "sk-new-master")
    assert decrypt_guardrail_hangarllm_params(_stored_params(prisma_client.db.hangarllm_guardrailstable.update_many)) == {
        "api_key": "edited-key"
    }


@pytest.mark.asyncio
async def test_rotate_guardrail_params_gives_up_on_a_row_that_keeps_changing(monkeypatch):
    from hangarllm.constants import GUARDRAIL_ROTATION_ATTEMPTS
    from hangarllm.proxy.guardrails.guardrail_registry import encrypt_guardrail_hangarllm_params

    monkeypatch.delenv("HANGARLLM_SALT_KEY", raising=False)
    monkeypatch.setattr("hangarllm.proxy.proxy_server.master_key", "sk-old-master")
    row = _Row(guardrail_id="g-1", updated_at="t1", hangarllm_params=encrypt_guardrail_hangarllm_params({"api_key": "k"}))
    prisma_client = MagicMock()
    prisma_client.db.hangarllm_guardrailstable.find_many = AsyncMock(return_value=[row])
    prisma_client.db.hangarllm_guardrailstable.find_unique = AsyncMock(return_value=row)
    prisma_client.db.hangarllm_guardrailstable.update_many = AsyncMock(return_value=0)

    rows_updated = await GuardrailRegistry.rotate_guardrail_params_master_key(
        prisma_client=prisma_client, new_master_key="sk-new-master"
    )

    assert rows_updated == 0
    assert prisma_client.db.hangarllm_guardrailstable.update_many.await_count == GUARDRAIL_ROTATION_ATTEMPTS
    assert prisma_client.db.hangarllm_guardrailstable.find_unique.await_count == GUARDRAIL_ROTATION_ATTEMPTS - 1
