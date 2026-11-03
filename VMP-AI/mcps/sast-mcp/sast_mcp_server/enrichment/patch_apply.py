"""Apply an agent-generated unified diff to files on disk.

Uses ``git apply`` as the patch engine. ``git apply`` works on a plain
directory (no repository required), strips the leading ``a/``..``b/`` path
component by default, and—critically for safety—refuses to touch paths that
escape the target directory unless ``--unsafe-paths`` is passed (we never
pass it).
"""

import asyncio
import logging
import os
import tempfile

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60


async def apply_unified_diff(
    target_path: str,
    patch_text: str,
    check_only: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    reverse: bool = False,
) -> tuple[bool, str]:
    """Apply (or validate) a unified diff against files under ``target_path``.

    Args:
        target_path: Directory the patch paths are relative to.
        patch_text: The unified diff to apply.
        check_only: If True, run ``git apply --check`` and do not modify files.
        timeout: Subprocess timeout in seconds.
        reverse: If True, pass ``-R`` to undo a previously applied patch (used
            by ``remediate_and_verify`` to roll back when a fix fails to clear
            the finding).

    Returns:
        A ``(success, detail)`` tuple. ``detail`` carries git's stderr on
        failure, or a short confirmation message on success.
    """
    if not patch_text.strip():
        return (False, "Empty patch: nothing to apply.")

    # git apply needs the patch to end with a newline to parse the final hunk.
    if not patch_text.endswith("\n"):
        patch_text += "\n"

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".patch", prefix="sast-mcp-")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(patch_text)

        cmd = ["git", "-C", target_path, "apply"]
        if check_only:
            cmd.append("--check")
        if reverse:
            cmd.append("-R")
        cmd.append(tmp_path)

        logger.info("Running: %s", " ".join(cmd))
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except FileNotFoundError:
            return (False, "git is not installed or not on PATH; cannot apply patches.")
        except asyncio.TimeoutError:
            proc.kill()
            return (False, f"git apply timed out after {timeout}s.")

        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0:
            return (False, stderr_text or f"git apply failed (exit {proc.returncode}).")

        if check_only:
            action = "validated"
        elif reverse:
            action = "reverted"
        else:
            action = "applied"
        return (True, f"Patch {action} successfully.")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
