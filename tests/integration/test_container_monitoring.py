"""
Integration tests for container monitoring deployment and service management.

Tests cover Docker container integration, environment variable configuration,
service startup sequences, health checks, and container orchestration scenarios.
"""

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from cognitive_memory.core.config import CognitiveConfig
from heimdall.cognitive_system.monitoring_service import (
    MonitoringService,
    MonitoringServiceError,
)


class TestContainerEnvironmentIntegration:
    """Test monitoring service integration with container environment."""

    def test_container_environment_variable_parsing(self):
        """Test monitoring service configuration from container environment variables."""
        container_env = {
            "MONITORING_ENABLED": "true",
            "MONITORING_TARGET_PATH": str(Path.cwd()),
            "MONITORING_INTERVAL_SECONDS": "10.0",
            "MONITORING_BATCH_SIZE": "20",
            "MONITORING_IGNORE_PATTERNS": ".git,node_modules,__pycache__,.pytest_cache",
            "SYNC_ENABLED": "true",
            "SYNC_ATOMIC_OPERATIONS": "true",
            "SYNC_CONTINUE_ON_ERROR": "false",
            "SYNC_MAX_RETRY_ATTEMPTS": "5",
            "SYNC_RETRY_DELAY_SECONDS": "2.0",
        }

        with patch.dict(os.environ, container_env):
            config = CognitiveConfig.from_env()

            assert config.monitoring_enabled is True
            assert config.monitoring_interval_seconds == 10.0
            assert config.monitoring_batch_size == 20
            assert ".git" in config.monitoring_ignore_patterns
            assert "node_modules" in config.monitoring_ignore_patterns
            assert config.sync_enabled is True
            assert config.sync_atomic_operations is True
            assert config.sync_continue_on_error is False
            assert config.sync_max_retry_attempts == 5
            assert config.sync_retry_delay_seconds == 2.0

    def test_container_environment_defaults(self):
        """Test monitoring service with default container environment."""
        # Clear environment and set minimal required variables
        container_env = {
            "MONITORING_ENABLED": "true",
            "MONITORING_TARGET_PATH": str(Path.cwd()),
        }

        # Clear all monitoring-related environment variables
        env_to_clear = [
            "MONITORING_INTERVAL_SECONDS",
            "MONITORING_BATCH_SIZE",
            "MONITORING_IGNORE_PATTERNS",
            "SYNC_ENABLED",
            "SYNC_ATOMIC_OPERATIONS",
            "SYNC_CONTINUE_ON_ERROR",
            "SYNC_MAX_RETRY_ATTEMPTS",
            "SYNC_RETRY_DELAY_SECONDS",
        ]

        with patch.dict(os.environ, container_env, clear=False):
            # Remove monitoring env vars to test defaults
            for env_var in env_to_clear:
                os.environ.pop(env_var, None)

            config = CognitiveConfig.from_env()

            # Verify defaults are applied
            assert config.monitoring_enabled is True
            assert config.monitoring_interval_seconds == 5.0  # Default
            assert config.monitoring_batch_size == 10  # Default
            assert config.sync_enabled is True  # Default
            assert config.sync_atomic_operations is True  # Default

    def test_monitoring_disabled_in_container(self):
        """Test container behavior when monitoring is disabled."""
        container_env = {
            "MONITORING_ENABLED": "false",
            "MONITORING_TARGET_PATH": str(Path.cwd()),
        }

        with patch.dict(os.environ, container_env):
            config = CognitiveConfig.from_env()

            assert config.monitoring_enabled is False

            # Service initialization should fail
            with pytest.raises(MonitoringServiceError, match="Monitoring is disabled"):
                MonitoringService(config=config)

    def test_invalid_target_path_in_container(self):
        """Test container behavior with invalid target path."""
        container_env = {
            "MONITORING_ENABLED": "true",
            "MONITORING_TARGET_PATH": "/nonexistent/container/path",
        }

        with patch.dict(os.environ, container_env):
            config = CognitiveConfig.from_env()

            # Service initialization should fail
            with pytest.raises(
                MonitoringServiceError, match="Target path does not exist"
            ):
                MonitoringService(config=config)


