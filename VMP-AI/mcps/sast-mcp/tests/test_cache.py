"""Tests for the cache module."""

import time

import pytest

from sast_mcp_server.cache import ScanCache
from sast_mcp_server.models import ConfidenceLevel, Finding, SeverityLevel


@pytest.fixture
def mock_findings():
    """Create a few mock findings for testing."""
    return [
        Finding(
            scanner="test_scanner",
            title="High Vuln",
            message="Test High",
            file="test.py",
            line_start=1,
            line_end=1,
            severity=SeverityLevel.HIGH,
            confidence=ConfidenceLevel.HIGH,
            context="code1",
            finding_hash="hash1",
        ),
        Finding(
            scanner="test_scanner",
            title="Low Vuln",
            message="Test Low",
            file="test2.py",
            line_start=2,
            line_end=2,
            severity=SeverityLevel.LOW,
            confidence=ConfidenceLevel.LOW,
            context="code2",
            finding_hash="hash2",
        ),
    ]


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Fixture for a temporary target path with cache cleanup."""
    target_path = str(tmp_path)
    yield target_path
    # Cleanup done automatically by pytest tmp_path


def test_save_and_load_latest(temp_cache_dir, mock_findings):
    cache = ScanCache(temp_cache_dir)

    # Save first scan (kept only as the older entry; we assert load_latest skips it)
    cache.save_scan("test_scanner", mock_findings[:1])

    # Wait a bit so timestamp is different
    time.sleep(0.1)

    # Save second scan
    cache_id2 = cache.save_scan("test_scanner", mock_findings)

    # Load latest should be the second one
    latest = cache.load_latest("test_scanner")
    assert latest is not None
    assert latest.cache_id == cache_id2
    assert latest.finding_count == 2
    assert len(latest.findings) == 2
    assert latest.findings[0].title == "High Vuln"
    assert latest.findings[1].title == "Low Vuln"


def test_save_and_load_by_tag(temp_cache_dir, mock_findings):
    cache = ScanCache(temp_cache_dir)

    # Save with tag
    cache.save_scan("test_scanner", mock_findings, tag="main-branch")

    # Load by tag
    tagged = cache.load_by_tag("test_scanner", "main-branch")
    assert tagged is not None
    assert tagged.tag == "main-branch"
    assert tagged.finding_count == 2

    # Non-existent tag
    assert cache.load_by_tag("test_scanner", "non-existent") is None


def test_list_scans(temp_cache_dir, mock_findings):
    cache = ScanCache(temp_cache_dir)

    cache.save_scan("scanner1", mock_findings)
    time.sleep(0.1)
    cache.save_scan("scanner2", mock_findings, tag="prod")

    all_scans = cache.list_scans()
    assert len(all_scans) == 3 # 2 timestamped + 1 tagged

    s1_scans = cache.list_scans("scanner1")
    assert len(s1_scans) == 1
    assert s1_scans[0].scanner == "scanner1"

    s2_scans = cache.list_scans("scanner2")
    assert len(s2_scans) == 2 # 1 timestamped + 1 tagged


def test_compare_baseline(temp_cache_dir, mock_findings):
    cache = ScanCache(temp_cache_dir)

    # Baseline: hash1 and hash2
    cache.save_scan("test_scanner", mock_findings, tag="base")
    baseline = cache.load_by_tag("test_scanner", "base")
    assert baseline is not None

    # Current: hash2 (unchanged), hash3 (new)
    # hash1 is fixed
    new_finding = Finding(
        scanner="test_scanner",
        title="New Medium",
        message="Test Med",
        file="test3.py",
        line_start=3,
        line_end=3,
        severity=SeverityLevel.MEDIUM,
        confidence=ConfidenceLevel.MEDIUM,
        context="code3",
        finding_hash="hash3",
    )
    current_findings = [mock_findings[1], new_finding]

    diff = cache.compare(baseline, current_findings)

    assert diff.baseline_total == 2
    assert diff.current_total == 2

    assert len(diff.new_findings) == 1
    assert diff.new_findings[0].finding_hash == "hash3"

    assert len(diff.fixed_findings) == 1
    assert diff.fixed_findings[0].finding_hash == "hash1"

    assert len(diff.unchanged_findings) == 1
    assert diff.unchanged_findings[0].finding_hash == "hash2"

    # Trend checks
    assert diff.severity_trend["HIGH"]["delta"] == -1  # fixed hash1
    assert diff.severity_trend["MEDIUM"]["delta"] == 1 # added hash3
    assert diff.severity_trend["LOW"]["delta"] == 0    # hash2 unchanged


def test_cleanup_expired(temp_cache_dir, mock_findings):
    cache = ScanCache(temp_cache_dir)

    cache.save_scan("test_scanner", mock_findings)
    cache.save_scan("test_scanner", mock_findings, tag="keep_me")

    assert len(cache.list_scans()) == 2

    # Set a TTL of -1 so everything is expired
    removed = cache.cleanup_expired(ttl=-1)

    assert removed == 1 # Should remove the timestamped one

    scans_left = cache.list_scans()
    assert len(scans_left) == 1
    assert scans_left[0].tag == "keep_me" # Tagged shouldn't be removed
