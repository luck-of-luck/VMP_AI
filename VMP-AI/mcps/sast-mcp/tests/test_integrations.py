"""Tests for v0.6.0 dashboard integrations and AI patch generation."""

import base64
import gzip
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sast_mcp_server.cache import ScanCache
from sast_mcp_server.enrichment.patch_apply import apply_unified_diff
from sast_mcp_server.enrichment.patch_prompt import build_patch_prompt
from sast_mcp_server.integrations import IntegrationError
from sast_mcp_server.integrations._http import post_with_retry
from sast_mcp_server.integrations.defectdojo import upload_to_defectdojo
from sast_mcp_server.integrations.github import (
    comment_on_pull_request,
    upload_to_github,
)
from sast_mcp_server.integrations.gitlab import comment_on_merge_request
from sast_mcp_server.integrations.jira import create_jira_issue
from sast_mcp_server.integrations.slack import notify_slack
from sast_mcp_server.integrations.teams import notify_teams
from sast_mcp_server.models import ConfidenceLevel, Finding, SeverityLevel
from sast_mcp_server.scanners.base import BaseScanner


def _mock_async_client(status_code: int = 201, json_body: dict | None = None):
    """Build a mock that stands in for httpx.AsyncClient as a context manager.

    Returns (client_factory, post_mock) so tests can assert on the POST call.
    """
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body if json_body is not None else {}
    resp.text = json.dumps(json_body) if json_body is not None else ""

    post = AsyncMock(return_value=resp)
    client = AsyncMock()
    client.post = post
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    return (MagicMock(return_value=client), post)


def _write_sarif(tmp_path) -> str:
    sarif_file = tmp_path / "results.sarif"
    sarif_file.write_text('{"version": "2.1.0", "runs": []}', encoding="utf-8")
    return str(sarif_file)


