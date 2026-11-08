import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final

import pytest

import hangarllm
from hangarllm_cli.main import cli

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

_HELP_ARGV: Final = (
    ("--help",),
    ("logout", "--help"),
    ("login", "--help"),
    ("models", "list", "--help"),
    ("claude", "--help"),
    ("opencode", "--help"),
    ("codex", "--help"),
    ("pi", "--help"),
    ("keys", "list", "--help"),
)

_COMMAND_ARGV: Final = (("logout",), ("whoami",))

_RUN_EACH_ARGV: Final = """
import contextlib, io, json, sys
from {module} import cli
runs = {{}}
for argv in json.loads(sys.argv[1]):
    sys.argv = ["lite", *argv]
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        try:
            cli()
        except SystemExit as stopped:
            code = stopped.code
        else:
            code = 0
    runs[" ".join(argv)] = {{"exit": code, "output": output.getvalue()}}
print(json.dumps({{"runs": runs, "sdk_initialized": "completion" in vars(sys.modules["hangarllm"])}}))
"""

_USE_SDK_AFTER_HELP: Final = """
import builtins, importlib, json, sys
interpreter_imports = (builtins.__import__, importlib.import_module)
from {module} import cli
sys.argv = ["lite", "--help"]
try:
    cli()
except SystemExit:
    pass
before = "completion" in vars(sys.modules["hangarllm"])
{first_use}
from hangarllm.router import Router
import hangarllm
import hangarllm.responses.main
from hangarllm import acompletion
print(json.dumps({{
    "before": before,
    "router": Router.__name__,
    "completion": callable(hangarllm.completion),
    "acompletion": acompletion is hangarllm.acompletion,
    "responses_is_function": callable(hangarllm.responses) and not isinstance(hangarllm.responses, type(hangarllm)),
    "namespace": sorted(vars(hangarllm)),
    "module_type": type(hangarllm).__name__,
    "imports_restored": (builtins.__import__, importlib.import_module) == interpreter_imports,
}}))
"""

_FIRST_USE_FROM_THREADS: Final = """
import json, sys, threading
from hangarllm_cli.main import cli
sys.argv = ["lite", "--help"]
try:
    cli()
except SystemExit:
    pass
import hangarllm
start = threading.Barrier(4)
seen = []
def use_sdk():
    start.wait()
    try:
        seen.append(callable(hangarllm.completion))
    except AttributeError as error:
        seen.append(str(error))
threads = [threading.Thread(target=use_sdk) for _ in range(4)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
print(json.dumps({"seen": seen}))
"""

_STAR_IMPORT_AFTER_HELP: Final = """
import json, sys
from hangarllm_cli.main import cli
sys.argv = ["lite", "--help"]
try:
    cli()
except SystemExit:
    pass
before = "completion" in vars(sys.modules["hangarllm"])
from hangarllm import *
print(json.dumps({"before": before, "completion": callable(globals().get("completion")), "acompletion": callable(globals().get("acompletion"))}))
"""

_SDK_WHOSE_SUBMODULE_READS_IT_WHILE_LOADING: Final = {
    "sdk_sync.py": """
import threading
initializing = threading.Event()
submodule_loading = threading.Event()
""",
    "hangarllm/__init__.py": """
import sdk_sync
sdk_sync.initializing.set()
sdk_sync.submodule_loading.wait(2)
from hangarllm import submodule
ready = True
""",
    "hangarllm/submodule.py": """
import hangarllm
import sdk_sync
sdk_sync.submodule_loading.set()
ready_when_loaded = getattr(hangarllm, "ready", False)
""",
    "hangarllm/_process_defaults.py": "def apply_process_defaults() -> None: ...\n",
    "hangarllm/proxy/__init__.py": "",
    "hangarllm/proxy/client/__init__.py": "",
    "hangarllm/proxy/client/cli/__init__.py": "",
    "hangarllm/proxy/client/cli/main.py": """
import json, threading
import hangarllm
import sdk_sync

def cli():
    def initialize_sdk():
        hangarllm.ready

    def import_submodule_once_initialization_starts():
        sdk_sync.initializing.wait()
        import hangarllm.submodule

    threads = [threading.Thread(target=initialize_sdk, daemon=True),
               threading.Thread(target=import_submodule_once_initialization_starts, daemon=True)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    print(json.dumps({"finished": [not thread.is_alive() for thread in threads]}))

hangarllm_proxy_cli = cli
""",
}

