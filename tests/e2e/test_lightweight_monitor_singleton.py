#!/usr/bin/env python3
"""
End-to-end tests for singleton enforcement and resource management in lightweight monitoring.

Tests singleton lock behavior, resource cleanup, and edge cases.
"""

import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from loguru import logger

from lightweight_monitor import (
    LightweightMonitor,
    LightweightMonitorError,
    SingletonLock,
)


class TestLightweightMonitorSingleton:
    """Test singleton enforcement and resource management."""

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

    def test_singleton_lock_basic_functionality(self, temp_project):
        """Test basic singleton lock acquire and release."""
        lock_file = temp_project["lock_file"]

        # First lock should succeed
        with SingletonLock(lock_file) as lock1:
            assert lock1.locked is True
            assert lock_file.exists()

            # Read PID from lock file
            pid_content = lock_file.read_text().strip()
            assert pid_content == str(os.getpid())

            # Second lock should fail
            with pytest.raises(LightweightMonitorError, match="already running"):
                with SingletonLock(lock_file):
                    pass

        # After context exit, lock file should be cleaned up
        assert not lock_file.exists()

    def test_singleton_lock_exception_cleanup(self, temp_project):
        """Test that singleton lock cleans up properly on exceptions."""
        lock_file = temp_project["lock_file"]

        try:
            with SingletonLock(lock_file) as lock:
                assert lock.locked is True
                assert lock_file.exists()
                # Simulate exception inside context
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Lock file should be cleaned up even after exception
        assert not lock_file.exists()

    def test_singleton_lock_stale_lock_handling(self, temp_project):
        """Test handling of stale lock files from crashed processes."""
        lock_file = temp_project["lock_file"]

        # Create stale lock file with non-existent PID
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_file.write_text("99999")  # Very unlikely to be a real PID

        # portalocker should detect the stale lock and allow acquisition
        # (this is the correct behavior - portalocker handles stale locks from dead processes)
        with SingletonLock(lock_file) as lock:
            assert lock.locked is True
            assert lock_file.exists()

            # PID should be updated to current process
            pid_content = lock_file.read_text().strip()
            assert pid_content == str(os.getpid())

        # Lock file should be cleaned up
        assert not lock_file.exists()

    def test_singleton_lock_concurrent_access(self, temp_project):
        """Test concurrent access to singleton lock."""
        lock_file = temp_project["lock_file"]
        results = []

        def try_acquire_lock():
            """Try to acquire lock in separate thread."""
            try:
                with SingletonLock(lock_file):
                    results.append("acquired")
                    time.sleep(0.5)  # Hold lock briefly
            except LightweightMonitorError:
                results.append("failed")

        # Start multiple threads trying to acquire lock
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=try_acquire_lock)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Only one should succeed, others should fail
        assert results.count("acquired") == 1
        assert results.count("failed") == 2

        # Lock file should be cleaned up
        assert not lock_file.exists()

    def test_multiple_monitor_instances_same_project(self, temp_project):
        """Test that multiple monitor instances in same project are prevented."""
        monitor1 = LightweightMonitor(
            project_root=temp_project["project_root"],
            target_path=temp_project["docs_dir"],
            lock_file=temp_project["lock_file"],
        )

        monitor2 = LightweightMonitor(
            project_root=temp_project["project_root"],
            target_path=temp_project["docs_dir"],
            lock_file=temp_project["lock_file"],
        )

        # First monitor should start successfully
        assert monitor1.start() is True
        assert monitor1.running is True

        # Second monitor should fail to start
        assert monitor2.start() is False
        assert monitor2.running is False

        # Clean up first monitor
        assert monitor1.stop() is True
        assert not temp_project["lock_file"].exists()

    def test_monitor_start_stop_lifecycle(self, temp_project):
        """Test monitor start/stop lifecycle and resource cleanup."""
        monitor = LightweightMonitor(
            project_root=temp_project["project_root"],
            target_path=temp_project["docs_dir"],
            lock_file=temp_project["lock_file"],
        )

        # Initial state
        assert monitor.running is False
        assert monitor.singleton_lock is None

        # Start monitor
        assert monitor.start() is True
        assert monitor.running is True
        assert monitor.singleton_lock is not None
        assert monitor.singleton_lock.locked is True
        assert temp_project["lock_file"].exists()

        # Stop monitor
        assert monitor.stop() is True
        assert monitor.running is False
        assert monitor.singleton_lock is None
        assert not temp_project["lock_file"].exists()

    def test_monitor_signal_handling(self, temp_project):
        """Test monitor signal handling and graceful shutdown."""
        monitor = LightweightMonitor(
            project_root=temp_project["project_root"],
            target_path=temp_project["docs_dir"],
            lock_file=temp_project["lock_file"],
        )

        # Start monitor
        assert monitor.start() is True

        # Test signal handler registration
        assert monitor.signal_handler._handlers_registered is True

        # Simulate SIGTERM
        monitor.signal_handler.shutdown_event.set()

        # Should detect shutdown request
        assert monitor.signal_handler.is_shutdown_requested() is True

        # Stop monitor
        assert monitor.stop() is True
        assert not temp_project["lock_file"].exists()

    def test_monitor_processing_thread_lifecycle(self, temp_project):
        """Test that processing thread starts and stops properly."""
        monitor = LightweightMonitor(
            project_root=temp_project["project_root"],
            target_path=temp_project["docs_dir"],
            lock_file=temp_project["lock_file"],
        )

        # Start monitor
        assert monitor.start() is True

        # Processing thread should be created and started
        assert monitor.processing_thread is not None
        assert monitor.processing_thread.name == "EventProcessor"

        # File watcher should be initialized
        assert monitor.file_watcher is not None

        # Monitor should be running
        assert monitor.running is True

        # Stop monitor
        assert monitor.stop() is True

        # Processing thread should stop within timeout
        # (The thread may exit immediately due to no events, which is expected behavior)
        assert not monitor.processing_thread.is_alive()

    def test_monitor_statistics_initialization(self, temp_project):
        """Test that monitor statistics are properly initialized."""
        monitor = LightweightMonitor(
            project_root=temp_project["project_root"],
            target_path=temp_project["docs_dir"],
            lock_file=temp_project["lock_file"],
        )

        # Check initial statistics
        stats = monitor.get_status()
        assert stats["running"] is False
        assert stats["pid"] is None
        assert stats["started_at"] is None
        assert stats["files_processed"] == 0
        assert stats["subprocess_calls"] == 0
        assert stats["subprocess_errors"] == 0

        # Start monitor
        assert monitor.start() is True

        # Check statistics after start
        stats = monitor.get_status()
        assert stats["running"] is True
        assert stats["pid"] == os.getpid()
        assert stats["started_at"] is not None
        assert stats["uptime_seconds"] is not None
        assert stats["uptime_seconds"] >= 0

        # Stop monitor
        assert monitor.stop() is True

    def test_lock_file_permissions_and_creation(self, temp_project):
        """Test lock file creation and permissions."""
        # Test with nested directory structure
        deep_lock_file = (
            temp_project["project_root"] / "deep" / "nested" / "path" / "monitor.lock"
        )

        with SingletonLock(deep_lock_file) as lock:
            assert lock.locked is True
            assert deep_lock_file.exists()
            assert deep_lock_file.parent.exists()

            # Check that we can read the lock file
            pid_content = deep_lock_file.read_text().strip()
            assert pid_content == str(os.getpid())

        # Directory structure should remain, but lock file should be gone
        assert deep_lock_file.parent.exists()
        assert not deep_lock_file.exists()

    def test_monitor_file_watcher_integration(self, temp_project):
        """Test that file watcher is properly integrated with monitor."""
        monitor = LightweightMonitor(
            project_root=temp_project["project_root"],
            target_path=temp_project["docs_dir"],
            lock_file=temp_project["lock_file"],
        )

        # Start monitor
        assert monitor.start() is True

        # File watcher should be initialized
        assert monitor.file_watcher is not None
        assert monitor.file_watcher.event_queue is not None

        # Should be monitoring the target path
        monitored_files = monitor.file_watcher.get_monitored_files()
        # The actual file set depends on what files exist in docs_dir
        assert isinstance(monitored_files, set)

        # Stop monitor
        assert monitor.stop() is True

    def test_monitor_restart_after_stop(self, temp_project):
        """Test that monitor can be restarted after being stopped."""
        monitor = LightweightMonitor(
            project_root=temp_project["project_root"],
            target_path=temp_project["docs_dir"],
            lock_file=temp_project["lock_file"],
        )

        # First start/stop cycle
        assert monitor.start() is True
        assert monitor.running is True
        assert monitor.stop() is True
        assert monitor.running is False
        assert not temp_project["lock_file"].exists()

        # Second start/stop cycle should work
        assert monitor.start() is True
        assert monitor.running is True
        assert monitor.stop() is True
        assert monitor.running is False
        assert not temp_project["lock_file"].exists()

    def test_monitor_start_failure_cleanup(self, temp_project):
        """Test that failed monitor start properly cleans up resources."""
        monitor = LightweightMonitor(
            project_root=temp_project["project_root"],
            target_path=temp_project["docs_dir"],
            lock_file=temp_project["lock_file"],
        )

        # Mock MarkdownFileWatcher to raise exception during start
        with patch("lightweight_monitor.MarkdownFileWatcher") as mock_watcher_class:
            mock_watcher_class.side_effect = Exception(
                "Test exception during file watcher creation"
            )

            # Monitor start should fail
            assert monitor.start() is False
            assert monitor.running is False

            # Resources should be cleaned up
            assert monitor.singleton_lock is None
            assert not temp_project["lock_file"].exists()

    def test_multiple_projects_different_locks(self, temp_project):
        """Test that different projects can run simultaneously with different lock files."""
        # Create second project directory
        with tempfile.TemporaryDirectory() as temp_dir2:
            project_root2 = Path(temp_dir2)
            docs_dir2 = project_root2 / ".heimdall" / "docs"
            docs_dir2.mkdir(parents=True)
            lock_file2 = project_root2 / ".heimdall" / "monitor.lock"

            # Create monitors for both projects
            monitor1 = LightweightMonitor(
                project_root=temp_project["project_root"],
                target_path=temp_project["docs_dir"],
                lock_file=temp_project["lock_file"],
            )

            monitor2 = LightweightMonitor(
                project_root=project_root2, target_path=docs_dir2, lock_file=lock_file2
            )

            # Both should start successfully (different lock files)
            assert monitor1.start() is True
            assert monitor2.start() is True

            # Both should be running
            assert monitor1.running is True
            assert monitor2.running is True

            # Both lock files should exist
            assert temp_project["lock_file"].exists()
            assert lock_file2.exists()

            # Stop both monitors
            assert monitor1.stop() is True
            assert monitor2.stop() is True

            # Both lock files should be cleaned up
            assert not temp_project["lock_file"].exists()
            assert not lock_file2.exists()


