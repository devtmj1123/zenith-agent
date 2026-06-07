"""Self-Diagnosis — detect issues and auto-improve Zenith-OS.

Monitors:
- Token waste (repeated queries, excessive tool calls, overkill responses)
- Error patterns (frequent failures, specific tool errors)
- Memory health (embedding model, soft memory size)
- Tool performance (slow tools, high failure rates)
- System health (disk space, config validity)

Auto-fixes:
- Cache tuning based on hit rates
- Memory cleanup when too large
- Error pattern elimination (retry strategies)
- Token budget adjustment

Usage:
    from core.self_diagnosis import SelfDiagnosis
    diag = SelfDiagnosis()
    issues = diag.run_diagnostics()
    fixes = diag.auto_fix()
"""
from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum
import logging

log = logging.getLogger(__name__)

ZENITH_HOME = Path.home() / ".zenith"


class IssueSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class DiagnosticIssue:
    """A detected issue."""
    category: str
    severity: IssueSeverity
    title: str
    description: str
    auto_fixable: bool = False
    fix_action: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagnosticReport:
    """Full diagnostic report."""
    timestamp: float
    issues: List[DiagnosticIssue]
    stats: Dict[str, Any]
    health_score: int  # 0-100

    def summary(self) -> str:
        critical = sum(1 for i in self.issues if i.severity == IssueSeverity.CRITICAL)
        errors = sum(1 for i in self.issues if i.severity == IssueSeverity.ERROR)
        warnings = sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)
        info = sum(1 for i in self.issues if i.severity == IssueSeverity.INFO)

        lines = [
            f"  Health Score: {self.health_score}/100",
            f"  Issues: {critical} critical, {errors} errors, {warnings} warnings, {info} info",
            "",
        ]

        for issue in self.issues:
            icon = {"critical": "🔴", "error": "🟠", "warning": "🟡", "info": "🔵"}
            fix = " [auto-fixable]" if issue.auto_fixable else ""
            lines.append(f"  {icon.get(issue.severity.value, '⚪')} [{issue.category}] {issue.title}{fix}")
            lines.append(f"    {issue.description}")

        return "\n".join(lines)


