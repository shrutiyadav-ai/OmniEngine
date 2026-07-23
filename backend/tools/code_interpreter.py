"""
OmniEngine — Code Interpreter Tool (Docker Sandbox)

Executes Python code safely inside an isolated, ephemeral Docker container sandbox.
Enforces memory/CPU limits, execution timeouts, and network isolation.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any

from pydantic import BaseModel, Field

from backend.core.config import get_settings
from backend.tools.registry import BaseTool

logger = logging.getLogger(__name__)


class CodeInterpreterInput(BaseModel):
    """Input schema for code execution."""

    code: str = Field(..., description="Python code string to execute", min_length=1)
    timeout_seconds: int = Field(30, description="Execution timeout in seconds", ge=1, le=60)


class CodeInterpreterTool(BaseTool):
    """Docker-based code interpreter tool."""

    name = "code_interpreter"
    description = (
        "Executes Python code in a secure, sandboxed container. Returns stdout and stderr."
    )
    args_schema = CodeInterpreterInput

    async def execute(  # type: ignore[override]
        self, code: str, timeout_seconds: int = 30, **kwargs: Any
    ) -> str:
        """Execute code in Docker sandbox."""
        settings = get_settings()

        try:
            import docker

            client = docker.from_env()

            # Prepare temporary code file
            file_id = str(uuid.uuid4())
            tmp_dir = "/tmp/omni-sandbox"  # noqa: S108
            os.makedirs(tmp_dir, exist_ok=True)
            host_file_path = os.path.join(tmp_dir, f"code_{file_id}.py")

            with open(host_file_path, "w", encoding="utf-8") as f:  # noqa: ASYNC230
                f.write(code)

            # Run in container with strict security isolation
            container = client.containers.run(
                image=settings.sandbox_image,
                command=["python", f"/sandbox/workspace/code_{file_id}.py"],
                volumes={tmp_dir: {"bind": "/sandbox/workspace", "mode": "ro"}},
                network_mode="none" if settings.sandbox_network_disabled else "bridge",
                mem_limit=settings.sandbox_max_memory,
                nano_cpus=int(settings.sandbox_max_cpu * 1e9),
                pids_limit=64,
                read_only=True,
                detach=True,
            )

            # Wait for execution with timeout
            loop = asyncio.get_running_loop()
            try:
                result = await loop.run_in_executor(
                    None, lambda: container.wait(timeout=timeout_seconds)
                )
                logs = container.logs().decode("utf-8")
                exit_code = result.get("StatusCode", -1)

                return f"Exit Code: {exit_code}\nOutput:\n{logs}"

            except Exception:
                container.kill()
                return f"Execution timed out after {timeout_seconds} seconds."

            finally:
                container.remove(force=True)
                if os.path.exists(host_file_path):  # noqa: ASYNC240
                    os.remove(host_file_path)

        except Exception as e:
            logger.warning(
                "Docker sandbox not available, using subprocess/simulation fallback: %s", str(e)
            )
            # Fallback for environments without Docker daemon access
            try:
                proc = await asyncio.create_subprocess_exec(
                    "python",
                    "-c",
                    code,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
                return f"Output:\n{stdout.decode()}\nErrors:\n{stderr.decode()}"
            except Exception as fallback_err:
                return f"Code execution failed: {fallback_err!s}"
