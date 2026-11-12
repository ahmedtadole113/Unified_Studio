"""HTTP command execution runner for the isolated Linux SRE Practice Sandbox."""

import json
import os
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

DEFAULT_CWD = "/lab"


def _safe_cwd(cwd: str) -> str:
    if not cwd:
        return DEFAULT_CWD
    real = os.path.realpath(cwd)
    if not os.path.isdir(real):
        return DEFAULT_CWD
    return real


def run_shell_command(command: str, cwd: str = DEFAULT_CWD, timeout: int = 25) -> dict:
    """Execute a shell command in the practice sandbox and return output + updated cwd."""
    work_dir = _safe_cwd(cwd)
    clamped_timeout = max(2, min(int(timeout), 45))
    marker = "__LAB_PWD_MARKER__"
    wrapped = f"{command}\n__ec=$?\necho '{marker}'\"$(pwd)\"\nexit $__ec"
    started = time.time()
    try:
        proc = subprocess.run(
            ["bash", "-lc", wrapped],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=clamped_timeout,
            env={
                **os.environ,
                "HOME": "/root",
                "TERM": "xterm-256color",
                "KUBECONFIG": "/root/.kube/config",
            },
        )
        stdout = proc.stdout or ""
        new_cwd = work_dir
        if marker in stdout:
            before, after = stdout.rsplit(marker, 1)
            stdout = before.rstrip("\n")
            candidate = after.strip().splitlines()[0] if after.strip() else work_dir
            if os.path.isdir(candidate):
                new_cwd = candidate
        return {
            "stdout": stdout[-16000:],
            "stderr": (proc.stderr or "")[-8000:],
            "exit_code": proc.returncode,
            "cwd": new_cwd,
            "duration_ms": int((time.time() - started) * 1000),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "stdout": (exc.stdout or "")[-8000:],
            "stderr": f"Command timed out after {clamped_timeout}s. Avoid blocking commands like 'top' without '-b -n1' or 'tail -f' without timeout.",
            "exit_code": 124,
            "cwd": work_dir,
            "duration_ms": int((time.time() - started) * 1000),
        }


def get_tool_status() -> dict:
    """Check installed CLI tools inside the practice sandbox."""
    checks = {
        "bash": "bash --version | head -n1",
        "git": "git --version",
        "python3": "python3 --version",
        "docker": "docker --version",
        "kubectl": "kubectl version --client --output=yaml | grep gitVersion | head -n1",
        "helm": "helm version --short",
        "terraform": "terraform version | head -n1",
        "ansible": "ansible --version | head -n1",
        "nginx": "nginx -v 2>&1",
    }
    versions = {}
    for name, cmd in checks.items():
        res = run_shell_command(cmd, cwd="/lab", timeout=5)
        versions[name] = (res["stdout"] or res["stderr"]).strip() if res["exit_code"] == 0 else "unavailable"
    k8s_ok = run_shell_command("kubectl get nodes --no-headers", cwd="/lab", timeout=5)
    return {
        "status": "ok",
        "cwd": "/lab",
        "tools": versions,
        "k8s_connected": k8s_ok["exit_code"] == 0,
        "k8s_nodes": k8s_ok["stdout"].strip(),
    }


class LabHandler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/status":
            self._send_json(200, get_tool_status())
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            self._send_json(400, {"error": str(exc)})
            return

        if path == "/exec":
            cmd = str(body.get("command", "")).strip()
            if not cmd:
                self._send_json(400, {"error": "command is required"})
                return
            res = run_shell_command(cmd, cwd=body.get("cwd", DEFAULT_CWD), timeout=body.get("timeout", 25))
            self._send_json(200, res)
        elif path == "/reset":
            res = run_shell_command("bash /opt/entrypoint.sh --seed-only || true", cwd="/lab", timeout=15)
            self._send_json(200, {"status": "reset", "detail": res})
        else:
            self._send_json(404, {"error": "Not found"})

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 8090), LabHandler)
    server.serve_forever()