# --------------------------------------------------------------------------
# DefectDojo
# --------------------------------------------------------------------------
class TestDefectDojo:
    @pytest.mark.asyncio
    async def test_missing_config_raises(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DEFECTDOJO_URL", raising=False)
        monkeypatch.delenv("DEFECTDOJO_API_KEY", raising=False)
        with pytest.raises(IntegrationError, match="not configured"):
            await upload_to_defectdojo(_write_sarif(tmp_path), engagement_id=7)

    @pytest.mark.asyncio
    async def test_successful_upload(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEFECTDOJO_URL", "https://dd.example.com/")
        monkeypatch.setenv("DEFECTDOJO_API_KEY", "secret-token")
        sarif_path = _write_sarif(tmp_path)

        factory, post = _mock_async_client(201, {"test": 42})
        with patch(
            "sast_mcp_server.integrations._http.httpx.AsyncClient", factory
        ):
            result = await upload_to_defectdojo(sarif_path, engagement_id=7)

        assert result == {"test": 42}
        # Endpoint and auth header are constructed correctly
        args, kwargs = post.call_args
        assert args[0] == "https://dd.example.com/api/v2/import-scan/"
        assert kwargs["headers"]["Authorization"] == "Token secret-token"
        assert kwargs["data"]["engagement"] == "7"
        assert kwargs["data"]["scan_type"] == "SARIF"
        assert "file" in kwargs["files"]

    @pytest.mark.asyncio
    async def test_error_status_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEFECTDOJO_URL", "https://dd.example.com")
        monkeypatch.setenv("DEFECTDOJO_API_KEY", "secret-token")
        sarif_path = _write_sarif(tmp_path)

        factory, _ = _mock_async_client(400, {"detail": "bad engagement"})
        with patch(
            "sast_mcp_server.integrations._http.httpx.AsyncClient", factory
        ), pytest.raises(IntegrationError, match="400"):
            await upload_to_defectdojo(sarif_path, engagement_id=999)

    @pytest.mark.asyncio
    async def test_missing_file_raises(self, monkeypatch):
        monkeypatch.setenv("DEFECTDOJO_URL", "https://dd.example.com")
        monkeypatch.setenv("DEFECTDOJO_API_KEY", "secret-token")
        with pytest.raises(IntegrationError, match="Could not read"):
            await upload_to_defectdojo("/nonexistent/results.sarif", engagement_id=1)


# --------------------------------------------------------------------------
# GitHub Code Scanning
# --------------------------------------------------------------------------
class TestGitHub:
    @pytest.mark.asyncio
    async def test_missing_token_raises(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(IntegrationError, match="not configured"):
            await upload_to_github(
                _write_sarif(tmp_path), "owner/repo", "abc123", "refs/heads/main"
            )

    @pytest.mark.asyncio
    async def test_invalid_repo_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_xxx")
        with pytest.raises(IntegrationError, match="Invalid repo"):
            await upload_to_github(
                _write_sarif(tmp_path), "not-a-repo", "abc123", "refs/heads/main"
            )

    @pytest.mark.asyncio
    async def test_successful_upload_encodes_sarif(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_xxx")
        sarif_path = _write_sarif(tmp_path)
        with open(sarif_path, "rb") as f:
            raw = f.read()

        factory, post = _mock_async_client(202, {"id": 1, "url": "https://api/x"})
        with patch(
            "sast_mcp_server.integrations._http.httpx.AsyncClient", factory
        ):
            result = await upload_to_github(
                sarif_path, "owner/repo", "deadbeefcafe", "refs/heads/main"
            )

        assert result["id"] == 1
        args, kwargs = post.call_args
        assert args[0] == "https://api.github.com/repos/owner/repo/code-scanning/sarifs"
        assert kwargs["headers"]["Authorization"] == "Bearer ghp_xxx"
        body = kwargs["json"]
        assert body["commit_sha"] == "deadbeefcafe"
        assert body["ref"] == "refs/heads/main"
        # The sarif field must be gzip-compressed then base64-encoded
        assert gzip.decompress(base64.b64decode(body["sarif"])) == raw

    @pytest.mark.asyncio
    async def test_error_status_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_xxx")
        sarif_path = _write_sarif(tmp_path)
        factory, _ = _mock_async_client(403, {"message": "forbidden"})
        with patch(
            "sast_mcp_server.integrations._http.httpx.AsyncClient", factory
        ), pytest.raises(IntegrationError, match="403"):
            await upload_to_github(sarif_path, "owner/repo", "abc", "refs/heads/main")


# --------------------------------------------------------------------------
# Patch prompt generation
# --------------------------------------------------------------------------
class TestPatchPrompt:
    def _cache_finding(self, tmp_path) -> str:
        """Write a vulnerable source file and cache a finding for it."""
        src = tmp_path / "app.py"
        src.write_text(
            "import yaml\n\n\ndef load(data):\n    return yaml.load(data)\n",
            encoding="utf-8",
        )
        finding = Finding(
            scanner="bandit",
            title="B506",
            message="Use of unsafe yaml.load",
            file="app.py",
            line_start=4,
            line_end=5,
            severity=SeverityLevel.HIGH,
            confidence=ConfidenceLevel.HIGH,
            context="def load(data):\n    return yaml.load(data)",
            language="python",
            finding_hash=BaseScanner.generate_hash("app.py", "B506", "yaml.load(data)"),
        )
        cache = ScanCache(str(tmp_path))
        cache.save_scan("bandit", [finding])
        return finding.finding_hash

    def test_prompt_contains_context(self, tmp_path):
        finding_hash = self._cache_finding(tmp_path)
        prompt = build_patch_prompt(str(tmp_path), finding_hash)

        assert "B506" in prompt
        assert "HIGH" in prompt
        assert "yaml.load(data)" in prompt
        assert "--- a/app.py" in prompt
        assert "unified diff" in prompt.lower()

    def test_unknown_hash_returns_error(self, tmp_path):
        ScanCache(str(tmp_path)).save_scan("bandit", [])
        prompt = build_patch_prompt(str(tmp_path), "deadbeef")
        assert "No cached finding" in prompt

    def test_missing_source_file_returns_error(self, tmp_path):
        finding = Finding(
            scanner="bandit",
            title="B506",
            message="x",
            file="gone.py",
            line_start=1,
            line_end=1,
            severity=SeverityLevel.HIGH,
            confidence=ConfidenceLevel.HIGH,
            context="",
            language="python",
            finding_hash="abc123",
        )
        ScanCache(str(tmp_path)).save_scan("bandit", [finding])
        prompt = build_patch_prompt(str(tmp_path), "abc123")
        assert "could not be found" in prompt


# --------------------------------------------------------------------------
# Patch application
# --------------------------------------------------------------------------
def _mock_git(returncode: int = 0, stderr: str = ""):
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(b"", stderr.encode("utf-8")))
    proc.returncode = returncode
    proc.kill = MagicMock()
    return proc


class TestApplyPatch:
    @pytest.mark.asyncio
    async def test_empty_patch_short_circuits(self, tmp_path):
        success, detail = await apply_unified_diff(str(tmp_path), "   \n")
        assert success is False
        assert "Empty patch" in detail

    @pytest.mark.asyncio
    async def test_successful_apply(self, tmp_path):
        proc = _mock_git(returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            success, detail = await apply_unified_diff(
                str(tmp_path), "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
            )
        assert success is True
        assert "applied" in detail

    @pytest.mark.asyncio
    async def test_check_only(self, tmp_path):
        proc = _mock_git(returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc) as exec_mock:
            success, detail = await apply_unified_diff(
                str(tmp_path), "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n", check_only=True
            )
        assert success is True
        assert "validated" in detail
        # --check must be present in the git invocation
        assert "--check" in exec_mock.call_args.args

    @pytest.mark.asyncio
    async def test_failed_apply_returns_stderr(self, tmp_path):
        proc = _mock_git(returncode=1, stderr="error: patch does not apply")
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            success, detail = await apply_unified_diff(
                str(tmp_path), "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
            )
        assert success is False
        assert "does not apply" in detail


# --------------------------------------------------------------------------
# v0.7.0 integrations
# --------------------------------------------------------------------------
class TestGitLab:
    @pytest.mark.asyncio
    async def test_missing_token_raises(self, monkeypatch):
        monkeypatch.delenv("GITLAB_TOKEN", raising=False)
        with pytest.raises(IntegrationError, match="not configured"):
            await comment_on_merge_request("group/proj", 3, "hi")

    @pytest.mark.asyncio
    async def test_comment_posts_note(self, monkeypatch):
        monkeypatch.setenv("GITLAB_TOKEN", "glpat")
        factory, post = _mock_async_client(201, {"id": 5})
        with patch("sast_mcp_server.integrations._http.httpx.AsyncClient", factory):
            result = await comment_on_merge_request("group/proj", 7, "summary")
        assert result["id"] == 5
        args, kwargs = post.call_args
        assert args[0].endswith("/merge_requests/7/notes")
        assert kwargs["headers"]["PRIVATE-TOKEN"] == "glpat"
        assert kwargs["json"]["body"] == "summary"


class TestGitHubPrComment:
    @pytest.mark.asyncio
    async def test_comment(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "ghp")
        factory, post = _mock_async_client(201, {"id": 9, "html_url": "https://gh/c/9"})
        with patch("sast_mcp_server.integrations._http.httpx.AsyncClient", factory):
            result = await comment_on_pull_request("owner/repo", 12, "body")
        assert result["id"] == 9
        args, kwargs = post.call_args
        assert args[0].endswith("/repos/owner/repo/issues/12/comments")
        assert kwargs["json"]["body"] == "body"


class TestSlackTeams:
    @pytest.mark.asyncio
    async def test_slack_missing_webhook(self, monkeypatch):
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
        with pytest.raises(IntegrationError, match="not configured"):
            await notify_slack("hi")

    @pytest.mark.asyncio
    async def test_slack_posts(self, monkeypatch):
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")
        factory, post = _mock_async_client(200, {})
        with patch("sast_mcp_server.integrations._http.httpx.AsyncClient", factory):
            await notify_slack("alert")
        args, kwargs = post.call_args
        assert args[0] == "https://hooks.slack.com/x"
        assert kwargs["json"]["text"] == "alert"

    @pytest.mark.asyncio
    async def test_teams_posts_card(self, monkeypatch):
        monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://teams/x")
        factory, post = _mock_async_client(200, {})
        with patch("sast_mcp_server.integrations._http.httpx.AsyncClient", factory):
            await notify_teams("alert", title="T")
        _, kwargs = post.call_args
        assert kwargs["json"]["@type"] == "MessageCard"
        assert kwargs["json"]["text"] == "alert"


class TestJira:
    @pytest.mark.asyncio
    async def test_missing_config(self, monkeypatch):
        for var in ("JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"):
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(IntegrationError, match="not configured"):
            await create_jira_issue("SEC", "s", "d")

    @pytest.mark.asyncio
    async def test_creates_issue(self, monkeypatch):
        monkeypatch.setenv("JIRA_URL", "https://x.atlassian.net")
        monkeypatch.setenv("JIRA_EMAIL", "me@x.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "tok")
        factory, post = _mock_async_client(201, {"key": "SEC-1"})
        with patch("sast_mcp_server.integrations._http.httpx.AsyncClient", factory):
            result = await create_jira_issue("SEC", "Summary", "Desc")
        assert result["key"] == "SEC-1"
        args, kwargs = post.call_args
        assert args[0].endswith("/rest/api/3/issue")
        assert kwargs["headers"]["Authorization"].startswith("Basic ")
        assert kwargs["json"]["fields"]["project"]["key"] == "SEC"


# --------------------------------------------------------------------------
# Shared HTTP retry/backoff
# --------------------------------------------------------------------------
def _multi_response_client(statuses):
    """Build a client whose post() yields the given status codes in order."""
    responses = []
    for code in statuses:
        r = MagicMock()
        r.status_code = code
        r.json.return_value = {"ok": code < 400}
        r.text = ""
        responses.append(r)
    post = AsyncMock(side_effect=responses)
    client = AsyncMock()
    client.post = post
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=client), post


class TestRetry:
    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self):
        factory, post = _multi_response_client([503, 503, 200])
        with patch("sast_mcp_server.integrations._http.httpx.AsyncClient", factory), \
                patch("asyncio.sleep", new=AsyncMock()):
            resp = await post_with_retry(
                "https://x", service="Test", retries=3
            )
        assert resp.status_code == 200
        assert post.call_count == 3

    @pytest.mark.asyncio
    async def test_4xx_not_retried(self):
        factory, post = _multi_response_client([400, 200])
        with patch("sast_mcp_server.integrations._http.httpx.AsyncClient", factory), \
                patch("asyncio.sleep", new=AsyncMock()), \
                pytest.raises(IntegrationError, match="400"):
            await post_with_retry("https://x", service="Test", retries=3)
        assert post.call_count == 1

    @pytest.mark.asyncio
    async def test_exhausts_retries(self):
        factory, post = _multi_response_client([503, 503, 503])
        with patch("sast_mcp_server.integrations._http.httpx.AsyncClient", factory), \
                patch("asyncio.sleep", new=AsyncMock()), \
                pytest.raises(IntegrationError):
            await post_with_retry("https://x", service="Test", retries=2)
        assert post.call_count == 3  # initial + 2 retries