class TestSingletonLockEdgeCases:
    """Test edge cases for singleton lock behavior."""

    def test_lock_file_directory_creation(self):
        """Test that lock file directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Lock file in non-existent directory
            lock_file = Path(temp_dir) / "non" / "existent" / "path" / "test.lock"

            with SingletonLock(lock_file) as lock:
                assert lock.locked is True
                assert lock_file.exists()
                assert lock_file.parent.exists()

            # Directory should remain, lock file should be gone
            assert lock_file.parent.exists()
            assert not lock_file.exists()

    def test_lock_file_permission_errors(self):
        """Test handling of permission errors when creating lock file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a directory with restricted permissions
            restricted_dir = Path(temp_dir) / "restricted"
            restricted_dir.mkdir(mode=0o000)  # No permissions

            try:
                lock_file = restricted_dir / "test.lock"

                # Should raise LightweightMonitorError due to permission denied
                with pytest.raises(
                    LightweightMonitorError, match="Failed to acquire singleton lock"
                ):
                    with SingletonLock(lock_file):
                        pass

            finally:
                # Restore permissions for cleanup
                restricted_dir.chmod(0o755)

    def test_lock_file_cleanup_on_various_exceptions(self):
        """Test that lock file cleanup works with various exception types."""
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_file = Path(temp_dir) / "test.lock"

            # Test with different exception types
            exception_types = [
                ValueError("Test value error"),
                RuntimeError("Test runtime error"),
                KeyboardInterrupt(),
                SystemExit(1),
            ]

            for exception in exception_types:
                try:
                    with SingletonLock(lock_file):
                        assert lock_file.exists()
                        raise exception
                except (ValueError, RuntimeError, KeyboardInterrupt, SystemExit):
                    pass

                # Lock file should be cleaned up regardless of exception type
                assert not lock_file.exists()