_SDK_WHOSE_INIT_FAILS: Final = {
    "hangarllm/__init__.py": 'raise ImportError("a dependency of the SDK is broken")\n',
    "hangarllm/utils.py": "",
    "hangarllm/_process_defaults.py": "def apply_process_defaults() -> None: ...\n",
    "hangarllm/proxy/__init__.py": "",
    "hangarllm/proxy/client/__init__.py": "",
    "hangarllm/proxy/client/cli/__init__.py": "",
    "hangarllm/proxy/client/cli/main.py": """
import json
import hangarllm

def error_from(use):
    try:
        use()
    except Exception as error:
        return f"{type(error).__name__}: {error}"
    return None

def import_sdk_code():
    import hangarllm.utils

def cli():
    print(json.dumps([error_from(lambda: hangarllm.completion), error_from(lambda: hangarllm.completion), error_from(import_sdk_code)]))

hangarllm_proxy_cli = cli
""",
}

_RUN_LITE_AGAINST_SDK_AT: Final = """
import sys
sys.path.insert(0, sys.argv[1])
from hangarllm_cli.main import cli
cli()
"""

_PYPROJECT: Final = Path(__file__).resolve().parents[2] / "pyproject.toml"

_RUN_ENTRY_POINT_HELP: Final = """
import contextlib, io, json, sys
from {module} import {function}
imported_sdk = "hangarllm" in sys.modules
sys.argv = ["hangarllm", "--help"]
output = io.StringIO()
with contextlib.redirect_stdout(output):
    try:
        {function}()
    except SystemExit as stopped:
        code = stopped.code
    else:
        code = 0
print(json.dumps({{"imported_sdk": imported_sdk, "exit": code, "help": output.getvalue()}}))
"""

_WORKER_LOGGERS_UNDER_A_DEFAULT_LOG_CONFIG: Final = """
import json, logging, os
os.environ["HANGARLLM_WORKER_LOG_CONFIG"] = json.dumps({{"version": 1, "root": {{"level": "INFO"}}}})
from hangarllm_cli.main import proxy_worker_app
proxy_worker_app()
print(json.dumps({{name: logging.getLogger(name).disabled for name in {names!r}}}))
"""

_COMMAND_MODULES_LOADED_BY: Final = """
import json, sys
from hangarllm_cli.main import cli
sys.argv = ["lite", *sys.argv[1:]]
try:
    cli()
except SystemExit:
    pass
prefix = "hangarllm.proxy.client.cli.commands."
print(json.dumps({"modules": sorted(name[len(prefix):] for name in sys.modules if name.startswith(prefix))}))
"""


def _run(source: str, argv: tuple[str, ...], home: Path) -> dict[str, object]:
    result: Final = subprocess.run(
        [sys.executable, "-I", "-c", source, *argv],
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "HOME": str(home), "HANGARLLM_LOCAL_MODEL_COST_MAP": "True"},
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.rstrip("\n").rpartition("\n")[2])


@pytest.fixture(scope="module")
def cli_runs(tmp_path_factory: pytest.TempPathFactory) -> Mapping[str, dict[str, object]]:
    argv: Final = (json.dumps(_HELP_ARGV + _COMMAND_ARGV),)
    return {
        "thin": _run(_RUN_EACH_ARGV.format(module="hangarllm_cli.main"), argv, tmp_path_factory.mktemp("thin")),
        "full": _run(
            _RUN_EACH_ARGV.format(module="hangarllm.proxy.client.cli.main"), argv, tmp_path_factory.mktemp("full")
        ),
    }


def test_hangarllm_command_imports_the_proxy_only_when_it_runs(tmp_path: Path):
    module, _, function = tomllib.loads(_PYPROJECT.read_text())["project"]["scripts"]["hangarllm"].partition(":")
    run: Final = _run(_RUN_ENTRY_POINT_HELP.format(module=module, function=function), (), tmp_path)
    assert run["imported_sdk"] is False
    assert run["exit"] == 0
    assert "--num_workers" in str(run["help"])


def test_a_worker_log_config_silences_the_sdk_loggers_but_not_the_ones_the_proxy_app_creates(tmp_path: Path):
    disabled: Final = _run(
        _WORKER_LOGGERS_UNDER_A_DEFAULT_LOG_CONFIG.format(names=("HangarLLM Proxy", "hangarllm.proxy.health_check")),
        (),
        tmp_path,
    )
    assert disabled == {"HangarLLM Proxy": True, "hangarllm.proxy.health_check": False}


def test_lite_runs_commands_without_initializing_the_sdk(cli_runs: Mapping[str, dict[str, object]]):
    assert cli_runs["thin"]["sdk_initialized"] is False
    assert cli_runs["full"]["sdk_initialized"] is True


