"""OWASP ZAP integration for Dynamic Application Security Testing (DAST)."""

import asyncio
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from sast_mcp_server.models import ConfidenceLevel, Finding, SeverityLevel
from sast_mcp_server.scanners.base import BaseScanner

logger = logging.getLogger(__name__)


class ZapScanner(BaseScanner):
    """Scanner implementation for OWASP ZAP (Dynamic Application Security Testing).

    Unlike SAST tools, ZAP requires the target application to be running.
    This integration can orchestrate Docker Compose to spin up the target,
    run a ZAP scan against it, and then tear it down.
    """

    name = "zap"

    async def check_dependency(self) -> None:
        """Check if Docker is installed, as ZAP runs via Docker container."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError("Docker is not installed or accessible, required for ZAP.")
        except FileNotFoundError as err:
            raise RuntimeError("Docker is not installed or accessible, required for ZAP.") from err

    async def scan(
        self,
        target_path: str,
        min_severity: str = "LOW",
        min_confidence: str = "LOW",
        modified_files: set[str] | None = None,
        timeout: int = 600,
    ) -> list[Finding]:
        """Standard scan method is overridden for ZAP.

        Since ZAP is a DAST tool, it requires a URL, not just a file path.
        If called directly without parameters, it will fail unless we are orchestrating.
        Use `run_active_scan` tool instead.
        """
        raise NotImplementedError(
            "ZAP is a DAST scanner and cannot be run via standard static scan(). "
            "Use the `run_active_scan` tool to orchestrate a dynamic scan."
        )

    async def run_dynamic_scan(
        self,
        target_path: str,
        docker_compose_file: str,
        target_url: str,
        timeout: int = 1200
    ) -> list[Finding]:
        """Orchestrate a dynamic scan using ZAP and Docker Compose.

        1. Spins up the app via docker-compose
        2. Waits for the target URL to be responsive
        3. Runs the ZAP container baseline scan
        4. Tears down the app
        5. Parses results
        """
        compose_path = os.path.join(target_path, docker_compose_file)
        if not os.path.exists(compose_path):
            raise FileNotFoundError(f"Docker compose file not found: {compose_path}")

        report_filename = "zap_report.json"
        report_path = os.path.join(target_path, report_filename)

        # Clean up any old report
        if os.path.exists(report_path):
            os.remove(report_path)

        try:
            # 1. Spin up the target app
            logger.info(f"Starting target application via {docker_compose_file}")
            up_proc = await asyncio.create_subprocess_exec(
                "docker", "compose", "-f", compose_path, "up", "-d",
                cwd=target_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await up_proc.communicate()
            if up_proc.returncode != 0:
                raise RuntimeError("Failed to start target application via Docker Compose.")

            # 2. Wait for target URL to be responsive
            logger.info(f"Waiting for {target_url} to become responsive...")
            if not await self._wait_for_url(target_url, max_retries=30, delay=2):
                raise RuntimeError(f"Target application at {target_url} never became responsive.")

            # 3. Run ZAP scan via docker container
            logger.info(f"Running ZAP baseline scan against {target_url}")

            # Use host networking or standard docker routing depending on the target_url
            # For simplicity, if target is localhost, we need host networking
            is_local = "localhost" in target_url or "127.0.0.1" in target_url
            network_args = ["--network", "host"] if is_local else []

            # Map the local directory to /zap/wrk so ZAP can write the JSON report
            cmd = [
                "docker", "run", "--rm"
            ] + network_args + [
                "-v", f"{os.path.abspath(target_path)}:/zap/wrk/:rw",
                "-t", "ghcr.io/zaproxy/zaproxy:stable",
                "zap-baseline.py",
                "-t", target_url,
                "-J", report_filename,
                "-I" # Ignore failures so it always generates the report
            ]

            zap_proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=target_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                await asyncio.wait_for(zap_proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                zap_proc.kill()
                logger.error("ZAP scan timed out.")
                # Don't raise yet, we need to tear down

            # 5. Parse results
            if not os.path.exists(report_path):
                logger.warning("ZAP did not generate a report file.")
                return []

            with open(report_path, encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    logger.warning("ZAP produced invalid JSON output")
                    return []

            findings = []
            site = data.get("site", [])
            for s in site:
                alerts = s.get("alerts", [])
                for alert in alerts:
                    findings.append(self._parse_alert(alert, target_url))

            return findings

        finally:
            # 4. Tear down the app
            logger.info("Tearing down target application")
            down_proc = await asyncio.create_subprocess_exec(
                "docker", "compose", "-f", compose_path, "down",
                cwd=target_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await down_proc.communicate()

            # Clean up report file
            if os.path.exists(report_path):
                os.remove(report_path)

    async def _wait_for_url(self, url: str, max_retries: int = 30, delay: int = 2) -> bool:
        """Poll the URL until it returns a 200-399 status code."""
        for _ in range(max_retries):
            try:
                # Use urllib to avoid an extra async-http dependency for a healthcheck
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=2) as response:
                    if response.status < 400:
                        return True
            except (urllib.error.URLError, ConnectionError):
                pass

            await asyncio.sleep(delay)
        return False

    def _parse_alert(self, alert: dict[str, Any], target_url: str) -> Finding:
        """Parse a ZAP alert into the standard Finding model."""

        name = alert.get("name", "Unknown Vulnerability")
        desc = alert.get("desc", "")
        risk_code = str(alert.get("riskcode", "1"))
        confidence_code = str(alert.get("confidence", "1"))

        # ZAP Risk Codes: 0: Informational, 1: Low, 2: Medium, 3: High
        severity_map = {
            "3": SeverityLevel.HIGH,
            "2": SeverityLevel.MEDIUM,
            "1": SeverityLevel.LOW,
            "0": SeverityLevel.LOW,
        }
        severity = severity_map.get(risk_code, SeverityLevel.MEDIUM)

        # ZAP Confidence Codes: 1: Low, 2: Medium, 3: High, 4: Confirmed
        confidence_map = {
            "4": ConfidenceLevel.HIGH,
            "3": ConfidenceLevel.HIGH,
            "2": ConfidenceLevel.MEDIUM,
            "1": ConfidenceLevel.LOW,
        }
        confidence = confidence_map.get(confidence_code, ConfidenceLevel.LOW)

        solution = alert.get("solution", "")
        instances = alert.get("instances", [])

        # Build context from instances
        context = f"Target URL: {target_url}\n"
        context += f"Solution: {solution}\n\n"
        if instances:
            context += f"Found on {len(instances)} endpoints. First 3:\n"
            for inst in instances[:3]:
                uri = inst.get("uri", "")
                method = inst.get("method", "GET")
                param = inst.get("param", "")
                evidence = inst.get("evidence", "")

                context += f"- {method} {uri}"
                if param:
                    context += f" (Param: {param})"
                if evidence:
                    context += f" -> Evidence: {evidence[:50]}"
                context += "\n"

        finding = Finding(
            scanner=self.name,
            title=f"[DAST] {name}",
            message=desc,
            file="RUNTIME", # DAST doesn't map to files cleanly
            line_start=1,
            line_end=1,
            severity=severity,
            confidence=confidence,
            context=context,
            finding_hash=self.generate_hash("RUNTIME", name, str(instances)),
        )

        return finding
