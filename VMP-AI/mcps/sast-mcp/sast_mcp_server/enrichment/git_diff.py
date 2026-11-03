"""Git diff integration for incremental scanning."""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def get_modified_files(target_path: str) -> set[str]:
    """Return a set of file paths modified according to git diff.

    Compares the working tree against HEAD to find changed files.

    Args:
        target_path: Path to the git repository root or a subdirectory.

    Returns:
        Set of relative file paths that have been modified.
        Returns empty set if git is not available or the path is not a git repo.
    """
    cmd = ["git", "-C", target_path, "diff", "--name-only", "HEAD"]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
    except FileNotFoundError:
        logger.warning("git binary not found on PATH. git_diff_only will not work.")
        return set()

    if proc.returncode != 0:
        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        logger.warning("git diff failed (rc=%d): %s", proc.returncode, stderr_text)
        return set()

    files = stdout.decode("utf-8").strip().split("\n")
    result = {f for f in files if f}
    logger.info("Git diff found %d modified files", len(result))
    return result