if __name__ == "__main__":
    # Run basic tests manually
    logger.info("Running basic singleton enforcement tests...")

    with tempfile.TemporaryDirectory() as temp_dir:
        project_root = Path(temp_dir)
        docs_dir = project_root / ".heimdall" / "docs"
        docs_dir.mkdir(parents=True)
        lock_file = project_root / ".heimdall" / "monitor.lock"

        # Test basic singleton lock
        logger.info("Testing basic singleton lock...")
        with SingletonLock(lock_file) as lock:
            logger.info(f"Lock acquired: {lock.locked}")
            assert lock.locked is True
            assert lock_file.exists()

        logger.info(f"Lock file cleaned up: {not lock_file.exists()}")
        assert not lock_file.exists()

        # Test monitor singleton enforcement
        logger.info("Testing monitor singleton enforcement...")
        monitor1 = LightweightMonitor(
            project_root=project_root, target_path=docs_dir, lock_file=lock_file
        )

        monitor2 = LightweightMonitor(
            project_root=project_root, target_path=docs_dir, lock_file=lock_file
        )

        # First should start
        result1 = monitor1.start()
        logger.info(f"Monitor 1 start result: {result1}")
        assert result1 is True

        # Second should fail
        result2 = monitor2.start()
        logger.info(f"Monitor 2 start result: {result2}")
        assert result2 is False

        # Cleanup
        stop_result = monitor1.stop()
        logger.info(f"Monitor 1 stop result: {stop_result}")
        assert stop_result is True

        logger.info("Basic singleton enforcement tests completed successfully!")