class TestContainerServiceLifecycle:
    """Test service lifecycle within container environment."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory mimicking container mount."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create typical project structure
            project_dir = Path(tmp_dir) / "project"
            project_dir.mkdir()

            # Create some markdown files
            (project_dir / "README.md").write_text("# Test Project")
            (project_dir / "docs").mkdir()
            (project_dir / "docs" / "guide.md").write_text("# User Guide")

            yield str(project_dir)

    @pytest.fixture
    def container_service(self, temp_project_dir):
        """Create monitoring service with container-like configuration."""
        container_env = {
            "MONITORING_ENABLED": "true",
            "MONITORING_TARGET_PATH": temp_project_dir,
            "MONITORING_INTERVAL_SECONDS": "1.0",  # Fast for testing
            "MONITORING_IGNORE_PATTERNS": ".git,node_modules,__pycache__",
            "SYNC_ENABLED": "true",
            "SYNC_ATOMIC_OPERATIONS": "true",
        }

        with patch.dict(os.environ, container_env):
            config = CognitiveConfig.from_env()
            service = MonitoringService(config=config)
            yield service

            # Cleanup
            if service.status.is_running:
                service.stop()

    @patch("memory_system.monitoring_service.initialize_system")
    @patch("cognitive_memory.monitoring.create_default_registry")
    def test_container_service_startup_sequence(
        self, mock_registry, mock_init_system, container_service
    ):
        """Test complete container service startup sequence."""
        # Mock dependencies
        mock_cognitive_system = Mock()
        mock_init_system.return_value = mock_cognitive_system
        mock_registry.return_value = Mock()

        with patch.object(container_service, "_is_service_running", return_value=False):
            with patch.object(container_service, "_write_pid_file"):
                success = container_service.start()

                assert success is True
                assert container_service.status.is_running is True
                assert container_service.cognitive_system is not None
                assert container_service.file_monitor is not None
                assert container_service.sync_handler is not None

                # Verify monitoring is actually started
                assert container_service.file_monitor is not None

    def test_container_service_health_check_integration(self, container_service):
        """Test container health check integration."""
        # Simulate running service
        container_service.status.is_running = True
        container_service.cognitive_system = Mock()
        container_service.file_monitor = Mock()
        container_service.file_monitor._monitoring = True

        with patch("pathlib.Path.exists", return_value=True):
            health = container_service.health_check()

            assert health["status"] in ["healthy", "warning"]
            assert "timestamp" in health
            assert len(health["checks"]) >= 4

            # Verify all critical checks pass
            critical_checks = ["service_running", "cognitive_system", "file_monitoring"]
            for check in health["checks"]:
                if check["name"] in critical_checks:
                    assert check["status"] == "pass"

    def test_container_service_graceful_shutdown(self, container_service):
        """Test graceful service shutdown in container environment."""
        # Set up running service
        container_service.status.is_running = True
        container_service.file_monitor = Mock()

        with patch.object(container_service, "_remove_pid_file"):
            success = container_service.stop()

            assert success is True
            assert container_service.status.is_running is False
            container_service.file_monitor.stop_monitoring.assert_called_once()


class TestContainerProcessManagement:
    """Test process management within container environment."""

    def test_pid_file_management_in_container(self):
        """Test PID file operations in container environment."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            container_env = {
                "MONITORING_ENABLED": "true",
                "MONITORING_TARGET_PATH": tmp_dir,
            }

            with patch.dict(os.environ, container_env):
                service = MonitoringService()

                # Override PID file location for testing
                test_pid_file = Path(tmp_dir) / "test.pid"
                service.PID_FILE = str(test_pid_file)

                # Test PID file creation
                service._write_pid_file()
                assert test_pid_file.exists()

                # Test PID file content
                with open(test_pid_file) as f:
                    pid_content = f.read().strip()
                    assert pid_content == str(os.getpid())

                # Test PID file removal
                service._remove_pid_file()
                assert not test_pid_file.exists()

    def test_signal_handling_setup(self):
        """Test signal handler setup for container integration."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            container_env = {
                "MONITORING_ENABLED": "true",
                "MONITORING_TARGET_PATH": tmp_dir,
            }

            with patch.dict(os.environ, container_env):
                service = MonitoringService()

                # Test signal handler setup doesn't raise exceptions
                try:
                    service._setup_signal_handlers()
                except Exception as e:
                    pytest.fail(f"Signal handler setup failed: {e}")

    def test_container_resource_monitoring(self):
        """Test resource monitoring within container limits."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            container_env = {
                "MONITORING_ENABLED": "true",
                "MONITORING_TARGET_PATH": tmp_dir,
            }

            with patch.dict(os.environ, container_env):
                service = MonitoringService()
                service.status.pid = os.getpid()

                # Test memory usage calculation
                memory_usage = service.status._get_memory_usage()
                if memory_usage is not None:
                    assert isinstance(memory_usage, float)
                    assert memory_usage > 0

                # Test CPU usage calculation
                cpu_percent = service.status._get_cpu_percent()
                if cpu_percent is not None:
                    assert isinstance(cpu_percent, float)
                    assert cpu_percent >= 0


