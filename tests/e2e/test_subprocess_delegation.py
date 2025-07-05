#!/usr/bin/env python3
"""
End-to-end tests for subprocess delegation in lightweight monitoring.

Tests various file change scenarios to validate subprocess execution.
"""

import tempfile
import time
from pathlib import Path

import pytest
from loguru import logger

from lightweight_monitor import ChangeType, FileChangeEvent, LightweightMonitor


class TestSubprocessDelegation:
    """Test subprocess delegation functionality."""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            docs_dir = project_root / ".heimdall" / "docs"
            docs_dir.mkdir(parents=True)

            # Create test markdown file
            test_file = docs_dir / "test.md"
            test_file.write_text("# Test Document\n\nThis is a test.")

            yield {
                "project_root": project_root,
                "docs_dir": docs_dir,
                "test_file": test_file,
                "lock_file": project_root / ".heimdall" / "monitor.lock",
            }

    def test_subprocess_command_mapping(self, temp_project):
        """Test that file change events map to correct CLI commands."""
        monitor = LightweightMonitor(
            project_root=temp_project["project_root"],
            target_path=temp_project["docs_dir"],
            lock_file=temp_project["lock_file"],
        )

        # Test ADDED event
        added_event = FileChangeEvent(
            path=temp_project["test_file"],
            change_type=ChangeType.ADDED,
            timestamp=time.time(),
        )
        cmd = monitor._build_subprocess_command(added_event)
        assert cmd == ["heimdall", "load", str(temp_project["test_file"])]

        # Test MODIFIED event
        modified_event = FileChangeEvent(
            path=temp_project["test_file"],
            change_type=ChangeType.MODIFIED,
            timestamp=time.time(),
        )
        cmd = monitor._build_subprocess_command(modified_event)
        assert cmd == ["heimdall", "load", str(temp_project["test_file"])]

        # Test DELETED event
        deleted_event = FileChangeEvent(
            path=temp_project["test_file"],
            change_type=ChangeType.DELETED,
            timestamp=time.time(),
        )
        cmd = monitor._build_subprocess_command(deleted_event)
        assert cmd == ["heimdall", "remove-file", str(temp_project["test_file"])]

    def test_permanent_failure_detection(self, temp_project):
        """Test detection of permanent failures that shouldn't be retried."""
        monitor = LightweightMonitor(
            project_root=temp_project["project_root"],
            target_path=temp_project["docs_dir"],
            lock_file=temp_project["lock_file"],
        )

        # Test command not found
        assert monitor._is_permanent_failure(127, "command not found") is True

        # Test permission denied
        assert monitor._is_permanent_failure(126, "permission denied") is True

        # Test file not found
        assert monitor._is_permanent_failure(1, "no such file or directory") is True

        # Test temporary failure (connection error, etc.)
        assert monitor._is_permanent_failure(1, "connection refused") is False

        # Test success
        assert monitor._is_permanent_failure(0, "") is False

    def test_subprocess_execution_with_invalid_command(self, temp_project):
        """Test subprocess execution with invalid command (should not retry)."""
        monitor = LightweightMonitor(
            project_root=temp_project["project_root"],
            target_path=temp_project["docs_dir"],
            lock_file=temp_project["lock_file"],
        )

        # Set low retry count for faster test
        monitor.max_retries = 1
        monitor.retry_delay = 0.1
        monitor.subprocess_timeout = 5

        # Test with invalid command
        event = FileChangeEvent(
            path=temp_project["test_file"],
            change_type=ChangeType.ADDED,
            timestamp=time.time(),
        )

        # Replace heimdall with invalid command
        original_method = monitor._build_subprocess_command

        def mock_build_command(event):
            return ["invalid_command_xyz", "load", str(event.path)]

        monitor._build_subprocess_command = mock_build_command

        # Should fail without retries (permanent failure)
        start_time = time.time()
        result = monitor._execute_subprocess_with_retry(
            ["invalid_command_xyz", "load", str(temp_project["test_file"])], event
        )
        execution_time = time.time() - start_time

        assert result is False
        # Should complete quickly (no retries for permanent failure)
        assert execution_time < 2.0

        # Restore original method
        monitor._build_subprocess_command = original_method

    def test_subprocess_timeout_handling(self, temp_project):
        """Test subprocess timeout handling and retry logic."""
        monitor = LightweightMonitor(
            project_root=temp_project["project_root"],
            target_path=temp_project["docs_dir"],
            lock_file=temp_project["lock_file"],
        )

        # Set very short timeout for testing
        monitor.max_retries = 1
        monitor.retry_delay = 0.1
        monitor.subprocess_timeout = 0.1  # Very short timeout

        # Test with command that will timeout (sleep)
        event = FileChangeEvent(
            path=temp_project["test_file"],
            change_type=ChangeType.ADDED,
            timestamp=time.time(),
        )

        # Use sleep command that will timeout
        start_time = time.time()
        result = monitor._execute_subprocess_with_retry(
            ["sleep", "1"],  # Sleep for 1 second (will timeout at 0.1s)
            event,
        )
        execution_time = time.time() - start_time

        assert result is False
        # Should have attempted retries
        assert monitor.stats["subprocess_timeouts"] > 0
        # Should complete in reasonable time (with retry delays)
        assert 0.3 < execution_time < 3.0

    def test_statistics_tracking(self, temp_project):
        """Test that subprocess statistics are properly tracked."""
        monitor = LightweightMonitor(
            project_root=temp_project["project_root"],
            target_path=temp_project["docs_dir"],
            lock_file=temp_project["lock_file"],
        )

        # Initial stats should be zero
        assert monitor.stats["subprocess_calls"] == 0
        assert monitor.stats["subprocess_errors"] == 0
        assert monitor.stats["subprocess_retries"] == 0
        assert monitor.stats["subprocess_timeouts"] == 0

        # Test successful command (echo)
        event = FileChangeEvent(
            path=temp_project["test_file"],
            change_type=ChangeType.ADDED,
            timestamp=time.time(),
        )

        result = monitor._execute_subprocess_with_retry(["echo", "test"], event)

        assert result is True
        assert monitor.stats["subprocess_calls"] == 1
        assert monitor.stats["subprocess_errors"] == 0

        # Test failed command
        result = monitor._execute_subprocess_with_retry(
            ["false"],  # Command that always fails
            event,
        )

        assert result is False
        # Should have incremented calls but not retries (permanent failure)
        assert monitor.stats["subprocess_calls"] > 1

    def test_configuration_parameters(self, temp_project):
        """Test that configuration parameters are properly set."""
        monitor = LightweightMonitor(
            project_root=temp_project["project_root"],
            target_path=temp_project["docs_dir"],
            lock_file=temp_project["lock_file"],
        )

        # Check default configuration
        assert monitor.max_retries == 3
        assert monitor.retry_delay == 2.0
        assert monitor.subprocess_timeout == 300

        # Test configuration modification
        monitor.max_retries = 5
        monitor.retry_delay = 1.0
        monitor.subprocess_timeout = 600

        assert monitor.max_retries == 5
        assert monitor.retry_delay == 1.0
        assert monitor.subprocess_timeout == 600


if __name__ == "__main__":
    # Run basic test manually
    logger.info("Running basic subprocess delegation tests...")

    with tempfile.TemporaryDirectory() as temp_dir:
        project_root = Path(temp_dir)
        docs_dir = project_root / ".heimdall" / "docs"
        docs_dir.mkdir(parents=True)

        monitor = LightweightMonitor(
            project_root=project_root,
            target_path=docs_dir,
            lock_file=project_root / ".heimdall" / "monitor.lock",
        )

        # Test command building
        test_file = docs_dir / "test.md"
        event = FileChangeEvent(
            path=test_file, change_type=ChangeType.ADDED, timestamp=time.time()
        )

        cmd = monitor._build_subprocess_command(event)
        logger.info(f"Generated command for ADDED event: {cmd}")

        # Test permanent failure detection
        is_permanent = monitor._is_permanent_failure(127, "command not found")
        logger.info(f"Command not found is permanent failure: {is_permanent}")

        # Test simple subprocess execution (echo command)
        result = monitor._execute_subprocess_with_retry(["echo", "test"], event)
        logger.info(f"Echo command execution result: {result}")

        logger.info("Basic tests completed successfully!")
