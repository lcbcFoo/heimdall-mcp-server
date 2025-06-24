"""
Unit tests for MonitoringService production service management.

Tests cover service lifecycle, configuration validation, error handling,
health checks, and production deployment scenarios.
"""

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import psutil
import pytest

from cognitive_memory.core.config import CognitiveConfig
from cognitive_memory.monitoring import (
    ChangeType,
    FileChangeEvent,
)
from heimdall.cognitive_system.monitoring_service import (
    MonitoringService,
    MonitoringServiceError,
    ServiceStatus,
)


class TestServiceStatus:
    """Test ServiceStatus functionality."""

    def test_initialization(self):
        """Test ServiceStatus initialization."""
        status = ServiceStatus()

        assert status.started_at is None
        assert status.pid is None
        assert status.is_running is False
        assert status.error_count == 0
        assert status.last_error is None
        assert status.restart_count == 0
        assert status.files_monitored == 0
        assert status.sync_operations == 0
        assert status.last_sync_time is None

    def test_to_dict_basic(self):
        """Test ServiceStatus to_dict conversion."""
        status = ServiceStatus()
        status.started_at = 1234567890.0
        status.pid = 12345
        status.is_running = True
        status.error_count = 2
        status.last_error = "Test error"
        status.restart_count = 1
        status.files_monitored = 5
        status.sync_operations = 10
        status.last_sync_time = 1234567900.0

        result = status.to_dict()

        assert result["started_at"] == 1234567890.0
        assert result["pid"] == 12345
        assert result["is_running"] is True
        assert result["error_count"] == 2
        assert result["last_error"] == "Test error"
        assert result["restart_count"] == 1
        assert result["files_monitored"] == 5
        assert result["sync_operations"] == 10
        assert result["last_sync_time"] == 1234567900.0
        assert "uptime_seconds" in result
        assert "memory_usage_mb" in result
        assert "cpu_percent" in result

    def test_to_dict_no_started_time(self):
        """Test to_dict when service hasn't started."""
        status = ServiceStatus()
        result = status.to_dict()

        assert result["uptime_seconds"] is None

    @patch("psutil.Process")
    def test_memory_usage_calculation(self, mock_process_class):
        """Test memory usage calculation."""
        # Mock process memory info
        mock_process = Mock()
        mock_memory_info = Mock()
        mock_memory_info.rss = 100 * 1024 * 1024  # 100 MB in bytes
        mock_process.memory_info.return_value = mock_memory_info
        mock_process_class.return_value = mock_process

        status = ServiceStatus()
        status.pid = 12345

        memory_usage = status._get_memory_usage()
        assert memory_usage == 100.0  # 100 MB

    @patch("psutil.Process")
    def test_memory_usage_process_not_found(self, mock_process_class):
        """Test memory usage when process not found."""
        mock_process_class.side_effect = psutil.NoSuchProcess(12345)

        status = ServiceStatus()
        status.pid = 12345

        memory_usage = status._get_memory_usage()
        assert memory_usage is None

    @patch("psutil.Process")
    def test_cpu_percent_calculation(self, mock_process_class):
        """Test CPU percentage calculation."""
        mock_process = Mock()
        mock_process.cpu_percent.return_value = 15.5
        mock_process_class.return_value = mock_process

        status = ServiceStatus()
        status.pid = 12345

        cpu_percent = status._get_cpu_percent()
        assert cpu_percent == 15.5