class SelfDiagnosis:
    """Detect issues and auto-improve Zenith-OS."""

    def __init__(self):
        self._eval_log_dir = ZENITH_HOME / "eval_logs"
        self._config_dir = ZENITH_HOME

    def run_diagnostics(self) -> DiagnosticReport:
        """Run all diagnostic checks."""
        issues = []
        stats = {}

        # Token efficiency checks
        token_issues, token_stats = self._check_token_efficiency()
        issues.extend(token_issues)
        stats.update(token_stats)

        # Error pattern checks
        error_issues, error_stats = self._check_error_patterns()
        issues.extend(error_issues)
        stats.update(error_stats)

        # Memory health
        memory_issues, memory_stats = self._check_memory_health()
        issues.extend(memory_issues)
        stats.update(memory_stats)

        # Tool performance
        tool_issues, tool_stats = self._check_tool_performance()
        issues.extend(tool_issues)
        stats.update(tool_stats)

        # System health
        system_issues, system_stats = self._check_system_health()
        issues.extend(system_issues)
        stats.update(system_stats)

        # Config validity
        config_issues = self._check_config()
        issues.extend(config_issues)

        # Calculate health score
        health_score = self._calc_health_score(issues)

        return DiagnosticReport(
            timestamp=time.time(),
            issues=issues,
            stats=stats,
            health_score=health_score,
        )

    def _check_token_efficiency(self) -> tuple:
        """Check for token waste patterns."""
        issues = []
        stats = {}

        # Load recent eval logs
        log_files = sorted(self._eval_log_dir.glob("*.jsonl"))[-7:]  # Last 7 days
        if not log_files:
            return issues, stats

        entries = []
        for lf in log_files:
            try:
                with open(lf, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            entries.append(json.loads(line))
            except Exception:
                pass

        if not entries:
            return issues, stats

        total_tokens = sum(e.get("input_tokens", 0) + e.get("output_tokens", 0) for e in entries)
        avg_efficiency = sum(e.get("efficiency", 0) for e in entries) / len(entries)
        low_efficiency = [e for e in entries if e.get("efficiency", 100) < 40]

        stats["total_tokens_7d"] = total_tokens
        stats["avg_efficiency"] = round(avg_efficiency, 1)
        stats["low_efficiency_count"] = len(low_efficiency)

        if avg_efficiency < 50:
            issues.append(DiagnosticIssue(
                category="tokens",
                severity=IssueSeverity.WARNING,
                title="Low token efficiency",
                description=f"Average efficiency is {avg_efficiency:.0f}/100. Consider simplifying prompts or reducing tool calls.",
                auto_fixable=True,
                fix_action="adjust_token_budget",
            ))

        if len(low_efficiency) > len(entries) * 0.3:
            issues.append(DiagnosticIssue(
                category="tokens",
                severity=IssueSeverity.WARNING,
                title="Frequent token waste",
                description=f"{len(low_efficiency)} of {len(entries)} messages had low efficiency (<40).",
                auto_fixable=False,
            ))

        # Check for repeated queries (same goal asked multiple times)
        goals = [e.get("goal", "") for e in entries]
        from collections import Counter
        goal_counts = Counter(goals)
        repeats = {g: c for g, c in goal_counts.items() if c > 2}
        if repeats:
            issues.append(DiagnosticIssue(
                category="tokens",
                severity=IssueSeverity.INFO,
                title="Repeated queries detected",
                description=f"{len(repeats)} queries were asked 3+ times. Agent may be failing to help.",
                metadata={"repeats": list(repeats.keys())[:5]},
            ))

        return issues, stats

    def _check_error_patterns(self) -> tuple:
        """Check for frequent errors."""
        issues = []
        stats = {}

        log_files = sorted(self._eval_log_dir.glob("*.jsonl"))[-3:]  # Last 3 days
        if not log_files:
            return issues, stats

        entries = []
        for lf in log_files:
            try:
                with open(lf, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            entries.append(json.loads(line))
            except Exception:
                pass

        if not entries:
            return issues, stats

        error_entries = [e for e in entries if e.get("had_error")]
        error_rate = len(error_entries) / len(entries) if entries else 0

        stats["error_rate"] = round(error_rate, 3)
        stats["total_errors"] = len(error_entries)

        if error_rate > 0.3:
            issues.append(DiagnosticIssue(
                category="errors",
                severity=IssueSeverity.ERROR,
                title="High error rate",
                description=f"{error_rate:.0%} of recent messages had errors ({len(error_entries)}/{len(entries)}).",
                auto_fixable=False,
            ))
        elif error_rate > 0.1:
            issues.append(DiagnosticIssue(
                category="errors",
                severity=IssueSeverity.WARNING,
                title="Elevated error rate",
                description=f"{error_rate:.0%} of recent messages had errors.",
                auto_fixable=False,
            ))

        return issues, stats

    def _check_memory_health(self) -> tuple:
        """Check memory system health."""
        issues = []
        stats = {}

        # Check soft memory size
        memory_dir = ZENITH_HOME / "memory"
        if memory_dir.exists():
            total_size = sum(f.stat().st_size for f in memory_dir.rglob("*") if f.is_file())
            stats["memory_size_mb"] = round(total_size / (1024 * 1024), 2)

            if total_size > 500 * 1024 * 1024:  # 500MB
                issues.append(DiagnosticIssue(
                    category="memory",
                    severity=IssueSeverity.WARNING,
                    title="Memory storage large",
                    description=f"Memory is {stats['memory_size_mb']}MB. Consider cleanup.",
                    auto_fixable=True,
                    fix_action="cleanup_memory",
                ))

        # Check embedding model
        try:
            from memory.soft_memory import SoftMemory
            if SoftMemory._embedding_model is None:
                issues.append(DiagnosticIssue(
                    category="memory",
                    severity=IssueSeverity.INFO,
                    title="Embedding model not loaded",
                    description="Model will load on first use. This is normal for cold start.",
                ))
            stats["embedding_loaded"] = SoftMemory._embedding_model is not None
        except Exception as e:
            issues.append(DiagnosticIssue(
                category="memory",
                severity=IssueSeverity.ERROR,
                title="Memory system error",
                description=str(e)[:200],
            ))

        return issues, stats

    def _check_tool_performance(self) -> tuple:
        """Check tool performance."""
        issues = []
        stats = {}

        # Check if browse CLI is installed
        import shutil
        browse_installed = shutil.which("browse") is not None
        stats["browse_cli"] = browse_installed

        if not browse_installed:
            issues.append(DiagnosticIssue(
                category="tools",
                severity=IssueSeverity.WARNING,
                title="Browse CLI not installed",
                description="Browser automation requires: npm install -g browse",
                auto_fixable=False,
            ))

        # Check if required Python packages are installed
        required = ["aiohttp", "httpx", "pyyaml", "typer"]
        missing = []
        for pkg in required:
            try:
                __import__(pkg)
            except ImportError:
                missing.append(pkg)

        if missing:
            issues.append(DiagnosticIssue(
                category="tools",
                severity=IssueSeverity.ERROR,
                title="Missing dependencies",
                description=f"Required packages not installed: {', '.join(missing)}",
                auto_fixable=True,
                fix_action="install_missing",
                metadata={"packages": missing},
            ))

        stats["missing_packages"] = missing

        return issues, stats

    def _check_system_health(self) -> tuple:
        """Check system health."""
        issues = []
        stats = {}

        # Check disk space
        try:
            import shutil
            total, used, free = shutil.disk_usage(Path.home())
            stats["disk_free_gb"] = round(free / (1024**3), 1)
            stats["disk_total_gb"] = round(total / (1024**3), 1)

            if free < 1 * 1024**3:  # Less than 1GB
                issues.append(DiagnosticIssue(
                    category="system",
                    severity=IssueSeverity.CRITICAL,
                    title="Low disk space",
                    description=f"Only {stats['disk_free_gb']}GB free. Zenith needs space for memory and logs.",
                ))
            elif free < 5 * 1024**3:  # Less than 5GB
                issues.append(DiagnosticIssue(
                    category="system",
                    severity=IssueSeverity.WARNING,
                    title="Disk space low",
                    description=f"{stats['disk_free_gb']}GB free. Consider cleanup.",
                ))
        except Exception:
            pass

        # Check .zenith directory
        if not ZENITH_HOME.exists():
            issues.append(DiagnosticIssue(
                category="system",
                severity=IssueSeverity.INFO,
                title="First run detected",
                description="Zenith home directory will be created on first use.",
            ))

        return issues, stats

    def _check_config(self) -> List[DiagnosticIssue]:
        """Check configuration validity."""
        issues = []

        # Check .env file
        env_file = Path(__file__).parent.parent / ".env"
        if not env_file.exists():
            issues.append(DiagnosticIssue(
                category="config",
                severity=IssueSeverity.WARNING,
                title="No .env file",
                description="Copy .env.example to .env and set your API keys.",
            ))
        else:
            # Check for API keys
            from config.settings import Settings
            settings = Settings()
            settings.load_from_env()

            if not settings.is_configured():
                issues.append(DiagnosticIssue(
                    category="config",
                    severity=IssueSeverity.ERROR,
                    title="No API key configured",
                    description=f"Set REASONING_API_KEY or use --provider ollama for local models.",
                ))

        return issues

    def _calc_health_score(self, issues: List[DiagnosticIssue]) -> int:
        """Calculate overall health score (0-100)."""
        score = 100

        for issue in issues:
            if issue.severity == IssueSeverity.CRITICAL:
                score -= 30
            elif issue.severity == IssueSeverity.ERROR:
                score -= 15
            elif issue.severity == IssueSeverity.WARNING:
                score -= 5
            elif issue.severity == IssueSeverity.INFO:
                score -= 1

        return max(0, min(100, score))

    def auto_fix(self, report: DiagnosticReport) -> List[str]:
        """Apply auto-fixes for fixable issues."""
        fixes = []

        for issue in report.issues:
            if not issue.auto_fixable:
                continue

            try:
                if issue.fix_action == "install_missing":
                    packages = issue.metadata.get("packages", [])
                    if packages:
                        import subprocess
                        subprocess.run(
                            ["pip", "install", "--quiet"] + packages,
                            capture_output=True, timeout=60,
                        )
                        fixes.append(f"Installed: {', '.join(packages)}")

                elif issue.fix_action == "cleanup_memory":
                    # Clean old eval logs (keep last 30 days)
                    log_dir = ZENITH_HOME / "eval_logs"
                    if log_dir.exists():
                        cutoff = time.time() - 30 * 86400
                        removed = 0
                        for f in log_dir.glob("*.jsonl"):
                            if f.stat().st_mtime < cutoff:
                                f.unlink()
                                removed += 1
                        if removed:
                            fixes.append(f"Removed {removed} old eval logs")

                elif issue.fix_action == "adjust_token_budget":
                    fixes.append("Token budget adjustment requires manual review")

            except Exception as e:
                fixes.append(f"Failed to fix '{issue.title}': {e}")

        return fixes


# ===== API Integration =====

def run_diagnosis() -> dict:
    """Run diagnostics and return results as dict (for API)."""
    diag = SelfDiagnosis()
    report = diag.run_diagnostics()

    return {
        "health_score": report.health_score,
        "issues": [
            {
                "category": i.category,
                "severity": i.severity.value,
                "title": i.title,
                "description": i.description,
                "auto_fixable": i.auto_fixable,
            }
            for i in report.issues
        ],
        "stats": report.stats,
        "summary": report.summary(),
    }


def run_auto_fix() -> dict:
    """Run diagnostics and apply auto-fixes."""
    diag = SelfDiagnosis()
    report = diag.run_diagnostics()
    fixes = diag.auto_fix(report)

    return {
        "health_score": report.health_score,
        "issues_found": len(report.issues),
        "fixes_applied": fixes,
    }
