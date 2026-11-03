"""zstd dictionary training for the condense pipeline.

Trains a zstd dictionary on representative code samples from a codebase.
A dictionary trained on similar files improves compression 10-30% for
small-to-medium files (<100KB) vs. standard zstd.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...constants import CondenseDefaults, CondenseDictionaryDefaults, SubprocessDefaults
from ...core.logging import get_logger
from .estimator import _collect_files

logger = get_logger("condense.dictionary")

SMALL_SAMPLE_THRESHOLD = 10
MEDIUM_SAMPLE_THRESHOLD = 50
SMALL_SAMPLE_IMPROVEMENT_PCT = 5.0
MEDIUM_SAMPLE_IMPROVEMENT_PCT = 10.0
LARGE_SAMPLE_IMPROVEMENT_PCT = 15.0


def _resolve_dict_path(root: Path, language: Optional[str], output_dir: Optional[str]) -> Path:
    dict_dir = Path(output_dir) if output_dir else root / CondenseDictionaryDefaults.DICT_OUTPUT_DIR
    dict_dir.mkdir(parents=True, exist_ok=True)
    return dict_dir / f"dict_{language or 'all'}.zdict"


def _build_training_result(dict_path: Path, samples_used: int, total_bytes: int, language: Optional[str]) -> Dict[str, Any]:
    dict_size = dict_path.stat().st_size if dict_path.exists() else 0
    estimated_improvement = _estimate_improvement(samples_used, total_bytes)
    logger.info(
        "dictionary_trained",
        dict_path=str(dict_path),
        samples_used=samples_used,
        dict_size_bytes=dict_size,
    )
    return {
        "dict_path": str(dict_path),
        "dict_size_bytes": dict_size,
        "samples_used": samples_used,
        "total_sample_bytes": total_bytes,
        "estimated_improvement_pct": estimated_improvement,
        "language": language,
    }


def train_dictionary_impl(
    path: str,
    language: Optional[str] = None,
    sample_count: int = CondenseDictionaryDefaults.SAMPLE_COUNT,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Train a zstd dictionary on representative code samples.

    Args:
        path: Root directory to collect sample files from.
        language: Optional language filter (e.g. "python", "typescript").
        sample_count: Maximum number of sample files to use for training.
        output_dir: Directory to write the dictionary file. Defaults to
            `.condense/dictionaries/` relative to `path`.

    Returns:
        Dict with dict_path (str), dict_size_bytes (int), samples_used (int),
        and estimated_improvement_pct (float).
    """
    root = Path(path)
    if not root.exists():
        return {"error": f"Path does not exist: {path}"}
    if not root.is_dir():
        return {"error": f"Path must be a directory: {path}"}

    dict_path = _resolve_dict_path(root, language, output_dir)
    all_files = _collect_files(root, language)
    samples = _select_samples(all_files, sample_count)

    if not samples:
        return {"error": "No suitable sample files found for dictionary training"}

    samples_used, total_sample_bytes = _write_training_result(samples=samples, dict_path=dict_path)

    if samples_used == 0:
        return {"error": "All sample files exceeded size limit or were unreadable"}

    return _build_training_result(dict_path, samples_used, total_sample_bytes, language)


def _select_samples(files: List[Path], sample_count: int) -> List[Path]:
    """Select up to sample_count files within the per-sample size limit."""
    selected: List[Path] = []
    for fp in files:
        if len(selected) >= sample_count:
            break
        try:
            size = fp.stat().st_size
        except OSError:
            continue
        if size <= CondenseDictionaryDefaults.MAX_SAMPLE_SIZE_BYTES:
            selected.append(fp)
    return selected


def _copy_samples_to_tmpdir(samples: List[Path], tmp_dir: Path) -> tuple[int, int]:
    """Copy samples into tmp_dir, returning (samples_used, total_bytes)."""
    samples_used = 0
    total_bytes = 0
    for i, fp in enumerate(samples):
        try:
            content = fp.read_bytes()
        except OSError:
            continue
        if len(content) > CondenseDictionaryDefaults.MAX_SAMPLE_SIZE_BYTES:
            continue
        dest = tmp_dir / f"sample_{i}{fp.suffix}"
        dest.write_bytes(content)
        total_bytes += len(content)
        samples_used += 1
    return samples_used, total_bytes


def _run_zstd_train(tmp_dir: Path, dict_path: Path) -> None:
    """Invoke zstd --train; raise RuntimeError on failure."""
    cmd = [
        "zstd",
        "--train",
        f"--maxdict={CondenseDictionaryDefaults.DICT_SIZE_BYTES}",
        "-o",
        str(dict_path),
    ]
    cmd.extend(str(p) for p in tmp_dir.iterdir())
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=SubprocessDefaults.ZSTD_TRAIN_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        logger.error(
            "zstd_train_failed",
            returncode=result.returncode,
            stderr=result.stderr[: CondenseDefaults.MAX_FILE_SIZE_BYTES],
        )
        raise RuntimeError(f"zstd --train failed: {result.stderr.strip()}")


def _write_training_result(
    samples: List[Path],
    dict_path: Path,
) -> tuple[int, int]:
    """Run zstd --train on collected samples, return (samples_used, total_bytes)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        samples_used, total_bytes = _copy_samples_to_tmpdir(samples, tmp_dir)
        if samples_used == 0:
            return 0, 0
        _run_zstd_train(tmp_dir, dict_path)
    return samples_used, total_bytes


def _estimate_improvement(samples_used: int, total_bytes: int) -> float:
    """Estimate compression improvement from dictionary training.

    Per zstd documentation, dictionary training typically yields 10-30%
    better compression for small-to-medium files with consistent patterns.
    We use a conservative 15% estimate with a small-sample penalty.
    """
    if samples_used < SMALL_SAMPLE_THRESHOLD:
        return SMALL_SAMPLE_IMPROVEMENT_PCT  # Too few samples for reliable training
    if samples_used < MEDIUM_SAMPLE_THRESHOLD:
        return MEDIUM_SAMPLE_IMPROVEMENT_PCT  # Moderate sample set
    return LARGE_SAMPLE_IMPROVEMENT_PCT  # Full benefit for large, diverse sample sets
