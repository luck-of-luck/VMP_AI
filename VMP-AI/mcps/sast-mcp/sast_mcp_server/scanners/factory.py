"""Scanner factory — maps scanner names to their implementations."""

import logging

from sast_mcp_server.scanners.bandit import BanditScanner
from sast_mcp_server.scanners.base import BaseScanner
from sast_mcp_server.scanners.bearer import BearerScanner
from sast_mcp_server.scanners.checkov import CheckovScanner
from sast_mcp_server.scanners.codeql import CodeQLScanner
from sast_mcp_server.scanners.gitleaks import GitleaksScanner
from sast_mcp_server.scanners.grype import GrypeScanner
from sast_mcp_server.scanners.njsscan import NjsscanScanner
from sast_mcp_server.scanners.osv_scanner import OsvScanner
from sast_mcp_server.scanners.semgrep import SemgrepScanner
from sast_mcp_server.scanners.trivy import TrivyScanner
from sast_mcp_server.scanners.zap import ZapScanner

logger = logging.getLogger(__name__)

# Registry of all available scanners
_SCANNER_REGISTRY: dict[str, type[BaseScanner]] = {
    "bandit": BanditScanner,
    "njsscan": NjsscanScanner,
    "bearer": BearerScanner,
    "semgrep": SemgrepScanner,
    "trivy": TrivyScanner,
    "codeql": CodeQLScanner,
    "checkov": CheckovScanner,
    "gitleaks": GitleaksScanner,
    "grype": GrypeScanner,
    "osv-scanner": OsvScanner,
    "zap": ZapScanner,
}

# Metadata for the list_scanners tool
SCANNER_INFO: dict[str, dict[str, str]] = {
    "bandit": {
        "description": "Python security linter (finds common security issues in Python code)",
        "languages": "Python",
        "install": "pip install bandit",
    },
    "njsscan": {
        "description": "Node.js/JavaScript static security analysis tool",
        "languages": "JavaScript, TypeScript, Node.js",
        "install": "pip install njsscan",
    },
    "bearer": {
        "description": "Multi-language SAST with data-flow analysis",
        "languages": "Python, JavaScript, TypeScript, Ruby, Java, Go, PHP",
        "install": "https://docs.bearer.com/installation/",
    },
    "semgrep": {
        "description": "Multi-language SAST with community rule registry (30+ languages)",
        "languages": (
            "Python, JavaScript, TypeScript, Java, Go, Ruby, C, C++, C#, "
            "Rust, Kotlin, Swift, PHP, Scala, and more"
        ),
        "install": "pip install semgrep",
    },
    "trivy": {
        "description": "All-in-one scanner for vulnerabilities, secrets, and IaC misconfigurations",
        "languages": "All (dependency CVEs), IaC (Terraform, K8s, Docker, CloudFormation)",
        "install": "https://aquasecurity.github.io/trivy/latest/getting-started/installation/",
    },
    "codeql": {
        "description": "Deep semantic SAST with data-flow and taint tracking (by GitHub)",
        "languages": "Python, JavaScript, TypeScript, Java, C/C++, C#, Go, Ruby, Swift",
        "install": "https://github.com/github/codeql-cli-binaries/releases",
    },
    "checkov": {
        "description": "Infrastructure-as-Code policy checks.",
        "languages": "Terraform, CloudFormation, Kubernetes, Docker",
        "install": "pip install checkov",
    },
    "gitleaks": {
        "description": "Deep secret scanning in git history.",
        "languages": "All",
        "install": "brew install gitleaks / wget https://github.com/gitleaks/gitleaks/releases/...",
    },
    "grype": {
        "description": "Vulnerability scanner for images, filesystems, and SBOMs (Anchore).",
        "languages": "Containers, OS packages, language deps (lockfiles, SBOMs)",
        "install": "https://github.com/anchore/grype#installation",
    },
    "osv-scanner": {
        "description": "Software Composition Analysis against OSV database.",
        "languages": "Multiple (lockfiles, sboms)",
        "install": "go install github.com/google/osv-scanner/cmd/osv-scanner@v1",
    },
    "zap": {
        "description": "Dynamic Application Security Testing (DAST) via Docker.",
        "languages": "RUNTIME",
        "install": "docker pull ghcr.io/zaproxy/zaproxy:stable",
    },
}


class ScannerFactory:
    """Factory for creating scanner instances."""

    @staticmethod
    def get_scanner(name: str) -> BaseScanner:
        """Create and return a scanner instance by name.

        Args:
            name: Scanner name (case-insensitive). One of: bandit, njsscan, bearer.

        Returns:
            An instance of the requested scanner.

        Raises:
            ValueError: If the scanner name is not recognized.
        """
        name_lower = name.lower().strip()
        if name_lower not in _SCANNER_REGISTRY:
            supported = ", ".join(sorted(_SCANNER_REGISTRY.keys()))
            raise ValueError(
                f"Scanner '{name}' is not supported. "
                f"Supported scanners: {supported}"
            )
        return _SCANNER_REGISTRY[name_lower]()

    @staticmethod
    def list_scanners() -> list[str]:
        """Return list of all registered scanner names."""
        return sorted(_SCANNER_REGISTRY.keys())
