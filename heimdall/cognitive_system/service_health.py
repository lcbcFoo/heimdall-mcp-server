"""
Service health checking for monitoring service container integration.

This module provides health check functionality for the monitoring service
that integrates with container orchestration health checks and monitoring systems.
"""

import os
import time
from pathlib import Path
from typing import Any

import psutil
from loguru import logger

from cognitive_memory.core.config import CognitiveConfig


class HealthCheckResult:
    """Individual health check result."""

    def __init__(
        self,
        name: str,
        status: str,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        self.name = name
        self.status = status  # 'pass', 'warn', 'fail'
        self.message = message
        self.details = details or {}
        self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class ServiceHealthChecker:
    """
    Health checker for monitoring service in container environments.

    Provides comprehensive health validation for container orchestration,
    including service status, resource usage, and dependency validation.
    """

    PID_FILE = "/tmp/monitoring.pid"
    MEMORY_THRESHOLD_MB = 800
    CPU_THRESHOLD_PERCENT = 80

    def __init__(self, config: CognitiveConfig | None = None):
        """
        Initialize health checker.

        Args:
            config: Optional cognitive configuration, defaults to environment-based config
        """
        self.config = config or CognitiveConfig.from_env()

    def check_all(self) -> dict[str, Any]:
        """
        Perform comprehensive health check.

        Returns:
            Dictionary containing overall health status and individual check results
        """
        checks = []
        overall_status = "healthy"

        # Run individual health checks
        check_methods = [
            self._check_service_running,
            self._check_pid_file,
            self._check_configuration,
            self._check_target_path,
            self._check_dependencies,
            self._check_resource_usage,
            self._check_permissions,
        ]

        for check_method in check_methods:
            try:
                result = check_method()
                checks.append(result)

                # Update overall status based on individual check results
                if result.status == "fail":
                    overall_status = "unhealthy"
                elif result.status == "warn" and overall_status == "healthy":
                    overall_status = "warning"

            except Exception as e:
                logger.error(f"Health check {check_method.__name__} failed: {e}")
                checks.append(
                    HealthCheckResult(
                        name=check_method.__name__.replace("_check_", ""),
                        status="fail",
                        message=f"Health check failed: {e}",
                    )
                )
                overall_status = "unhealthy"

        return {
            "status": overall_status,
            "checks": [check.to_dict() for check in checks],
            "timestamp": time.time(),
            "summary": self._generate_summary(checks),
        }

    def _check_service_running(self) -> HealthCheckResult:
        """Check if monitoring service is running."""
        pid_file = Path(self.PID_FILE)

        if not pid_file.exists():
            return HealthCheckResult(
                "service_running", "fail", "Monitoring service PID file not found"
            )

        try:
            with open(pid_file) as f:
                pid = int(f.read().strip())

            if not psutil.pid_exists(pid):
                return HealthCheckResult(
                    "service_running",
                    "fail",
                    f"Monitoring service process not found (PID: {pid})",
                )

            # Check if process is actually our monitoring service
            try:
                process = psutil.Process(pid)
                cmdline = " ".join(process.cmdline())
                if "monitoring_service" not in cmdline:
                    return HealthCheckResult(
                        "service_running",
                        "warn",
                        f"PID {pid} exists but may not be monitoring service",
                    )
            except psutil.AccessDenied:
                # Can't read process details, but PID exists
                pass

            return HealthCheckResult(
                "service_running",
                "pass",
                f"Monitoring service is running (PID: {pid})",
                {"pid": pid},
            )

        except (ValueError, FileNotFoundError, PermissionError) as e:
            return HealthCheckResult(
                "service_running", "fail", f"Error reading PID file: {e}"
            )

    def _check_pid_file(self) -> HealthCheckResult:
        """Check PID file validity."""
        pid_file = Path(self.PID_FILE)

        if not pid_file.exists():
            return HealthCheckResult("pid_file", "fail", "PID file does not exist")

        try:
            stat = pid_file.stat()
            age_seconds = time.time() - stat.st_mtime

            # PID file should be recent (updated within last minute)
            if age_seconds > 300:  # 5 minutes
                return HealthCheckResult(
                    "pid_file",
                    "warn",
                    f"PID file is old ({age_seconds:.0f} seconds)",
                    {"age_seconds": age_seconds},
                )

            return HealthCheckResult(
                "pid_file",
                "pass",
                f"PID file is recent ({age_seconds:.0f} seconds old)",
                {"age_seconds": age_seconds, "path": str(pid_file)},
            )

        except Exception as e:
            return HealthCheckResult(
                "pid_file", "fail", f"Error checking PID file: {e}"
            )

    def _check_configuration(self) -> HealthCheckResult:
        """Check monitoring configuration validity."""
        try:
            # Check monitoring enabled
            if not self.config.monitoring_enabled:
                return HealthCheckResult(
                    "configuration", "fail", "Monitoring is disabled in configuration"
                )

            # Check required environment variables
            required_vars = ["MONITORING_TARGET_PATH"]
            missing_vars = []

            for var in required_vars:
                if not os.getenv(var):
                    missing_vars.append(var)

            if missing_vars:
                return HealthCheckResult(
                    "configuration",
                    "fail",
                    f"Missing required environment variables: {', '.join(missing_vars)}",
                )

            # Check configuration values
            details = {
                "monitoring_enabled": self.config.monitoring_enabled,
                "monitoring_interval_seconds": self.config.monitoring_interval_seconds,
                "sync_enabled": self.config.sync_enabled,
                "target_path": os.getenv("MONITORING_TARGET_PATH"),
            }

            return HealthCheckResult(
                "configuration", "pass", "Configuration is valid", details
            )

        except Exception as e:
            return HealthCheckResult(
                "configuration", "fail", f"Configuration check failed: {e}"
            )

    def _check_target_path(self) -> HealthCheckResult:
        """Check target path accessibility."""
        target_path = os.getenv("MONITORING_TARGET_PATH")

        if not target_path:
            return HealthCheckResult(
                "target_path", "fail", "MONITORING_TARGET_PATH not set"
            )

        path_obj = Path(target_path)

        if not path_obj.exists():
            return HealthCheckResult(
                "target_path", "fail", f"Target path does not exist: {target_path}"
            )

        if not path_obj.is_dir():
            return HealthCheckResult(
                "target_path", "fail", f"Target path is not a directory: {target_path}"
            )

        if not os.access(target_path, os.R_OK):
            return HealthCheckResult(
                "target_path",
                "fail",
                f"No read permission for target path: {target_path}",
            )

        # Count files that would be monitored
        try:
            markdown_files = list(path_obj.rglob("*.md"))
            file_count = len(markdown_files)

            details = {
                "path": target_path,
                "exists": True,
                "readable": True,
                "markdown_files": file_count,
            }

            return HealthCheckResult(
                "target_path",
                "pass",
                f"Target path is accessible with {file_count} markdown files",
                details,
            )

        except Exception as e:
            return HealthCheckResult(
                "target_path",
                "warn",
                f"Target path accessible but error counting files: {e}",
                {"path": target_path, "error": str(e)},
            )

    def _check_dependencies(self) -> HealthCheckResult:
        """Check external dependencies (Qdrant, etc.)."""
        try:
            # Check Qdrant connection
            qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")

            # Try to import qdrant client and test connection
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.http.exceptions import UnexpectedResponse

                client = QdrantClient(url=qdrant_url)

                # Simple health check
                collections = client.get_collections()

                return HealthCheckResult(
                    "dependencies",
                    "pass",
                    f"Qdrant connection successful ({len(collections.collections)} collections)",
                    {
                        "qdrant_url": qdrant_url,
                        "collections_count": len(collections.collections),
                    },
                )

            except UnexpectedResponse as e:
                return HealthCheckResult(
                    "dependencies", "fail", f"Qdrant connection failed: {e}"
                )
            except Exception as e:
                return HealthCheckResult(
                    "dependencies", "warn", f"Qdrant connection uncertain: {e}"
                )

        except ImportError:
            return HealthCheckResult(
                "dependencies", "fail", "Qdrant client not available"
            )

    def _check_resource_usage(self) -> HealthCheckResult:
        """Check system resource usage."""
        try:
            pid_file = Path(self.PID_FILE)

            if not pid_file.exists():
                return HealthCheckResult(
                    "resource_usage",
                    "warn",
                    "Cannot check resources - service not running",
                )

            with open(pid_file) as f:
                pid = int(f.read().strip())

            if not psutil.pid_exists(pid):
                return HealthCheckResult(
                    "resource_usage",
                    "warn",
                    "Cannot check resources - process not found",
                )

            process = psutil.Process(pid)
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            cpu_percent = process.cpu_percent(interval=0.1)

            details = {
                "memory_mb": round(memory_mb, 1),
                "cpu_percent": round(cpu_percent, 1),
                "num_threads": process.num_threads(),
                "open_files": len(process.open_files()),
            }

            # Check thresholds
            if memory_mb > self.MEMORY_THRESHOLD_MB:
                return HealthCheckResult(
                    "resource_usage",
                    "warn",
                    f"High memory usage: {memory_mb:.1f} MB (threshold: {self.MEMORY_THRESHOLD_MB} MB)",
                    details,
                )

            if cpu_percent > self.CPU_THRESHOLD_PERCENT:
                return HealthCheckResult(
                    "resource_usage",
                    "warn",
                    f"High CPU usage: {cpu_percent:.1f}% (threshold: {self.CPU_THRESHOLD_PERCENT}%)",
                    details,
                )

            return HealthCheckResult(
                "resource_usage",
                "pass",
                f"Resource usage normal (Memory: {memory_mb:.1f} MB, CPU: {cpu_percent:.1f}%)",
                details,
            )

        except Exception as e:
            return HealthCheckResult(
                "resource_usage", "warn", f"Error checking resource usage: {e}"
            )

    def _check_permissions(self) -> HealthCheckResult:
        """Check file system permissions."""
        try:
            checks = []

            # Check PID file directory
            pid_dir = Path(self.PID_FILE).parent
            if not os.access(pid_dir, os.W_OK):
                checks.append(f"No write permission for {pid_dir}")

            # Check target path
            target_path = os.getenv("MONITORING_TARGET_PATH")
            if target_path and not os.access(target_path, os.R_OK):
                checks.append(f"No read permission for {target_path}")

            # Check SQLite database path
            sqlite_path = os.getenv("SQLITE_PATH", "/app/data/cognitive_memory.db")
            sqlite_dir = Path(sqlite_path).parent
            if not os.access(sqlite_dir, os.W_OK):
                checks.append(f"No write permission for {sqlite_dir}")

            if checks:
                return HealthCheckResult(
                    "permissions", "fail", f"Permission issues: {'; '.join(checks)}"
                )

            return HealthCheckResult(
                "permissions", "pass", "All required permissions available"
            )

        except Exception as e:
            return HealthCheckResult(
                "permissions", "warn", f"Error checking permissions: {e}"
            )

    def _generate_summary(self, checks: list[HealthCheckResult]) -> dict[str, Any]:
        """Generate summary statistics from health checks."""
        total = len(checks)
        passed = sum(1 for check in checks if check.status == "pass")
        warned = sum(1 for check in checks if check.status == "warn")
        failed = sum(1 for check in checks if check.status == "fail")

        return {
            "total_checks": total,
            "passed": passed,
            "warnings": warned,
            "failed": failed,
            "success_rate": round((passed / total) * 100, 1) if total > 0 else 0,
        }


def check_health() -> int:
    """
    Standalone health check function for container health checks.

    Returns:
        0 if healthy, 1 if warnings, 2 if unhealthy
    """
    try:
        checker = ServiceHealthChecker()
        result = checker.check_all()

        if result["status"] == "healthy":
            return 0
        elif result["status"] == "warning":
            return 1
        else:
            return 2

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return 2


if __name__ == "__main__":
    import sys

    sys.exit(check_health())
