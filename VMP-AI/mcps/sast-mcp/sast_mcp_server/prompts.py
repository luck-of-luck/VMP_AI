"""MCP Prompts — pre-built security workflow templates for AI agents.

These prompt templates guide agents through common security workflows,
functioning as reusable "Standard Operating Procedures" for security scanning.
"""

import logging

from sast_mcp_server.reporting.compliance import (
    cis_benchmark_categories,
    owasp_top_10_categories,
    pci_dss_categories,
    sans_top_25_categories,
)

logger = logging.getLogger(__name__)


def register_prompts(mcp) -> None:
    """Register all MCP prompts on the given FastMCP server instance.

    Args:
        mcp: The FastMCP server instance.
    """

    @mcp.prompt()
    def security_review(target_path: str, focus: str = "all") -> str:
        """Comprehensive security review workflow for a codebase.

        Guides the agent through a full security assessment:
        scanning, baseline comparison, fix suggestions, and summary.
        """
        focus_instruction = ""
        if focus != "all":
            focus_instruction = (
                f"\n- Focus specifically on {focus}-related vulnerabilities"
            )

        intro = (
            "You are performing a comprehensive security review "
            f"of the codebase at: {target_path}"
        )

        return f"""{intro}

Follow these steps in order:

1. **Discover installed scanners**
   Call `list_scanners` to see which SAST tools are available.

2. **Run a comprehensive scan**
   Call `scan_all` with `target_path="{target_path}"` and `min_severity="MEDIUM"`.
   This will run all installed scanners in parallel with deduplication.

3. **Check for baseline comparison**
   Call `compare_baseline` with `target_path="{target_path}"` and `tag="latest"`.
   If a baseline exists, highlight NEW findings that weren't in the previous scan.
   If no baseline exists, note this is the first scan.

4. **Analyze findings**
   For each HIGH or CRITICAL finding:{focus_instruction}
   - Explain the vulnerability in plain language
   - Show the vulnerable code from the context
   - Provide a concrete code fix
   - Assess the exploitability and business impact

5. **Save baseline**
   Call `save_baseline` with `target_path="{target_path}"` and `tag="latest"`.

6. **Generate summary**
   Provide an executive summary including:
   - Total findings by severity
   - Top 3 most critical issues
   - Recommended remediation priority
   - Overall security posture assessment (Good / Needs Attention / Critical)
"""

    @mcp.prompt()
    def fix_vulnerability(finding_hash: str, target_path: str) -> str:
        """Remediation advisor for a specific vulnerability finding.

        Guides the agent through understanding and fixing a specific finding.
        """
        intro = (
            "You are a security remediation advisor. "
            f"Fix the vulnerability identified by hash: {finding_hash}"
        )

        return f"""{intro}

Follow these steps:

1. **Load the finding**
   The finding hash is `{finding_hash}` in the project at `{target_path}`.
   If available, check the cached scan results to find details about this finding.

2. **Understand the vulnerability**
   - Read the source code file at the reported location
   - Understand the enclosing function context
   - Identify the root cause (missing validation, unsafe API usage, etc.)
   - Look up the CWE or OWASP category if the finding title contains one

3. **Generate the fix**
   - Call `generate_fix_prompt(target_path="{target_path}", finding_hash="{finding_hash}")`
     to get a ready-to-use prompt containing the vulnerable code and context.
   - Produce a minimal unified diff that resolves the vulnerability while
     maintaining the original functionality.

4. **Apply and verify the fix**
   - Call `apply_patch(target_path="{target_path}", patch=<diff>, check_only=True)`
     to confirm the diff applies cleanly, then run it again with
     `check_only=False` to write the change.
   - Explain why the fix resolves the issue and whether it could introduce
     regressions; suggest a unit test that guards against the vulnerability.

5. **Report**
   - Show the before/after diff of the changes
   - Confirm the vulnerability is resolved
   - Suggest if `ignore_vulnerability` should be used instead (for false positives)
"""

    @mcp.prompt()
    def pr_security_check(target_path: str) -> str:
        """Pull request security gate — scan only changed files.

        Guides the agent through a focused PR security review.
        """
        intro = (
            "You are a security reviewer checking a pull request "
            f"for the project at: {target_path}"
        )

        return f"""{intro}

Follow these steps:

1. **Scan changed files only**
   Call `scan_vulnerabilities` (or `scan_all`) with:
   - `target_path="{target_path}"`
   - `git_diff_only=True`
   - `min_severity="LOW"` (catch everything in the diff)

2. **Compare against baseline**
   Call `compare_baseline` with `target_path="{target_path}"` and `tag="main"`.
   Focus on the `new_findings` — these are vulnerabilities introduced by this PR.

3. **Evaluate severity gate**
   - If there are NEW **CRITICAL** or **HIGH** findings: recommend BLOCKING the PR
   - If there are only NEW **MEDIUM** or **LOW** findings: recommend review with advisory
   - If no new findings: approve from a security perspective

4. **Generate PR comment**
   Format your response as a PR review comment including:
   - ✅ or ❌ Security check status
   - Number of new vs. fixed findings
   - Details of any blocking findings with code context
   - Suggested fixes for each new finding

5. **Export for CI/CD (optional)**
   If the user wants CI integration, call `export_sarif` to generate a SARIF file
   that can be uploaded to GitHub Code Scanning.
"""

    @mcp.prompt()
    def compliance_report(
        target_path: str, standard: str = "owasp-top-10"
    ) -> str:
        """Generate a compliance report against a security standard.

        Supports: owasp-top-10, sans-top-25, pci-dss, cis-benchmark
        """
        standard_mappings = {
            "owasp-top-10": owasp_top_10_categories(),
            "sans-top-25": sans_top_25_categories(),
            "pci-dss": pci_dss_categories(),
            "cis-benchmark": cis_benchmark_categories(),
        }

        categories = standard_mappings.get(standard, standard_mappings["owasp-top-10"])
        categories_text = "\n".join(f"   - {cat}" for cat in categories)

        return f"""You are generating a compliance report for: {target_path}
Standard: **{standard.upper()}**

Follow these steps:

1. **Run comprehensive scan**
   Call `scan_all` with `target_path="{target_path}"` and `min_severity="LOW"`.

2. **Map findings to {standard.upper()} categories**
   For each finding, determine which category it falls under:
{categories_text}

3. **Calculate compliance score**
   - Count how many categories have zero findings (compliant)
   - Count how many have findings (non-compliant)
   - Score = (compliant categories / total categories) × 100

4. **Generate report**
   Structure the report as:

   ## {standard.upper()} Compliance Report
   **Project:** {target_path}
   **Date:** [current date]
   **Overall Score:** [X]%

   ### Category Breakdown
   For each category:
   - Status: ✅ Compliant / ❌ Non-compliant
   - Finding count
   - Highest severity
   - Brief description of issues found

   ### Executive Summary
   - Key non-compliant areas
   - Recommended remediation priority
   - Estimated effort to reach full compliance

   ### Detailed Findings
   Group all findings by their mapped category.
"""


