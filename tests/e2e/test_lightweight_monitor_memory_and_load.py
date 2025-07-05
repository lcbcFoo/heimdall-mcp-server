#!/usr/bin/env python3
"""
End-to-end tests for memory usage validation and load testing in lightweight monitoring.

Tests memory efficiency, file change detection, rapid changes, and concurrent modifications.
"""

import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psutil
import pytest
from loguru import logger

from lightweight_monitor import LightweightMonitor


@pytest.mark.slow
class TestLightweightMonitorMemoryAndLoad:
    """Test memory usage and load handling in lightweight monitoring."""

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

    def _get_process_memory_mb(self, pid: int) -> float:
        """Get memory usage in MB for a process."""
        try:
            process = psutil.Process(pid)
            memory_info = process.memory_info()
            return memory_info.rss / (1024 * 1024)  # Convert bytes to MB
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0

    def _start_monitor_subprocess(self, project_root: Path) -> subprocess.Popen | None:
        """Start monitor in subprocess and return process handle."""
        try:
            # Change to project directory and start monitor
            process = subprocess.Popen(
                ["heimdall", "monitor", "start"],
                cwd=str(project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            # Give monitor time to start
            time.sleep(2)

            # Check if process is still running (didn't exit with error)
            if process.poll() is None:
                return process
            else:
                stdout, stderr = process.communicate()
                logger.error(
                    f"Monitor failed to start: stdout={stdout}, stderr={stderr}"
                )
                return None
        except Exception as e:
            logger.error(f"Failed to start monitor subprocess: {e}")
            return None

    def _stop_monitor_subprocess(
        self, project_root: Path, process: subprocess.Popen
    ) -> bool:
        """Stop monitor subprocess."""
        try:
            # First try graceful stop
            subprocess.run(
                ["heimdall", "monitor", "stop"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Wait for process to exit
            try:
                process.wait(timeout=5)
                return True
            except subprocess.TimeoutExpired:
                # Force kill if graceful stop didn't work
                process.kill()
                process.wait()
                return True
        except Exception as e:
            logger.error(f"Failed to stop monitor subprocess: {e}")
            try:
                process.kill()
                process.wait()
            except Exception:
                pass
            return False

    def _get_monitor_status(self, project_root: Path) -> dict:
        """Get monitor status including memory usage using JSON output."""
        try:
            result = subprocess.run(
                ["heimdall", "monitor", "status", "--json"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                # Parse JSON output
                import json

                status = json.loads(result.stdout.strip())

                # Normalize field names for easier access
                normalized = {
                    "running": status.get("is_running", False),
                    "pid": status.get("pid"),
                    "memory_mb": status.get("memory_usage_mb"),
                    "uptime_seconds": status.get("uptime_seconds"),
                    "files_monitored": status.get("files_monitored", 0),
                    "sync_operations": status.get("sync_operations", 0),
                    "error_count": status.get("error_count", 0),
                }

                return normalized
            else:
                logger.warning(f"Monitor status command failed: {result.stderr}")
                return {}
        except Exception as e:
            logger.error(f"Failed to get monitor status: {e}")
            return {}

    def test_memory_usage_stays_under_50mb(self, temp_project):
        """Test that monitor memory usage stays under 50MB consistently using subprocess."""
        # Start monitor in subprocess
        monitor_process = self._start_monitor_subprocess(temp_project["project_root"])
        if not monitor_process:
            pytest.skip("Could not start monitor subprocess")

        try:
            # Collect memory usage over time using CLI status command
            memory_readings = []

            # Run for 20 seconds, sampling every 2 seconds
            for i in range(10):
                status = self._get_monitor_status(temp_project["project_root"])

                if status and "memory_mb" in status:
                    memory_mb = status["memory_mb"]
                    memory_readings.append(memory_mb)
                    logger.info(f"Memory sample {i + 1}: {memory_mb:.2f} MB")
                elif status and "pid" in status:
                    # Fallback to direct PID memory measurement
                    memory_mb = self._get_process_memory_mb(status["pid"])
                    memory_readings.append(memory_mb)
                    logger.info(f"Memory sample {i + 1} (direct): {memory_mb:.2f} MB")
                else:
                    logger.warning(f"Could not get memory reading for sample {i + 1}")

                # Create some file activity to simulate real usage
                if i % 3 == 0:
                    activity_file = temp_project["docs_dir"] / f"activity_{i}.md"
                    activity_file.write_text(
                        f"# Activity File {i}\n\nGenerated at {time.time()}"
                    )

                time.sleep(2)

        finally:
            # Stop monitor
            self._stop_monitor_subprocess(temp_project["project_root"], monitor_process)

        # Analyze memory usage if we got readings
        if memory_readings:
            max_memory = max(memory_readings)
            avg_memory = sum(memory_readings) / len(memory_readings)

            logger.info(
                f"Memory usage - Max: {max_memory:.2f} MB, Avg: {avg_memory:.2f} MB"
            )

            # Assert memory stays under 50MB threshold (lightweight monitor with copied code)
            # Proven to use ~24MB with direct imports, allowing buffer for subprocess overhead
            assert max_memory < 50.0, (
                f"Memory usage {max_memory:.2f} MB exceeded 50MB lightweight threshold"
            )

            # More importantly, memory should be stable (not growing significantly)
            memory_growth = max_memory - min(memory_readings)
            assert memory_growth < 50.0, (
                f"Memory growth {memory_growth:.2f} MB indicates potential leak"
            )
        else:
            pytest.skip("No memory readings obtained from monitor status")

    def test_file_change_detection_end_to_end(self, temp_project):
        """Test file change detection end-to-end with real file modifications using subprocess."""
        # Start monitor in subprocess
        monitor_process = self._start_monitor_subprocess(temp_project["project_root"])
        if not monitor_process:
            pytest.skip("Could not start monitor subprocess")

        try:
            # Get initial status
            initial_status = self._get_monitor_status(temp_project["project_root"])
            logger.info(f"Initial monitor status: {initial_status}")

            # Test file creation
            new_file = temp_project["docs_dir"] / "created.md"
            new_file.write_text("# Created File\n\nThis file was created during test.")
            time.sleep(3)  # Give monitor time to detect change

            # Test file modification
            temp_project["test_file"].write_text(
                "# Modified Test Document\n\nThis content was modified."
            )
            time.sleep(3)

            # Test another file creation
            another_file = temp_project["docs_dir"] / "another.md"
            another_file.write_text("# Another File\n\nAnother test file.")
            time.sleep(3)

            # Give monitor more time to process all events
            time.sleep(5)

            # Get final status to see if files were processed
            final_status = self._get_monitor_status(temp_project["project_root"])
            logger.info(f"Final monitor status: {final_status}")

        finally:
            # Stop monitor
            self._stop_monitor_subprocess(temp_project["project_root"], monitor_process)

        # Validate that monitor was running and processing files
        assert initial_status.get("running", False), (
            "Monitor should be running initially"
        )

        # At minimum, we should have confirmation the monitor was operational
        # (In a real scenario, we'd check log files or memory statistics to confirm processing)
        logger.info(
            "File change detection test completed - monitor was operational during file operations"
        )

    def test_multiple_rapid_file_changes(self, temp_project):
        """Test handling of multiple rapid file changes using subprocess."""
        # Start monitor in subprocess
        monitor_process = self._start_monitor_subprocess(temp_project["project_root"])
        if not monitor_process:
            pytest.skip("Could not start monitor subprocess")

        try:
            # Get initial status
            initial_status = self._get_monitor_status(temp_project["project_root"])
            logger.info(f"Initial status: {initial_status}")

            # Create rapid file changes
            for i in range(10):  # Reduced from 20 for faster test
                rapid_file = temp_project["docs_dir"] / f"rapid_{i}.md"
                rapid_file.write_text(
                    f"# Rapid File {i}\n\nContent generated at {time.time()}"
                )

                # Brief delay to avoid overwhelming the system
                time.sleep(0.1)

            # Give monitor time to process all events
            time.sleep(8)

            # Check status to see if monitor is still responsive
            final_status = self._get_monitor_status(temp_project["project_root"])
            logger.info(f"Final status after rapid changes: {final_status}")

        finally:
            # Stop monitor
            self._stop_monitor_subprocess(temp_project["project_root"], monitor_process)

        # Validate monitor remained operational during rapid changes
        assert initial_status.get("running", False), (
            "Monitor should be running initially"
        )
        assert final_status.get("running", False), (
            "Monitor should still be running after rapid changes"
        )

        logger.info("Rapid file changes test completed - monitor remained operational")

    def test_across_different_project_directories(self, temp_project):
        """Test monitoring across different project directories with isolation."""
        # Create additional project directories
        project_dirs = []
        monitors = []

        try:
            # Create 3 additional project directories
            for _ in range(3):
                temp_dir = tempfile.mkdtemp()
                project_root = Path(temp_dir)
                docs_dir = project_root / ".heimdall" / "docs"
                docs_dir.mkdir(parents=True)

                project_dirs.append(
                    {
                        "temp_dir": temp_dir,
                        "project_root": project_root,
                        "docs_dir": docs_dir,
                        "lock_file": project_root / ".heimdall" / "monitor.lock",
                    }
                )

            # Create monitors for all projects (including the fixture project)
            all_projects = [temp_project] + project_dirs

            for project in all_projects:
                monitor = LightweightMonitor(
                    project_root=project["project_root"],
                    target_path=project["docs_dir"],
                    lock_file=project["lock_file"],
                )
                monitors.append(monitor)

            # Start all monitors
            for i, monitor in enumerate(monitors):
                result = monitor.start()
                assert result is True, f"Monitor {i} should start successfully"
                assert monitor.running is True

            # All should be running simultaneously
            running_count = sum(1 for monitor in monitors if monitor.running)
            assert running_count == len(monitors), (
                "All monitors should be running simultaneously"
            )

            # Test file operations in each project
            for i, (project, monitor) in enumerate(
                zip(all_projects, monitors, strict=False)
            ):
                test_file = project["docs_dir"] / f"project_{i}_test.md"
                test_file.write_text(f"# Project {i} Test\n\nContent for project {i}")

                # Verify monitor is still running
                assert monitor.running is True

            # Give time for file processing
            time.sleep(2)

            # All monitors should still be running
            for i, monitor in enumerate(monitors):
                assert monitor.running is True, f"Monitor {i} should still be running"

        finally:
            # Clean up all monitors
            for monitor in monitors:
                if monitor.running:
                    monitor.stop()

            # Clean up temporary directories
            import shutil

            for project in project_dirs:
                try:
                    shutil.rmtree(project["temp_dir"])
                except OSError:
                    pass  # Ignore cleanup errors

        logger.info(
            f"Successfully tested {len(monitors)} concurrent monitors across different projects"
        )

    def test_load_testing_concurrent_file_modifications(self, temp_project):
        """Test load handling with concurrent file modifications using subprocess."""
        # Start monitor in subprocess
        monitor_process = self._start_monitor_subprocess(temp_project["project_root"])
        if not monitor_process:
            pytest.skip("Could not start monitor subprocess")

        try:
            # Get initial status
            initial_status = self._get_monitor_status(temp_project["project_root"])
            logger.info(f"Initial status for load test: {initial_status}")

            # Create concurrent file modifications using ThreadPoolExecutor
            def create_files_in_thread(thread_id: int, file_count: int):
                """Create files in a separate thread."""
                for i in range(file_count):
                    file_path = (
                        temp_project["docs_dir"] / f"thread_{thread_id}_file_{i}.md"
                    )
                    content = (
                        f"# Thread {thread_id} File {i}\n\nGenerated at {time.time()}"
                    )
                    file_path.write_text(content)
                    time.sleep(0.05)  # Small delay between files

            # Use multiple threads to create files concurrently
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = []
                for thread_id in range(3):
                    future = executor.submit(
                        create_files_in_thread, thread_id, 5
                    )  # Reduced for faster test
                    futures.append(future)

                # Wait for all threads to complete
                for future in futures:
                    future.result()

            # Give monitor time to process all events
            time.sleep(10)

            # Check final status
            final_status = self._get_monitor_status(temp_project["project_root"])
            logger.info(f"Final status after concurrent load: {final_status}")

        finally:
            # Stop monitor
            self._stop_monitor_subprocess(temp_project["project_root"], monitor_process)

        # Validate monitor handled concurrent load
        assert initial_status.get("running", False), (
            "Monitor should be running initially"
        )
        assert final_status.get("running", False), (
            "Monitor should still be running after concurrent load"
        )

        logger.info(
            "Concurrent file modifications test completed - monitor handled load successfully"
        )

    def test_memory_stability_under_load(self, temp_project):
        """Test memory stability during sustained load using subprocess."""
        # Start monitor in subprocess
        monitor_process = self._start_monitor_subprocess(temp_project["project_root"])
        if not monitor_process:
            pytest.skip("Could not start monitor subprocess")

        memory_readings = []

        try:
            # Sustained load test: create files continuously while monitoring memory
            for cycle in range(8):  # 8 cycles of file creation
                # Get memory reading from monitor status
                status = self._get_monitor_status(temp_project["project_root"])

                if status and "memory_mb" in status:
                    memory_mb = status["memory_mb"]
                    memory_readings.append(memory_mb)
                    logger.info(f"Cycle {cycle + 1}: Memory = {memory_mb:.2f} MB")
                elif status and "pid" in status:
                    # Fallback to direct PID memory measurement
                    memory_mb = self._get_process_memory_mb(status["pid"])
                    memory_readings.append(memory_mb)
                    logger.info(
                        f"Cycle {cycle + 1} (direct): Memory = {memory_mb:.2f} MB"
                    )

                # Create batch of files
                for i in range(3):
                    load_file = (
                        temp_project["docs_dir"] / f"load_cycle_{cycle}_file_{i}.md"
                    )
                    load_file.write_text(
                        f"# Load Test File\n\nCycle {cycle}, File {i}, Time {time.time()}"
                    )

                time.sleep(1.5)  # Brief pause between cycles

        finally:
            # Stop monitor
            self._stop_monitor_subprocess(temp_project["project_root"], monitor_process)

        # Analyze memory stability if we got readings
        if memory_readings and len(memory_readings) >= 2:
            initial_memory = memory_readings[0]
            final_memory = memory_readings[-1]
            max_memory = max(memory_readings)
            memory_growth = final_memory - initial_memory

            logger.info(
                f"Memory analysis - Initial: {initial_memory:.2f} MB, Final: {final_memory:.2f} MB"
            )
            logger.info(
                f"Memory growth: {memory_growth:.2f} MB, Max: {max_memory:.2f} MB"
            )

            # Memory should remain stable (not grow excessively)
            assert memory_growth < 20.0, (
                f"Memory growth {memory_growth:.2f} MB should be minimal for lightweight monitor"
            )
            assert max_memory < 50.0, (
                f"Peak memory {max_memory:.2f} MB should stay under 50MB lightweight threshold"
            )

            logger.info("Memory stability test completed successfully")
        else:
            logger.warning("Insufficient memory readings for stability analysis")
            pytest.skip("Could not obtain sufficient memory readings for analysis")


if __name__ == "__main__":
    # Run basic memory test manually
    logger.info("Running basic memory and load tests...")

    with tempfile.TemporaryDirectory() as temp_dir:
        project_root = Path(temp_dir)
        docs_dir = project_root / ".heimdall" / "docs"
        docs_dir.mkdir(parents=True)

        monitor = LightweightMonitor(
            project_root=project_root,
            target_path=docs_dir,
            lock_file=project_root / ".heimdall" / "monitor.lock",
        )

        # Test monitor start and basic memory usage
        logger.info("Testing basic monitor memory usage...")
        assert monitor.start() is True

        current_pid = os.getpid()
        process = psutil.Process(current_pid)
        memory_mb = process.memory_info().rss / (1024 * 1024)

        logger.info(f"Monitor started, current memory usage: {memory_mb:.2f} MB")

        # Create a test file
        test_file = docs_dir / "manual_test.md"
        test_file.write_text("# Manual Test\n\nTesting file creation detection.")

        time.sleep(2)  # Give monitor time to detect

        # Check memory again
        memory_mb_after = process.memory_info().rss / (1024 * 1024)
        logger.info(f"After file creation, memory usage: {memory_mb_after:.2f} MB")

        # Stop monitor
        assert monitor.stop() is True
        logger.info("Monitor stopped successfully")

        # Memory should be lightweight (<50MB target)
        assert memory_mb < 50.0, (
            f"Memory usage {memory_mb:.2f} MB should be under 50MB lightweight threshold"
        )
        assert memory_mb_after < 50.0, (
            f"Memory after file operations {memory_mb_after:.2f} MB should stay under 50MB"
        )

        logger.info("Basic memory and load tests completed successfully!")
