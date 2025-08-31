"""
Persistent Julia runner used to keep a single Julia process alive and evaluate expressions
safely via stdin/stdout with a simple line protocol.

The runner reads lines of Julia code (one expression per line) and returns a base64-encoded
stringified result prefixed by a marker. Errors are returned with an ERROR marker.

This is intentionally lightweight to avoid external dependencies and to be easy to use
from existing code (the module exports a thread-safe PersistentJuliaRunner class and
convenience global helpers).
"""
from __future__ import annotations

import subprocess
import threading
import base64
import time
import tempfile
import os
import sys
from typing import Optional, Tuple

# Ensure stdout uses UTF-8 encoding to handle Julia output properly
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass  # Ignore if reconfigure is not available

RESULT_MARKER = "<<<RESULT>>>"
ERROR_MARKER = "<<<ERROR>>>"


class PersistentJuliaRunner:
    """Start a persistent Julia subprocess that evaluates single-line Julia expressions.

    Note: expressions must be valid Julia expressions parseable by Meta.parse. The
    expression's printed string(value) will be base64-encoded and returned to avoid
    delimiting issues.
    """

    def __init__(self, julia_executable: str = "julia"):
        self.julia_executable = julia_executable
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._start_process()

    def _start_process(self):
        if self._proc is not None:
            return
        # Create a small bootstrap Julia script to avoid Windows command-line quoting/length issues
        bootstrap = f"""
using Base64
while true
    line = try
        readline(stdin)
    catch
        ""
    end
    if line == ""
        continue
    end
    try
        result = eval(Meta.parse(line))
        println("{RESULT_MARKER}" * Base64.base64encode(string(result)))
    catch e
        println("{ERROR_MARKER}" * Base64.base64encode(string(e)))
    end
    flush(stdout)
end
"""
        tmp = tempfile.NamedTemporaryFile(prefix="julia_runner_", suffix=".jl", delete=False)
        self._bootstrap_path = tmp.name
        with tmp:
            tmp.write(bootstrap.encode("utf-8"))

        cmd = [self.julia_executable, "--startup-file=no", "--quiet", self._bootstrap_path]
        # Merge stderr into stdout to avoid deadlocks when Julia writes a lot to stderr
        # (e.g., timing macros) and we're only reading stdout.
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # line-buffered in text mode
            universal_newlines=True,
        )

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def stop(self):
        with self._lock:
            if self._proc is None:
                return
            try:
                self._proc.terminate()
            except Exception:
                pass
            try:
                self._proc.wait(timeout=2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
            # Attempt to remove bootstrap file
            try:
                path = getattr(self, "_bootstrap_path", None)
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

    def eval(self, expr: str, timeout: float = 10.0) -> Tuple[bool, str]:
        """Evaluate a single-line Julia expression and return (success, result_or_error).

        The expression should be a single Julia expression. The returned result is
        the decoded string form of Julia's string(...) of the evaluated expression.
        """
        if not self.is_alive():
            # attempt restart
            self._start_process()

        with self._lock:
            proc = self._proc
            if proc is None or proc.stdin is None or proc.stdout is None:
                return False, "Julia process not available"

            # If the expression contains newlines (a script) or is long, encode it
            # and send a one-line wrapper that decodes and executes it via include_string.
            send_expr = expr
            try:
                if "\n" in expr or len(expr) > 800:
                    b64 = base64.b64encode(expr.encode("utf-8")).decode("ascii")
                    # construct a single-line Julia expression that decodes and includes the script
                    send_expr = f"let _b=Base64.base64decode(\"{b64}\"); _s=String(_b); include_string(Main, _s); end"
            except Exception:
                send_expr = expr

            # Write expression and newline
            try:
                proc.stdin.write(send_expr + "\n")
                proc.stdin.flush()
            except Exception as e:
                return False, f"Failed to write to Julia stdin: {e}"

            # Read lines until we get a marker using a background reader thread so we can time out safely.
            end_time = time.time() + timeout

            result_holder: dict[str, Optional[str] | bool] = {"done": False, "ok": False, "payload": None}
            logs: list[str] = []
            done_evt = threading.Event()

            def _reader():
                try:
                    # Iterate line-by-line; stderr is merged into stdout.
                    for line in proc.stdout:  # type: ignore[arg-type]
                        if line is None:
                            continue
                        s = line.rstrip("\r\n")
                        if s.startswith(RESULT_MARKER):
                            b64 = s[len(RESULT_MARKER):]
                            try:
                                decoded = base64.b64decode(b64).decode("utf-8", errors="replace")
                            except Exception:
                                decoded = "<base64 decode error>"
                            result_holder["done"] = True
                            result_holder["ok"] = True
                            result_holder["payload"] = decoded
                            break
                        if s.startswith(ERROR_MARKER):
                            b64 = s[len(ERROR_MARKER):]
                            try:
                                decoded = base64.b64decode(b64).decode("utf-8", errors="replace")
                            except Exception:
                                decoded = "<base64 decode error>"
                            result_holder["done"] = True
                            result_holder["ok"] = False
                            result_holder["payload"] = decoded
                            break
                        # collect non-protocol lines so callers can get printed output
                        logs.append(s)
                except Exception as _:
                    # If the reader itself crashes, surface a generic error
                    if not result_holder["done"]:
                        result_holder["done"] = True
                        result_holder["ok"] = False
                        result_holder["payload"] = "Reader thread error"
                finally:
                    done_evt.set()

            t = threading.Thread(target=_reader, name="JuliaRunnerReader", daemon=True)
            t.start()

            # Wait for completion or timeout
            remaining = max(0.0, end_time - time.time())
            done = done_evt.wait(timeout=remaining)
            if done and result_holder["done"]:
                # If we captured any logs, prefer returning them; otherwise, return payload
                if logs and isinstance(result_holder["payload"], str) and bool(result_holder["ok"]):
                    return True, "\n".join(logs)
                return bool(result_holder["ok"]), str(result_holder["payload"] or "")

            # If we timed out, surface a clear message; leave the process alive for future calls.
            return False, "Timeout waiting for Julia response"


# Global singleton helpers
_global_runner: Optional[PersistentJuliaRunner] = None
_global_lock = threading.Lock()


def start_global_julia(julia_executable: str = "julia") -> PersistentJuliaRunner:
    global _global_runner
    with _global_lock:
        if _global_runner is None or not _global_runner.is_alive():
            _global_runner = PersistentJuliaRunner(julia_executable=julia_executable)
        return _global_runner


def stop_global_julia():
    global _global_runner
    with _global_lock:
        if _global_runner is not None:
            _global_runner.stop()
            _global_runner = None


def run_julia(expr: str, timeout: float = 10.0) -> Tuple[bool, str]:
    runner = start_global_julia()
    return runner.eval(expr, timeout=timeout)
