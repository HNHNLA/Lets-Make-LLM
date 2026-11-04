import ast
import datetime
import json
import os
import re

class Logger:
    @staticmethod
    def log(message, log_dir="."):
        # Create the log directory when it does not exist.
        os.makedirs(log_dir, exist_ok=True)
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        filepath = os.path.join(log_dir, f"{date_str}-lml.log")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(filepath, "a", encoding="utf-8") as stream:
            stream.write(f"[{timestamp}] {message}\n")


def extract_code(text):
    # Remove common Markdown code fences from model-generated Python.
    match = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def extract_json(text):
    # Extract the first JSON object from a model response.
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("The AI response did not contain a JSON object.")
    result = json.loads(cleaned[start:end + 1])
    if not isinstance(result, dict):
        raise ValueError("The AI response JSON must be an object.")
    return result


# ---------------------------------------------------------------------------
# Generated-code validation
#
# This is an ALLOWLIST-first static check: anything not explicitly known to be
# safe is rejected. It is still only a first filter, not a sandbox. Paths that
# generated code writes to cannot be proven statically, so run the script in an
# isolated environment (bwrap / container, no network) as the real boundary.
# ---------------------------------------------------------------------------

MAX_CODE_CHARS = 100_000

# Never importable, even if the caller lists them in allowed_imports.
HARD_BLOCKED_MODULES = frozenset({
    "subprocess", "socket", "shutil", "ctypes", "sys", "importlib", "builtins",
    "pickle", "marshal", "multiprocessing", "signal", "pty", "runpy", "code",
    "codeop", "urllib", "http", "ftplib", "smtplib", "telnetlib", "requests",
    "httpx", "aiohttp", "webbrowser", "asyncio", "pip", "setuptools",
})

# Builtins that may not be referenced at all (not just called).
FORBIDDEN_NAMES = frozenset({
    "eval", "exec", "compile", "__import__", "breakpoint", "globals", "locals",
    "vars", "input", "__builtins__",
})

# Dynamic attribute access is only allowed with a constant, safe attribute name.
DYNAMIC_ATTR_FUNCS = frozenset({"getattr", "setattr", "delattr"})

# Attribute names rejected on ANY object (we cannot infer types statically).
# Note: "remove" also rejects list.remove(); acceptable for generated scripts.
FORBIDDEN_ATTRS = frozenset({
    # process execution / replacement
    "system", "popen", "startfile", "fork", "forkpty", "kill", "killpg",
    "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp", "execvpe",
    "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp",
    "spawnvpe", "posix_spawn", "posix_spawnp",
    # destructive / permission-changing filesystem operations
    "remove", "removedirs", "rmdir", "unlink", "rename", "renames", "rmtree",
    "chmod", "chown", "lchown", "chroot", "symlink", "link", "symlink_to",
    "hardlink_to",
    # modules reachable as attributes of allowed libraries (escape hatches)
    "os", "sys", "subprocess", "builtins", "importlib", "shutil", "socket",
    "ctypes", "pickle", "marshal", "multiprocessing", "cpp_extension", "hub",
    # network / remote uploads
    "push_to_hub", "hf_hub_download", "snapshot_download", "upload_file",
    "upload_folder", "create_repo", "login",
})

# Dunder attributes that are harmless; every other dunder access is rejected.
SAFE_DUNDER_ATTRS = frozenset({
    "__init__", "__name__", "__file__", "__class__", "__len__", "__getitem__",
    "__setitem__", "__call__", "__enter__", "__exit__", "__iter__", "__next__",
    "__post_init__", "__doc__", "__version__", "__str__", "__repr__", "__eq__",
    "__hash__",
})

# `import os` is permitted only for these members (reading, mkdir, paths).
OS_SAFE_ATTRS = frozenset({
    "path", "makedirs", "mkdir", "listdir", "getcwd", "environ", "getenv", "sep",
    "linesep", "pathsep", "curdir", "pardir", "cpu_count", "fspath", "fsencode",
    "fsdecode", "walk", "scandir", "stat", "getpid", "name", "devnull", "access",
    "R_OK", "W_OK", "X_OK", "F_OK", "PathLike",
})

# Fully qualified callables that load pickles / arbitrary code.
FORBIDDEN_DOTTED_CALLS = frozenset({"torch.load", "torch.jit.load"})

# "{0.__class__.__init__.__globals__}" style str.format attribute traversal.
_FORMAT_TRAVERSAL = re.compile(r"\{[^{}]*[.\[][^{}]*__")