@pytest.mark.parametrize("argv", _HELP_ARGV + _COMMAND_ARGV, ids=" ".join)
def test_lite_prints_what_the_full_sdk_cli_prints(argv: tuple[str, ...], cli_runs: Mapping[str, dict[str, object]]):
    thin: Final = cli_runs["thin"]["runs"]
    full: Final = cli_runs["full"]["runs"]
    assert isinstance(thin, dict) and isinstance(full, dict)

    assert thin[" ".join(argv)] == full[" ".join(argv)]
    assert thin[" ".join(argv)]["output"]


@pytest.mark.parametrize(
    ("argv", "loaded", "not_loaded"),
    [
        (("logout", "--help"), {"auth"}, {"agents", "autoroute.commands", "models", "keys"}),
        (("models", "list", "--help"), {"models"}, {"agents", "autoroute.commands", "keys"}),
        (("claude", "--help"), {"agents"}, {"autoroute.commands", "models", "keys"}),
    ],
)
def test_lite_imports_only_the_command_it_runs(
    argv: tuple[str, ...], loaded: set[str], not_loaded: set[str], tmp_path: Path
):
    modules: Final = _run(_COMMAND_MODULES_LOADED_BY, argv, tmp_path)["modules"]
    assert isinstance(modules, list)

    assert loaded <= set(modules)
    assert not not_loaded & set(modules)


@pytest.fixture(scope="module")
def sdk_used_after_full_cli(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    return _run(
        _USE_SDK_AFTER_HELP.format(module="hangarllm.proxy.client.cli.main", first_use="pass"),
        (),
        tmp_path_factory.mktemp("full"),
    )


@pytest.mark.parametrize(
    "first_use",
    [
        "import hangarllm; hangarllm.completion",
        "import hangarllm; hangarllm.types.utils.ModelResponse",
        "from hangarllm import acompletion",
        "from hangarllm.router import Router",
        "from hangarllm.types import utils",
        "import hangarllm.responses.main",
        'importlib.import_module("hangarllm.router")',
        'importlib.import_module(".utils", "hangarllm")',
        'exec("from .types import utils", {"__name__": "hangarllm.lazy_import", "__package__": "hangarllm"})',
    ],
)
def test_sdk_initializes_in_place_on_first_use_after_lite_imports(
    first_use: str, sdk_used_after_full_cli: dict[str, object], tmp_path: Path
):
    thin: Final = _run(_USE_SDK_AFTER_HELP.format(module="hangarllm_cli.main", first_use=first_use), (), tmp_path)

    assert thin["before"] is False
    assert sdk_used_after_full_cli["before"] is True
    assert {**thin, "before": True} == sdk_used_after_full_cli
    assert (thin["router"], thin["completion"], thin["acompletion"], thin["responses_is_function"]) == (
        "Router",
        True,
        True,
        True,
    )


def test_star_import_after_lite_imports_gets_the_whole_sdk(tmp_path: Path):
    assert _run(_STAR_IMPORT_AFTER_HELP, (), tmp_path) == {"before": False, "completion": True, "acompletion": True}


def test_threads_that_use_the_sdk_at_once_all_wait_for_one_initialization(tmp_path: Path):
    used: Final = _run(_FIRST_USE_FROM_THREADS, (), tmp_path)

    assert used == {"seen": [True, True, True, True]}


def _write_sdk(root: Path, files: Mapping[str, str]) -> Path:
    for relative_path, source in files.items():
        (root / relative_path).parent.mkdir(parents=True, exist_ok=True)
        (root / relative_path).write_text(source)
    return root


def test_importing_sdk_code_while_another_thread_initializes_the_sdk_does_not_hang(tmp_path: Path):
    sdk_root: Final = _write_sdk(tmp_path / "sdk", _SDK_WHOSE_SUBMODULE_READS_IT_WHILE_LOADING)

    assert _run(_RUN_LITE_AGAINST_SDK_AT, (str(sdk_root),), tmp_path) == {"finished": [True, True]}


def test_every_use_after_a_failed_sdk_init_raises_the_init_error(tmp_path: Path):
    sdk_root: Final = _write_sdk(tmp_path / "sdk", _SDK_WHOSE_INIT_FAILS)

    assert _run(_RUN_LITE_AGAINST_SDK_AT, (str(sdk_root),), tmp_path) == ["ImportError: a dependency of the SDK is broken"] * 3


def test_lite_keeps_an_sdk_that_was_already_imported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setitem(sys.modules, "hangarllm", hangarllm)
    monkeypatch.setattr(hangarllm, "success_callback", ["kept"])
    monkeypatch.setattr(sys, "argv", ["lite", "--help"])

    with pytest.raises(SystemExit) as exited:
        cli()

    assert exited.value.code == 0
    assert "HangarLLM Proxy CLI - Manage your HangarLLM proxy server" in capsys.readouterr().out
    assert sys.modules["hangarllm"] is hangarllm
    assert hangarllm.success_callback == ["kept"]
