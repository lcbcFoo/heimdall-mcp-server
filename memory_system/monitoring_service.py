#!/usr/bin/env python3
"""
Host-based monitoring service for cognitive memory system.

This module provides a production-ready monitoring service that runs as a host process
with project-local PID files, automatically detecting file changes and
synchronizing memories. Designed for reliability, observability, and multi-project support.
"""

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

import psutil
from loguru import logger

from cognitive_memory.core.config import (
    SystemConfig,
    detect_container_environment,
    get_monitoring_config,
    get_project_paths,
)
from cognitive_memory.core.interfaces import CognitiveSystem
from cognitive_memory.main import initialize_system
from cognitive_memory.monitoring import (
    ChangeType,
    FileChangeEvent,
    FileSyncHandler,
    MarkdownFileMonitor,
    create_default_registry,
)


class MonitoringServiceError(Exception):
    """Base exception for monitoring service errors."""

    pass


class ServiceStatus:
    """Service status tracking and reporting."""

    def __init__(self) -> None:
        self.started_at: float | None = None
        self.pid: int | None = None
        self.is_running: bool = False
        self.error_count: int = 0
        self.last_error: str | None = None
        self.restart_count: int = 0
        self.files_monitored: int = 0
        self.sync_operations: int = 0
        self.last_sync_time: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert status to dictionary for JSON serialization."""
        return {
            "started_at": self.started_at,
            "pid": self.pid,
            "is_running": self.is_running,
            "uptime_seconds": time.time() - self.started_at
            if self.started_at
            else None,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "restart_count": self.restart_count,
            "files_monitored": self.files_monitored,
            "sync_operations": self.sync_operations,
            "last_sync_time": self.last_sync_time,
            "memory_usage_mb": self._get_memory_usage(),
            "cpu_percent": self._get_cpu_percent(),
        }

    def _get_memory_usage(self) -> float | None:
        """Get current memory usage in MB."""
        try:
            if self.pid:
                process = psutil.Process(self.pid)
                return float(process.memory_info().rss / 1024 / 1024)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return None

    def _get_cpu_percent(self) -> float | None:
        """Get current CPU usage percentage."""
        try:
            if self.pid:
                process = psutil.Process(self.pid)
                return float(process.cpu_percent())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return None


class MonitoringService:
    """
    Host-based monitoring service for cognitive memory system.

    Provides automatic file monitoring with project-local PID management,
    including daemon mode, health checks, error recovery, and production logging.
    Uses .heimdall/config.yaml for configuration instead of container environment variables.
    """

    # PID_FILE now determined per-project
    SOCKET_PATH = "/tmp/monitoring.sock"
    MAX_RESTART_ATTEMPTS = 5
    RESTART_BACKOFF_BASE = 1.0  # seconds
    RESTART_BACKOFF_MAX = 60.0  # seconds

    def __init__(self, project_root: str | None = None):
        """
        Initialize monitoring service.

        Args:
            project_root: Optional project root directory, defaults to current working directory
        """
        # Get project paths and configuration
        self.project_paths = get_project_paths(
            Path(project_root) if project_root else None
        )
        self.monitoring_config = get_monitoring_config(self.project_paths.project_root)

        # Load full system config for cognitive parameters
        system_config = SystemConfig.from_env()
        self.config = system_config.cognitive
        self.status = ServiceStatus()
        self.cognitive_system: CognitiveSystem | None = None
        self.file_monitor: MarkdownFileMonitor | None = None
        self.sync_handler: FileSyncHandler | None = None
        self._shutdown_requested = False
        self._restart_attempts = 0

        # Validate configuration
        self._validate_configuration()

        # Clean up any stale PID files
        self.project_paths.cleanup_stale_pid()

        # Detect container environment for health check behavior
        self._is_container = detect_container_environment()

        logger.info("MonitoringService initialized with configuration")

    def _validate_configuration(self) -> None:
        """Validate service configuration and dependencies."""
        if not self.config.monitoring_enabled:
            raise MonitoringServiceError("Monitoring is disabled in configuration")

        # Check target path from centralized configuration
        target_path = self.monitoring_config["target_path"]
        target_path_obj = Path(target_path)
        if not target_path_obj.exists():
            raise MonitoringServiceError(f"Target path does not exist: {target_path}")

        if not target_path_obj.is_dir():
            raise MonitoringServiceError(
                f"Target path is not a directory: {target_path}"
            )

        # Check permissions
        if not os.access(target_path, os.R_OK):
            raise MonitoringServiceError(
                f"No read permission for target path: {target_path}"
            )

        logger.info(f"Configuration validated - monitoring target: {target_path}")

    def start(self, daemon_mode: bool = False) -> bool:
        """
        Start the monitoring service.

        Args:
            daemon_mode: Whether to run as background daemon process

        Returns:
            True if service started successfully, False otherwise
        """
        try:
            # Check if already running using project-local PID
            if self._is_service_running():
                logger.warning("Monitoring service is already running")
                return False

            logger.info("Starting monitoring service...")

            # Initialize cognitive system
            self._initialize_cognitive_system()

            # Initialize monitoring components
            self._initialize_monitoring()

            # Setup signal handlers
            self._setup_signal_handlers()

            # Start monitoring
            if self.file_monitor:
                self.file_monitor.start_monitoring()

            # Update status
            self.status.started_at = time.time()
            self.status.pid = os.getpid()
            self.status.is_running = True
            self.status.restart_count = self._restart_attempts

            # Write project-local PID file
            self._write_pid_file()

            logger.info(
                f"Monitoring service started successfully (PID: {self.status.pid})"
            )

            if daemon_mode:
                self._run_daemon_loop()

            return True

        except Exception as e:
            logger.error(f"Failed to start monitoring service: {e}")
            self.status.error_count += 1
            self.status.last_error = str(e)
            return False

    def stop(self) -> bool:
        """
        Stop the monitoring service gracefully.

        Returns:
            True if service stopped successfully, False otherwise
        """
        try:
            logger.info("Stopping monitoring service...")
            self._shutdown_requested = True

            # Stop file monitoring
            if self.file_monitor:
                self.file_monitor.stop_monitoring()
                logger.info("File monitoring stopped")

            # Update status
            self.status.is_running = False

            # Remove project-local PID file
            self._remove_pid_file()

            logger.info("Monitoring service stopped successfully")
            return True

        except Exception as e:
            logger.error(f"Error stopping monitoring service: {e}")
            self.status.error_count += 1
            self.status.last_error = str(e)
            return False

    def restart(self) -> bool:
        """
        Restart the monitoring service.

        Returns:
            True if service restarted successfully, False otherwise
        """
        logger.info("Restarting monitoring service...")

        # Stop current service
        if not self.stop():
            logger.error("Failed to stop service for restart")
            return False

        # Wait a moment for cleanup
        time.sleep(1.0)

        # Start service again
        self._restart_attempts += 1
        return self.start()

    def get_status(self) -> dict[str, Any]:
        """
        Get current service status.

        Returns:
            Dictionary containing service status information
        """
        # Update monitored files count
        if self.file_monitor:
            self.status.files_monitored = len(self.file_monitor.get_monitored_files())

        return self.status.to_dict()

    def health_check(self) -> dict[str, Any]:
        """
        Perform health check for container orchestration.

        Returns:
            Dictionary containing health check results
        """
        health: dict[str, Any] = {
            "status": "healthy",
            "checks": [],
            "timestamp": time.time(),
        }

        try:
            # Check if service is running - different logic for container vs dev environments
            if self._is_container:
                # Container environment: check actual process via PID file
                if not self._is_service_running():
                    health["status"] = "unhealthy"
                    health["checks"].append(
                        {
                            "name": "service_running",
                            "status": "fail",
                            "message": "Monitoring service is not running",
                        }
                    )
                else:
                    health["checks"].append(
                        {
                            "name": "service_running",
                            "status": "pass",
                            "message": "Monitoring service is running",
                        }
                    )
            else:
                # Dev/test environment: check internal status
                if not self.status.is_running:
                    health["status"] = "unhealthy"
                    health["checks"].append(
                        {
                            "name": "service_running",
                            "status": "fail",
                            "message": "Monitoring service is not running (dev mode)",
                        }
                    )
                else:
                    health["checks"].append(
                        {
                            "name": "service_running",
                            "status": "pass",
                            "message": "Monitoring service is running (dev mode)",
                        }
                    )

            # Check project-local PID file
            if not self.project_paths.pid_file.exists():
                health["status"] = "unhealthy"
                health["checks"].append(
                    {
                        "name": "pid_file",
                        "status": "fail",
                        "message": "PID file not found",
                    }
                )
            else:
                health["checks"].append(
                    {"name": "pid_file", "status": "pass", "message": "PID file exists"}
                )

            # Check cognitive system
            # If service is running, assume cognitive system is initialized
            if self._is_service_running():
                health["checks"].append(
                    {
                        "name": "cognitive_system",
                        "status": "pass",
                        "message": "Cognitive system initialized (service running)",
                    }
                )
            elif not self.cognitive_system:
                health["status"] = "unhealthy"
                health["checks"].append(
                    {
                        "name": "cognitive_system",
                        "status": "fail",
                        "message": "Cognitive system not initialized",
                    }
                )
            else:
                health["checks"].append(
                    {
                        "name": "cognitive_system",
                        "status": "pass",
                        "message": "Cognitive system initialized",
                    }
                )

            # Check file monitoring
            # If service is running, assume file monitoring is active
            if self._is_service_running():
                health["checks"].append(
                    {
                        "name": "file_monitoring",
                        "status": "pass",
                        "message": "File monitoring active (service running)",
                    }
                )
            elif not self.file_monitor or not self.file_monitor._monitoring:
                health["status"] = "unhealthy"
                health["checks"].append(
                    {
                        "name": "file_monitoring",
                        "status": "fail",
                        "message": "File monitoring not active",
                    }
                )
            else:
                health["checks"].append(
                    {
                        "name": "file_monitoring",
                        "status": "pass",
                        "message": "File monitoring active",
                    }
                )

            # Check resource usage
            memory_usage = self.status._get_memory_usage()
            if memory_usage and memory_usage > 500:  # 500 MB threshold
                health["status"] = "warning"
                health["checks"].append(
                    {
                        "name": "memory_usage",
                        "status": "warn",
                        "message": f"High memory usage: {memory_usage:.1f} MB",
                    }
                )
            else:
                health["checks"].append(
                    {
                        "name": "memory_usage",
                        "status": "pass",
                        "message": f"Memory usage: {memory_usage:.1f} MB"
                        if memory_usage
                        else "Memory usage: unknown",
                    }
                )

        except Exception as e:
            health["status"] = "unhealthy"
            health["checks"].append(
                {
                    "name": "health_check_error",
                    "status": "fail",
                    "message": f"Health check failed: {e}",
                }
            )

        return health

    def _initialize_cognitive_system(self) -> None:
        """Initialize the cognitive system."""
        try:
            logger.info("Initializing cognitive system...")
            self.cognitive_system = initialize_system("default")
            logger.info("Cognitive system initialized successfully")
        except Exception as e:
            raise MonitoringServiceError(
                f"Failed to initialize cognitive system: {e}"
            ) from e

    def _initialize_monitoring(self) -> None:
        """Initialize file monitoring components."""
        try:
            logger.info("Initializing monitoring components...")

            # Get target path from centralized configuration
            target_path = self.monitoring_config["target_path"]

            # Create file monitor using centralized config
            self.file_monitor = MarkdownFileMonitor(
                polling_interval=self.monitoring_config["interval_seconds"],
                ignore_patterns=set(self.monitoring_config["ignore_patterns"]),
            )

            # Add target path to monitoring
            self.file_monitor.add_path(target_path)

            # Create loader registry and sync handler
            if not self.cognitive_system:
                raise MonitoringServiceError("Cognitive system not initialized")

            loader_registry = create_default_registry()
            self.sync_handler = FileSyncHandler(
                cognitive_system=self.cognitive_system,
                loader_registry=loader_registry,
                enable_atomic_operations=self.config.sync_atomic_operations,
            )

            # Register sync callbacks
            self.file_monitor.register_callback(
                ChangeType.ADDED, self._handle_file_change
            )
            self.file_monitor.register_callback(
                ChangeType.MODIFIED, self._handle_file_change
            )
            self.file_monitor.register_callback(
                ChangeType.DELETED, self._handle_file_change
            )

            logger.info(f"Monitoring initialized for path: {target_path}")

        except Exception as e:
            raise MonitoringServiceError(f"Failed to initialize monitoring: {e}") from e

    def _handle_file_change(self, event: FileChangeEvent) -> None:
        """Handle file change events."""
        try:
            logger.info(f"Processing file change: {event}")

            # Delegate to sync handler
            if not self.sync_handler:
                logger.error("Sync handler not initialized")
                return
            success = self.sync_handler.handle_file_change(event)

            if success:
                self.status.sync_operations += 1
                self.status.last_sync_time = time.time()
                logger.info(f"Successfully processed file change: {event.path}")
            else:
                self.status.error_count += 1
                logger.error(f"Failed to process file change: {event.path}")

        except Exception as e:
            self.status.error_count += 1
            self.status.last_error = str(e)
            logger.error(f"Error handling file change {event}: {e}")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum: int, frame: Any) -> None:
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self._shutdown_requested = True
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    def _run_daemon_loop(self) -> None:
        """Run the main daemon loop."""
        logger.info("Entering daemon mode...")

        try:
            while not self._shutdown_requested:
                # Sleep for a short interval
                time.sleep(1.0)

                # Check if we need to restart on error
                if self.status.error_count > 0 and self._should_restart():
                    logger.warning("Error threshold reached, attempting restart...")
                    if not self._attempt_restart():
                        logger.error("Restart failed, exiting...")
                        break

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
        except Exception as e:
            logger.error(f"Daemon loop error: {e}")
        finally:
            self.stop()

    def _should_restart(self) -> bool:
        """Determine if service should attempt restart."""
        return (
            self.status.error_count >= 3
            and self._restart_attempts < self.MAX_RESTART_ATTEMPTS
            and time.time() - (self.status.started_at or 0)
            > 60  # Don't restart too quickly
        )

    def _attempt_restart(self) -> bool:
        """Attempt to restart the service with exponential backoff."""
        if self._restart_attempts >= self.MAX_RESTART_ATTEMPTS:
            logger.error("Maximum restart attempts reached")
            return False

        # Calculate backoff delay
        delay = min(
            self.RESTART_BACKOFF_BASE * (2**self._restart_attempts),
            self.RESTART_BACKOFF_MAX,
        )

        logger.info(
            f"Restarting in {delay} seconds (attempt {self._restart_attempts + 1})"
        )
        time.sleep(delay)

        return self.restart()

    def _is_service_running(self) -> bool:
        """Check if monitoring service is already running using project-local PID."""
        pid_file = self.project_paths.pid_file
        if not pid_file.exists():
            return False

        try:
            with open(pid_file) as f:
                pid = int(f.read().strip())

            # Check if process exists
            return bool(psutil.pid_exists(pid))

        except (ValueError, FileNotFoundError, PermissionError):
            return False

    def _write_pid_file(self) -> None:
        """Write project-local PID file for service tracking."""
        try:
            with open(self.project_paths.pid_file, "w") as f:
                f.write(str(os.getpid()))
            logger.debug(f"PID file written: {self.project_paths.pid_file}")
        except Exception as e:
            logger.warning(f"Failed to write PID file: {e}")

    def _remove_pid_file(self) -> None:
        """Remove project-local PID file on service shutdown."""
        try:
            self.project_paths.pid_file.unlink(missing_ok=True)
            logger.debug(f"PID file removed: {self.project_paths.pid_file}")
        except Exception as e:
            logger.warning(f"Failed to remove PID file: {e}")


def main() -> int:
    """Main entry point for monitoring service CLI."""
    parser = argparse.ArgumentParser(
        description="Host-based monitoring service for cognitive memory system"
    )
    parser.add_argument("--start", action="store_true", help="Start monitoring service")
    parser.add_argument("--stop", action="store_true", help="Stop monitoring service")
    parser.add_argument(
        "--restart", action="store_true", help="Restart monitoring service"
    )
    parser.add_argument("--status", action="store_true", help="Show service status")
    parser.add_argument("--health", action="store_true", help="Perform health check")
    parser.add_argument("--daemon", action="store_true", help="Run in daemon mode")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument(
        "--project-root",
        type=str,
        help="Project root directory (defaults to current directory)",
    )

    args = parser.parse_args()

    try:
        service = MonitoringService(project_root=args.project_root)

        if args.start:
            success = service.start(daemon_mode=args.daemon)
            return 0 if success else 1

        elif args.stop:
            success = service.stop()
            return 0 if success else 1

        elif args.restart:
            success = service.restart()
            return 0 if success else 1

        elif args.status:
            status = service.get_status()
            if args.json:
                print(json.dumps(status, indent=2))
            else:
                print(
                    f"Service Status: {'Running' if status['is_running'] else 'Stopped'}"
                )
                if status["pid"]:
                    print(f"PID: {status['pid']}")
                if status["uptime_seconds"]:
                    print(f"Uptime: {status['uptime_seconds']:.1f} seconds")
                print(f"Files Monitored: {status['files_monitored']}")
                print(f"Sync Operations: {status['sync_operations']}")
                if status["error_count"] > 0:
                    print(f"Errors: {status['error_count']}")
            return 0

        elif args.health:
            health = service.health_check()
            if args.json:
                print(json.dumps(health, indent=2))
            else:
                print(f"Health Status: {health['status']}")
                for check in health["checks"]:
                    status_icon = (
                        "✅"
                        if check["status"] == "pass"
                        else "⚠️"
                        if check["status"] == "warn"
                        else "❌"
                    )
                    print(f"  {status_icon} {check['name']}: {check['message']}")
            return 0 if health["status"] in ["healthy", "warning"] else 1

        else:
            parser.print_help()
            return 1

    except MonitoringServiceError as e:
        print(f"Service Error: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