class TestMonitoringServiceInitialization:
    """Test MonitoringService initialization and configuration."""

    def test_default_initialization(self):
        """Test default MonitoringService initialization."""
        with patch.dict(
            os.environ,
            {"MONITORING_ENABLED": "true", "MONITORING_TARGET_PATH": str(Path.cwd())},
        ):
            service = MonitoringService()

            assert service.config is not None
            assert service.status is not None
            assert service.cognitive_system is None
            assert service.file_monitor is None
            assert service.sync_handler is None
            assert service._shutdown_requested is False
            assert service._restart_attempts == 0

    def test_custom_config_initialization(self):
        """Test MonitoringService with custom config."""
        config = CognitiveConfig(
            monitoring_enabled=True, monitoring_interval_seconds=10.0
        )

        with patch.dict(os.environ, {"MONITORING_TARGET_PATH": str(Path.cwd())}):
            service = MonitoringService(config=config)

            assert service.config == config
            assert service.config.monitoring_interval_seconds == 10.0

    def test_configuration_validation_disabled_monitoring(self):
        """Test configuration validation when monitoring is disabled."""
        config = CognitiveConfig(monitoring_enabled=False)

        with pytest.raises(MonitoringServiceError, match="Monitoring is disabled"):
            MonitoringService(config=config)

    def test_configuration_validation_missing_target_path(self):
        """Test configuration validation with missing target path."""
        config = CognitiveConfig(monitoring_enabled=True)

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(
                MonitoringServiceError, match="MONITORING_TARGET_PATH.*not set"
            ):
                MonitoringService(config=config)

    def test_configuration_validation_nonexistent_path(self):
        """Test configuration validation with non-existent target path."""
        config = CognitiveConfig(monitoring_enabled=True)

        with patch.dict(os.environ, {"MONITORING_TARGET_PATH": "/nonexistent/path"}):
            with pytest.raises(
                MonitoringServiceError, match="Target path does not exist"
            ):
                MonitoringService(config=config)

    def test_configuration_validation_non_directory_path(self):
        """Test configuration validation with file instead of directory."""
        config = CognitiveConfig(monitoring_enabled=True)

        with tempfile.NamedTemporaryFile() as tmp_file:
            with patch.dict(os.environ, {"MONITORING_TARGET_PATH": tmp_file.name}):
                with pytest.raises(MonitoringServiceError, match="not a directory"):
                    MonitoringService(config=config)

    def test_configuration_validation_no_read_permission(self):
        """Test configuration validation with no read permission."""
        config = CognitiveConfig(monitoring_enabled=True)

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Remove read permission
            os.chmod(tmp_dir, 0o000)

            try:
                with patch.dict(os.environ, {"MONITORING_TARGET_PATH": tmp_dir}):
                    with pytest.raises(
                        MonitoringServiceError, match="No read permission"
                    ):
                        MonitoringService(config=config)
            finally:
                # Restore permissions for cleanup
                os.chmod(tmp_dir, 0o755)


