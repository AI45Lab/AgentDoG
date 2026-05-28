import ast
import multiprocessing
import queue
import threading
from dataclasses import dataclass


SAFE_EXEC_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "isinstance": isinstance,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "next": next,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}

FORBIDDEN_CALLS = {"open", "exec", "eval", "__import__", "compile", "input"}
# Attribute-level restrictions stay focused on clearly dangerous process/filesystem helpers.
# Finite-state simulators often use list.remove(...) to update in-memory state, so `remove`
# is intentionally allowed here as long as imports and unsafe dunder access remain forbidden.
FORBIDDEN_ATTRS = {"system", "popen", "run", "unlink", "rmdir", "mkdir", "makedirs"}
SAFE_DUNDER_ATTRS = {"__class__", "__name__"}
VALIDATED_SOURCE_CACHE = set()


class ToolRuntimeError(RuntimeError):
    pass


class ToolValidationError(ToolRuntimeError):
    pass


class ToolTimeoutError(ToolRuntimeError):
    pass


class ToolContractError(ToolRuntimeError):
    pass


@dataclass
class ToolSandboxConfig:
    execution_timeout_seconds: float = 2.0
    max_source_chars: int = 12000


def validate_tool_source(source_code, entrypoint_name="execute"):
    cache_key = (entrypoint_name, source_code)
    if cache_key in VALIDATED_SOURCE_CACHE:
        return

    if len(source_code) > ToolSandboxConfig().max_source_chars:
        raise ToolValidationError("Tool source exceeds maximum allowed size.")

    try:
        tree = ast.parse(source_code)
    except SyntaxError as exc:
        raise ToolValidationError(f"Tool source has invalid syntax: {exc}") from exc

    has_entrypoint = False
    has_metadata = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ToolValidationError("Tool source must not use imports.")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                raise ToolValidationError(f"Forbidden call detected in tool source: {node.func.id}")
            if isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_ATTRS:
                raise ToolValidationError(f"Forbidden attribute call detected in tool source: {node.func.attr}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__") and node.attr not in SAFE_DUNDER_ATTRS:
            raise ToolValidationError("Dunder attribute access is not allowed in tool source.")
        if isinstance(node, ast.FunctionDef) and node.name == entrypoint_name:
            has_entrypoint = True
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "TOOL_METADATA":
                    has_metadata = True

    if not has_entrypoint:
        raise ToolValidationError(f"Tool source must define {entrypoint_name}(arguments, state, context).")
    if not has_metadata:
        raise ToolValidationError("Tool source must define TOOL_METADATA.")
    VALIDATED_SOURCE_CACHE.add(cache_key)


def _worker(source_code, entrypoint_name, arguments, state, context, result_queue):
    namespace = {"__builtins__": SAFE_EXEC_BUILTINS}
    try:
        exec(source_code, namespace, namespace)
        entrypoint = namespace.get(entrypoint_name)
        if not callable(entrypoint):
            result_queue.put(("error", f"Entrypoint {entrypoint_name} is not callable."))
            return
        result = entrypoint(arguments, state, context)
        result_queue.put(("ok", result))
    except Exception as exc:  # pragma: no cover - child process path
        result_queue.put(("error", f"{type(exc).__name__}: {exc}"))


def _load_tool_entrypoint(source_code, entrypoint_name):
    validate_tool_source(source_code, entrypoint_name=entrypoint_name)
    namespace = {"__builtins__": SAFE_EXEC_BUILTINS}
    exec(source_code, namespace, namespace)
    entrypoint = namespace.get(entrypoint_name)
    if not callable(entrypoint):
        raise ToolRuntimeError(f"Entrypoint {entrypoint_name} is not callable.")
    return entrypoint


class EpisodeToolExecutor:
    """Execute all tool calls for an episode on a single worker thread.

    This removes the fixed per-call process startup overhead while keeping tool
    execution serialized per episode.
    """

    def __init__(self, tool_programs, sandbox_config=None, thread_name=None):
        self.sandbox_config = sandbox_config or ToolSandboxConfig()
        self._tool_programs = dict(tool_programs)
        self._request_queue = queue.Queue()
        self._ready = threading.Event()
        self._init_error = None
        self._closed = False
        self._compiled_entrypoints = {}
        self._thread = threading.Thread(
            target=self._worker_loop,
            name=thread_name or "episode-tool-executor",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait(timeout=max(self.sandbox_config.execution_timeout_seconds, 1.0))
        if self._init_error is not None:
            raise self._init_error
        if not self._ready.is_set():
            raise ToolRuntimeError("Episode tool executor failed to initialize in time.")

    @property
    def worker_ident(self):
        return self._thread.ident

    def _worker_loop(self):
        try:
            for tool_name, program in self._tool_programs.items():
                self._compiled_entrypoints[tool_name] = _load_tool_entrypoint(
                    program["source_code"],
                    program["entrypoint_name"],
                )
        except Exception as exc:  # pragma: no cover - startup failure path
            self._init_error = exc
            self._ready.set()
            return
        self._ready.set()

        while True:
            request = self._request_queue.get()
            if request is None:
                return
            tool_name, arguments, state, context, result_queue = request
            try:
                entrypoint = self._compiled_entrypoints[tool_name]
                result = entrypoint(arguments, state, context)
                result_queue.put(("ok", result))
            except Exception as exc:  # pragma: no cover - worker failure path
                result_queue.put(("error", f"{type(exc).__name__}: {exc}"))

    def execute(self, tool_name, arguments, state, context):
        if self._closed:
            raise ToolRuntimeError("Episode tool executor is closed.")
        if self._init_error is not None:
            raise self._init_error
        if tool_name not in self._compiled_entrypoints:
            raise ToolRuntimeError(f"Tool {tool_name} is not loaded in this episode executor.")

        result_queue = queue.Queue(maxsize=1)
        self._request_queue.put((tool_name, arguments, state, context, result_queue))
        try:
            status, payload = result_queue.get(timeout=self.sandbox_config.execution_timeout_seconds)
        except queue.Empty as exc:
            raise ToolTimeoutError(
                f"Tool execution exceeded {self.sandbox_config.execution_timeout_seconds:.2f}s timeout."
            ) from exc

        if status == "error":
            raise ToolRuntimeError(payload)
        return payload

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._request_queue.put(None)
        self._thread.join(timeout=0.2)


def execute_tool_source(source_code, entrypoint_name, arguments, state, context, sandbox_config=None):
    sandbox_config = sandbox_config or ToolSandboxConfig()
    validate_tool_source(source_code, entrypoint_name=entrypoint_name)

    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(
        target=_worker,
        args=(source_code, entrypoint_name, arguments, state, context, result_queue),
    )
    process.start()
    process.join(timeout=sandbox_config.execution_timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(timeout=1)
        raise ToolTimeoutError(
            f"Tool execution exceeded {sandbox_config.execution_timeout_seconds:.2f}s timeout."
        )

    try:
        status, payload = result_queue.get_nowait()
    except queue.Empty as exc:
        raise ToolRuntimeError("Tool subprocess exited without producing a result.") from exc

    if status == "error":
        raise ToolRuntimeError(payload)
    return payload
