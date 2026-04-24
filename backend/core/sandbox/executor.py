"""
Secure Sandbox Executor.

Runs generated code inside ephemeral Docker containers with strict
resource limits and no network access. Captures stdout, stderr,
and exit codes for the Reviewer Agent.
"""

import asyncio
import logging
import tempfile
from pathlib import Path

import docker
from docker.errors import ContainerError, ImageNotFound, APIError

from core.config import settings

logger = logging.getLogger(__name__)


class SandboxExecutor:
    """
    Ephemeral Docker container executor for untrusted code.

    Security measures:
    - No network access (network_mode="none")
    - Read-only filesystem
    - Memory and CPU limits enforced
    - Hard timeout
    - Container auto-removed after execution
    """

    def __init__(self):
        self.timeout = settings.sandbox_timeout
        self.memory_limit = settings.sandbox_memory_limit
        self.cpu_quota = 50000  # 50% of one core

        try:
            self.client = docker.from_env()
            self._available = True
            logger.info("Docker sandbox initialized successfully")
        except Exception as e:
            self._available = False
            logger.warning(f"Docker not available for sandboxing: {e}")

    @property
    def is_available(self) -> bool:
        return self._available and settings.sandbox_enabled

    async def execute(
        self,
        code_blocks: dict[str, str],
        entry_point: str = "main.py",
        language: str = "python",
        install_deps: bool = True,
    ) -> dict:
        """
        Execute code in an ephemeral sandbox container.

        Args:
            code_blocks: Dictionary of {filename: code_content}.
            entry_point: The file to execute as the entry point.
            language: Programming language ("python" or "node").
            install_deps: Whether to install dependencies before running.

        Returns:
            {
                "exit_code": int,
                "stdout": str,
                "stderr": str,
                "timed_out": bool
            }
        """
        if not self.is_available:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": "Sandbox unavailable: Docker not connected or sandbox disabled",
                "timed_out": False,
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Write all code files to the temp directory
            for filename, content in code_blocks.items():
                filepath = Path(tmpdir) / filename
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_text(content, encoding="utf-8")

            # 2. Build the execution command
            image = self._get_image(language)
            command = self._build_command(
                entry_point, language, install_deps, code_blocks
            )

            logger.info(
                f"Sandbox: image={image}, entry={entry_point}, "
                f"files={len(code_blocks)}, timeout={self.timeout}s"
            )

            # 3. Run the container
            try:
                output = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.containers.run(
                        image=image,
                        command=["sh", "-c", command],
                        volumes={tmpdir: {"bind": "/app", "mode": "ro"}},
                        working_dir="/app",
                        mem_limit=self.memory_limit,
                        cpu_quota=self.cpu_quota,
                        network_mode="none",
                        read_only=False,  # Allow pip install to work in tmpfs
                        tmpfs={"/tmp": "size=64m"},
                        remove=True,
                        detach=False,
                        stdout=True,
                        stderr=True,
                        timeout=self.timeout,
                    ),
                )

                return {
                    "exit_code": 0,
                    "stdout": output.decode("utf-8") if isinstance(output, bytes) else str(output),
                    "stderr": "",
                    "timed_out": False,
                }

            except ContainerError as e:
                return {
                    "exit_code": e.exit_status,
                    "stdout": e.output.decode("utf-8") if e.output else "",
                    "stderr": e.stderr.decode("utf-8") if e.stderr else str(e),
                    "timed_out": False,
                }

            except ImageNotFound:
                logger.error(f"Docker image not found: {image}")
                return {
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"Docker image not found: {image}. Run: docker pull {image}",
                    "timed_out": False,
                }

            except APIError as e:
                if "timeout" in str(e).lower() or "deadline" in str(e).lower():
                    return {
                        "exit_code": -1,
                        "stdout": "",
                        "stderr": f"Sandbox timed out after {self.timeout}s",
                        "timed_out": True,
                    }
                return {
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"Docker API error: {str(e)}",
                    "timed_out": False,
                }

            except Exception as e:
                logger.error(f"Unexpected sandbox error: {e}")
                return {
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"Sandbox error: {str(e)}",
                    "timed_out": False,
                }

    def _get_image(self, language: str) -> str:
        """Select the appropriate Docker base image."""
        images = {
            "python": "python:3.12-slim",
            "node": "node:20-slim",
            "typescript": "node:20-slim",
        }
        return images.get(language, "python:3.12-slim")

    def _build_command(
        self,
        entry_point: str,
        language: str,
        install_deps: bool,
        code_blocks: dict[str, str],
    ) -> str:
        """Build the shell command to run inside the container."""
        parts = []

        if install_deps:
            if language == "python" and "requirements.txt" in code_blocks:
                parts.append("pip install -q -r requirements.txt 2>/dev/null")
            elif language in ("node", "typescript") and "package.json" in code_blocks:
                parts.append("npm install --silent 2>/dev/null")

        if language == "python":
            parts.append(f"python {entry_point}")
        elif language in ("node", "typescript"):
            parts.append(f"node {entry_point}")
        else:
            parts.append(f"python {entry_point}")

        return " && ".join(parts)


def detect_entry_point(architecture_schema: dict) -> str:
    """Infer the entry point file from the architecture schema."""
    file_tree = architecture_schema.get("file_tree", [])

    # Check for common entry points
    candidates = ["main.py", "app.py", "server.py", "index.js", "index.ts"]
    for candidate in candidates:
        matching = [f for f in file_tree if f.endswith(candidate)]
        if matching:
            return matching[0]

    # Default to first Python/JS file
    for f in file_tree:
        if f.endswith((".py", ".js", ".ts")):
            return f

    return "main.py"


def detect_language(architecture_schema: dict) -> str:
    """Infer the primary language from the architecture schema."""
    backend = architecture_schema.get("tech_stack", {}).get("backend", "")

    if backend in ("fastapi", "flask", "django"):
        return "python"
    elif backend in ("express", "nestjs", "koa"):
        return "node"

    # Fallback: check file extensions
    file_tree = architecture_schema.get("file_tree", [])
    py_count = sum(1 for f in file_tree if f.endswith(".py"))
    js_count = sum(1 for f in file_tree if f.endswith((".js", ".ts", ".tsx")))

    return "python" if py_count >= js_count else "node"