class TestMonitoringServiceLifecycle:
    """Test MonitoringService lifecycle operations."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield tmp_dir

    @pytest.fixture
    def service(self, temp_dir):
        """Create MonitoringService for testing."""
        config = CognitiveConfig(
            monitoring_enabled=True, monitoring_interval_seconds=1.0
        )

        with patch.dict(os.environ, {"MONITORING_TARGET_PATH": temp_dir}):
            service = MonitoringService(config=config)
            yield service

            # Cleanup
            if service.status.is_running:
                service.stop()

    @patch("memory_system.monitoring_service.initialize_system")
    @patch("cognitive_memory.monitoring.create_default_registry")
    def test_service_start_success(self, mock_registry, mock_init_system, service):
        """Test successful service start."""
        # Mock dependencies
        mock_cognitive_system = Mock()
        mock_init_system.return_value = mock_cognitive_system
        mock_registry.return_value = Mock()

        # Mock PID file operations
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False  # Service not already running

            with patch.object(service, "_write_pid_file"):
                success = service.start()

                assert success is True
                assert service.status.is_running is True
                assert service.status.pid == os.getpid()
                assert service.cognitive_system == mock_cognitive_system
                assert service.file_monitor is not None
                assert service.sync_handler is not None

    @patch("memory_system.monitoring_service.initialize_system")
    def test_service_start_already_running(self, mock_init_system, service):
        """Test service start when already running."""
        # Mock service as already running
        with patch.object(service, "_is_service_running", return_value=True):
            success = service.start()

            assert success is False
            mock_init_system.assert_not_called()

    @patch("memory_system.monitoring_service.initialize_system")
    def test_service_start_initialization_failure(self, mock_init_system, service):
        """Test service start with initialization failure."""
        mock_init_system.side_effect = Exception("Init failed")

        with patch.object(service, "_is_service_running", return_value=False):
            success = service.start()

            assert success is False
            assert service.status.error_count > 0
            assert "Init failed" in service.status.last_error

    def test_service_stop_success(self, service):
        """Test successful service stop."""
        # Set up service as running
        service.status.is_running = True
        service.file_monitor = Mock()

        with patch.object(service, "_remove_pid_file"):
            success = service.stop()

            assert success is True
            assert service.status.is_running is False
            service.file_monitor.stop_monitoring.assert_called_once()

    def test_service_stop_with_error(self, service):
        """Test service stop with error."""
        service.status.is_running = True
        service.file_monitor = Mock()
        service.file_monitor.stop_monitoring.side_effect = Exception("Stop failed")

        with patch.object(service, "_remove_pid_file"):
            success = service.stop()

            assert success is False
            assert service.status.error_count > 0
            assert "Stop failed" in service.status.last_error

    @patch("memory_system.monitoring_service.initialize_system")
    def test_service_restart_success(self, mock_init_system, service):
        """Test successful service restart."""
        mock_cognitive_system = Mock()
        mock_init_system.return_value = mock_cognitive_system

        # Mock file monitor for stop operation
        service.file_monitor = Mock()
        service.status.is_running = True

        with patch.object(service, "_is_service_running", return_value=False):
            with patch.object(service, "_write_pid_file"):
                with patch.object(service, "_remove_pid_file"):
                    with patch("cognitive_memory.monitoring.create_default_registry"):
                        success = service.restart()

                        assert success is True
                        assert service._restart_attempts == 1

    def test_service_restart_stop_failure(self, service):
        """Test service restart when stop fails."""
        with patch.object(service, "stop", return_value=False):
            success = service.restart()

            assert success is False


class TestMonitoringServiceStatus:
    """Test MonitoringService status and health functionality."""

    @pytest.fixture
    def service(self):
        """Create MonitoringService for testing."""
        config = CognitiveConfig(monitoring_enabled=True)

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"MONITORING_TARGET_PATH": tmp_dir}):
                service = MonitoringService(config=config)
                yield service

    def test_get_status_basic(self, service):
        """Test basic status retrieval."""
        service.status.started_at = time.time()
        service.status.pid = 12345
        service.status.is_running = True
        service.status.sync_operations = 5

        status = service.get_status()

        assert status["pid"] == 12345
        assert status["is_running"] is True
        assert status["sync_operations"] == 5
        assert "uptime_seconds" in status

    def test_get_status_with_file_monitor(self, service):
        """Test status retrieval with file monitor."""
        service.file_monitor = Mock()
        service.file_monitor.get_monitored_files.return_value = ["file1.md", "file2.md"]

        status = service.get_status()

        assert status["files_monitored"] == 2

    def test_health_check_healthy_service(self, service):
        """Test health check for healthy service."""
        service.status.is_running = True
        service.cognitive_system = Mock()
        service.file_monitor = Mock()
        service.file_monitor._monitoring = True

        with patch("pathlib.Path.exists", return_value=True):
            health = service.health_check()

            assert health["status"] == "healthy"
            assert len(health["checks"]) >= 4

            # Check individual health checks
            check_names = [check["name"] for check in health["checks"]]
            assert "service_running" in check_names
            assert "pid_file" in check_names
            assert "cognitive_system" in check_names
            assert "file_monitoring" in check_names

    def test_health_check_unhealthy_service(self, service):
        """Test health check for unhealthy service."""
        service.status.is_running = False
        service.cognitive_system = None
        service.file_monitor = None

        with patch("pathlib.Path.exists", return_value=False):
            health = service.health_check()

            assert health["status"] == "unhealthy"

            # Should have failed checks
            failed_checks = [
                check for check in health["checks"] if check["status"] == "fail"
            ]
            assert len(failed_checks) >= 3

    def test_health_check_high_memory_warning(self, service):
        """Test health check with high memory usage."""
        service.status.is_running = True
        service.cognitive_system = Mock()
        service.file_monitor = Mock()
        service.file_monitor._monitoring = True

        # Mock high memory usage
        with patch.object(service.status, "_get_memory_usage", return_value=600.0):
            with patch("pathlib.Path.exists", return_value=True):
                health = service.health_check()

                assert health["status"] == "warning"

                # Should have memory warning
                memory_checks = [
                    check
                    for check in health["checks"]
                    if check["name"] == "memory_usage" and check["status"] == "warn"
                ]
                assert len(memory_checks) == 1

    def test_health_check_exception_handling(self, service):
        """Test health check exception handling."""
        # Make health check throw exception
        service.status._get_memory_usage = Mock(side_effect=Exception("Memory error"))

        health = service.health_check()

        assert health["status"] == "unhealthy"

        # Should have error check
        error_checks = [
            check for check in health["checks"] if check["name"] == "health_check_error"
        ]
        assert len(error_checks) == 1
        assert "Memory error" in error_checks[0]["message"]


class TestMonitoringServiceFileHandling:
    """Test MonitoringService file change handling."""

    @pytest.fixture
    def service(self):
        """Create MonitoringService with mocked dependencies."""
        config = CognitiveConfig(monitoring_enabled=True)

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"MONITORING_TARGET_PATH": tmp_dir}):
                service = MonitoringService(config=config)
                service.sync_handler = Mock()
                yield service

    def test_handle_file_change_success(self, service):
        """Test successful file change handling."""
        event = FileChangeEvent(
            path=Path("/test/file.md"),
            change_type=ChangeType.MODIFIED,
            timestamp=time.time(),
        )

        service.sync_handler.handle_file_change.return_value = True

        service._handle_file_change(event)

        assert service.status.sync_operations == 1
        assert service.status.last_sync_time is not None
        service.sync_handler.handle_file_change.assert_called_once_with(event)

    def test_handle_file_change_failure(self, service):
        """Test file change handling failure."""
        event = FileChangeEvent(
            path=Path("/test/file.md"),
            change_type=ChangeType.ADDED,
            timestamp=time.time(),
        )

        service.sync_handler.handle_file_change.return_value = False

        service._handle_file_change(event)

        assert service.status.sync_operations == 0
        assert service.status.error_count == 1

    def test_handle_file_change_no_sync_handler(self, service):
        """Test file change handling without sync handler."""
        event = FileChangeEvent(
            path=Path("/test/file.md"),
            change_type=ChangeType.DELETED,
            timestamp=time.time(),
        )

        service.sync_handler = None

        service._handle_file_change(event)

        assert service.status.sync_operations == 0

    def test_handle_file_change_exception(self, service):
        """Test file change handling with exception."""
        event = FileChangeEvent(
            path=Path("/test/file.md"),
            change_type=ChangeType.MODIFIED,
            timestamp=time.time(),
        )

        service.sync_handler.handle_file_change.side_effect = Exception("Sync error")

        service._handle_file_change(event)

        assert service.status.error_count == 1
        assert "Sync error" in service.status.last_error


class TestMonitoringServiceUtilities:
    """Test MonitoringService utility functions."""

    @pytest.fixture
    def service(self):
        """Create MonitoringService for testing."""
        config = CognitiveConfig(monitoring_enabled=True)

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"MONITORING_TARGET_PATH": tmp_dir}):
                yield MonitoringService(config=config)

    def test_is_service_running_no_pid_file(self, service):
        """Test service running check with no PID file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service.PID_FILE = str(Path(tmp_dir) / "nonexistent.pid")

            assert service._is_service_running() is False

    def test_is_service_running_invalid_pid(self, service):
        """Test service running check with invalid PID."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as pid_file:
            pid_file.write("invalid_pid")
            service.PID_FILE = pid_file.name

        try:
            assert service._is_service_running() is False
        finally:
            os.unlink(pid_file.name)

    @patch("psutil.pid_exists")
    def test_is_service_running_valid_pid(self, mock_pid_exists, service):
        """Test service running check with valid PID."""
        mock_pid_exists.return_value = True

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as pid_file:
            pid_file.write("12345")
            service.PID_FILE = pid_file.name

        try:
            assert service._is_service_running() is True
            mock_pid_exists.assert_called_once_with(12345)
        finally:
            os.unlink(pid_file.name)

    def test_write_pid_file(self, service):
        """Test PID file writing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service.PID_FILE = str(Path(tmp_dir) / "test.pid")

            service._write_pid_file()

            assert Path(service.PID_FILE).exists()
            with open(service.PID_FILE) as f:
                assert f.read().strip() == str(os.getpid())

    def test_remove_pid_file(self, service):
        """Test PID file removal."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service.PID_FILE = str(Path(tmp_dir) / "test.pid")

            # Create PID file first
            with open(service.PID_FILE, "w") as f:
                f.write("12345")

            assert Path(service.PID_FILE).exists()

            service._remove_pid_file()

            assert not Path(service.PID_FILE).exists()

    def test_should_restart_conditions(self, service):
        """Test restart condition logic."""
        # Test conditions where restart should happen
        service.status.error_count = 5
        service.status.started_at = time.time() - 120  # 2 minutes ago
        service._restart_attempts = 2

        assert service._should_restart() is True

        # Test condition where restart should not happen (too many attempts)
        service._restart_attempts = 10
        assert service._should_restart() is False

        # Test condition where restart should not happen (too recent)
        service._restart_attempts = 2
        service.status.started_at = time.time() - 30  # 30 seconds ago
        assert service._should_restart() is False

        # Test condition where restart should not happen (not enough errors)
        service.status.error_count = 1
        service.status.started_at = time.time() - 120
        assert service._should_restart() is False

    def test_attempt_restart_max_attempts(self, service):
        """Test restart attempt with max attempts reached."""
        service._restart_attempts = service.MAX_RESTART_ATTEMPTS

        result = service._attempt_restart()

        assert result is False

    @patch("time.sleep")
    def test_attempt_restart_with_backoff(self, mock_sleep, service):
        """Test restart attempt with exponential backoff."""
        service._restart_attempts = 2

        with patch.object(service, "restart", return_value=True):
            result = service._attempt_restart()

            assert result is True
            # Should sleep for 2^2 * 1.0 = 4.0 seconds
            mock_sleep.assert_called_once_with(4.0)


if __name__ == "__main__":
    pytest.main([__file__])