class TestContainerErrorHandling:
    """Test error handling and recovery in container environment."""

    def test_container_startup_with_missing_dependencies(self):
        """Test container startup behavior with missing dependencies."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            container_env = {
                "MONITORING_ENABLED": "true",
                "MONITORING_TARGET_PATH": tmp_dir,
            }

            with patch.dict(os.environ, container_env):
                service = MonitoringService()

                # Mock initialization failure
                with patch(
                    "memory_system.monitoring_service.initialize_system"
                ) as mock_init:
                    mock_init.side_effect = Exception("Qdrant connection failed")

                    with patch.object(
                        service, "_is_service_running", return_value=False
                    ):
                        success = service.start()

                        assert success is False
                        assert service.status.error_count > 0
                        assert "Qdrant connection failed" in service.status.last_error

    def test_container_file_permission_errors(self):
        """Test handling of file permission errors in container."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create directory with no read permissions
            restricted_dir = Path(tmp_dir) / "restricted"
            restricted_dir.mkdir()
            os.chmod(restricted_dir, 0o000)

            try:
                container_env = {
                    "MONITORING_ENABLED": "true",
                    "MONITORING_TARGET_PATH": str(restricted_dir),
                }

                with patch.dict(os.environ, container_env):
                    with pytest.raises(
                        MonitoringServiceError, match="No read permission"
                    ):
                        MonitoringService()
            finally:
                # Restore permissions for cleanup
                os.chmod(restricted_dir, 0o755)

    def test_container_service_recovery_after_error(self):
        """Test service recovery after errors in container environment."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            container_env = {
                "MONITORING_ENABLED": "true",
                "MONITORING_TARGET_PATH": tmp_dir,
            }

            with patch.dict(os.environ, container_env):
                service = MonitoringService()

                # Simulate error conditions
                service.status.error_count = 5
                service.status.started_at = time.time() - 120  # 2 minutes ago
                service._restart_attempts = 0

                # Test restart conditions
                assert service._should_restart() is True

                # Mock successful restart
                with patch.object(
                    service, "restart", return_value=True
                ) as mock_restart:
                    result = service._attempt_restart()
                    assert result is True
                    # Verify restart was called
                    mock_restart.assert_called_once()

    def test_container_graceful_degradation(self):
        """Test graceful degradation when monitoring components fail."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            container_env = {
                "MONITORING_ENABLED": "true",
                "MONITORING_TARGET_PATH": tmp_dir,
            }

            with patch.dict(os.environ, container_env):
                service = MonitoringService()

                # Set up partially initialized service
                service.cognitive_system = Mock()
                service.file_monitor = None  # Monitoring failed to initialize
                service.sync_handler = None

                # Health check should indicate problems but not crash
                health = service.health_check()
                assert health["status"] == "unhealthy"

                # Should have specific check failures
                failed_checks = [
                    check for check in health["checks"] if check["status"] == "fail"
                ]
                assert len(failed_checks) > 0


class TestContainerHealthCheckIntegration:
    """Test health check integration with container orchestration."""

    def test_docker_health_check_format(self):
        """Test health check output format for Docker compatibility."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            container_env = {
                "MONITORING_ENABLED": "true",
                "MONITORING_TARGET_PATH": tmp_dir,
            }

            with patch.dict(os.environ, container_env):
                service = MonitoringService()

                # Set up healthy service
                service.status.is_running = True
                service.cognitive_system = Mock()
                service.file_monitor = Mock()
                service.file_monitor._monitoring = True

                with patch("pathlib.Path.exists", return_value=True):
                    health = service.health_check()

                    # Verify required fields for Docker health check
                    assert "status" in health
                    assert health["status"] in ["healthy", "warning", "unhealthy"]
                    assert "checks" in health
                    assert isinstance(health["checks"], list)
                    assert "timestamp" in health

                    # Verify check format
                    for check in health["checks"]:
                        assert "name" in check
                        assert "status" in check
                        assert "message" in check
                        assert check["status"] in ["pass", "warn", "fail"]

    def test_kubernetes_readiness_probe_compatibility(self):
        """Test health check compatibility with Kubernetes readiness probes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            container_env = {
                "MONITORING_ENABLED": "true",
                "MONITORING_TARGET_PATH": tmp_dir,
            }

            with patch.dict(os.environ, container_env):
                service = MonitoringService()

                # Test service not ready (not running)
                service.status.is_running = False
                health = service.health_check()
                assert health["status"] == "unhealthy"

                # Test service ready (running and healthy)
                service.status.is_running = True
                service.cognitive_system = Mock()
                service.file_monitor = Mock()
                service.file_monitor._monitoring = True

                with patch("pathlib.Path.exists", return_value=True):
                    health = service.health_check()
                    assert health["status"] in ["healthy", "warning"]

    def test_container_orchestration_metrics(self):
        """Test metrics collection for container orchestration monitoring."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            container_env = {
                "MONITORING_ENABLED": "true",
                "MONITORING_TARGET_PATH": tmp_dir,
            }

            with patch.dict(os.environ, container_env):
                service = MonitoringService()
                service.status.started_at = time.time()
                service.status.pid = os.getpid()
                service.status.sync_operations = 10
                service.status.files_monitored = 5

                status = service.get_status()

                # Verify metrics for orchestration monitoring
                required_metrics = [
                    "uptime_seconds",
                    "memory_usage_mb",
                    "cpu_percent",
                    "sync_operations",
                    "files_monitored",
                    "error_count",
                ]

                for metric in required_metrics:
                    assert metric in status


if __name__ == "__main__":
    pytest.main([__file__])