class CodeValidationError(ValueError):
    """Raised when generated code breaks policy. `.violations` lists every finding."""

    def __init__(self, violations):
        self.violations = list(violations)
        super().__init__("Generated code rejected:\n- " + "\n- ".join(self.violations))


def _is_unsafe_dunder(name):
    return name.startswith("__") and name.endswith("__") and name not in SAFE_DUNDER_ATTRS


def _is_truthy_or_dynamic(node):
    # True unless the keyword value is the literal constant False/None.
    return not (isinstance(node, ast.Constant) and node.value in (False, None))


def validate_generated_python(code, allowed_imports):
    # Syntax + allowlist policy checks before generated code is executed.
    # Returns True when clean; otherwise raises CodeValidationError (a ValueError)
    # listing every violation, which can be fed back to the generator for a retry.
    if not isinstance(code, str) or not code.strip():
        raise CodeValidationError(["Generated code is empty."])
    if len(code) > MAX_CODE_CHARS:
        raise CodeValidationError([f"Generated code is too long ({len(code)} chars)."])
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
        raise CodeValidationError([f"Code could not be parsed: {exc}"]) from exc

    allowed = {str(name).split(".")[0] for name in allowed_imports}
    violations = []

    def flag(node, message):
        violations.append(f"line {getattr(node, 'lineno', '?')}: {message}")

    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    # Pass 1: imports. Track which local names are bound to which top-level module.
    aliases = {}
    os_aliases = set()

    def check_module(node, top):
        if top in HARD_BLOCKED_MODULES:
            flag(node, f"import of '{top}' is never allowed")
        elif top not in allowed:
            flag(node, f"import of disallowed module '{top}'")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                check_module(node, top)
                bound = alias.asname or top
                aliases[bound] = top
                if top == "os":
                    if alias.asname is None or alias.name == "os":
                        os_aliases.add(bound)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                flag(node, "relative imports are not allowed")
                continue
            module = node.module or ""
            top = module.split(".")[0]
            check_module(node, top)
            for alias in node.names:
                if alias.name == "*":
                    flag(node, "star imports are not allowed")
                    continue
                aliases[alias.asname or alias.name] = top
                if module == "os" and alias.name not in OS_SAFE_ATTRS:
                    flag(node, f"'from os import {alias.name}' is not allowed")
                if alias.name in FORBIDDEN_ATTRS or alias.name in FORBIDDEN_NAMES:
                    flag(node, f"importing '{alias.name}' is not allowed")

    def dotted_name(node):
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(aliases.get(node.id, node.id))
            return ".".join(reversed(parts))
        return None

    # Pass 2: names, attributes, calls, string constants.
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES:
                flag(node, f"use of '{node.id}' is not allowed")
            parent = parents.get(node)
            if node.id in DYNAMIC_ATTR_FUNCS:
                if not (isinstance(parent, ast.Call) and parent.func is node):
                    flag(node, f"'{node.id}' may only be called directly")
            if node.id in os_aliases and isinstance(node.ctx, ast.Load):
                if not (isinstance(parent, ast.Attribute) and parent.value is node):
                    flag(node, "the 'os' module may only be used via attribute access")

        elif isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_ATTRS:
                flag(node, f"use of attribute '{node.attr}' is not allowed")
            if _is_unsafe_dunder(node.attr):
                flag(node, f"access to '{node.attr}' is not allowed")
            if (
                isinstance(node.value, ast.Name)
                and node.value.id in os_aliases
                and node.attr not in OS_SAFE_ATTRS
            ):
                flag(node, f"'os.{node.attr}' is not allowed")

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in DYNAMIC_ATTR_FUNCS:
                target = node.args[1] if len(node.args) >= 2 else None
                if not (isinstance(target, ast.Constant) and isinstance(target.value, str)):
                    flag(node, f"{node.func.id}() requires a constant attribute name")
                elif target.value in FORBIDDEN_ATTRS or _is_unsafe_dunder(target.value):
                    flag(node, f"{node.func.id}() on '{target.value}' is not allowed")
            if dotted_name(node.func) in FORBIDDEN_DOTTED_CALLS:
                flag(node, f"call to '{dotted_name(node.func)}' is not allowed")
            for keyword in node.keywords:
                if keyword.arg in {"trust_remote_code", "push_to_hub"} and _is_truthy_or_dynamic(keyword.value):
                    flag(node, f"keyword '{keyword.arg}' must be the literal False")

        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _FORMAT_TRAVERSAL.search(node.value):
                flag(node, "format string with attribute/index traversal is not allowed")

    if violations:
        raise CodeValidationError(violations)
    return True
