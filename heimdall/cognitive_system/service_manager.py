"""
Service management for cognitive memory system dependencies.

This module provides automated management of external services required by the
cognitive memory system, with a focus on Qdrant vector database management.
"""

import shutil
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import psutil
import requests

from cognitive_memory.core.config import QdrantConfig

try:
    import docker
    import docker.errors

    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    docker = None


class ServiceStatus(Enum):
    """Service status enumeration."""

    RUNNING = "running"
    STOPPED = "stopped"
    UNKNOWN = "unknown"
    ERROR = "error"


@dataclass
class QdrantStatus:
    """Qdrant service status information."""

    status: ServiceStatus
    port: int | None = None
    pid: int | None = None
    container_id: str | None = None
    uptime_seconds: int | None = None
    health_status: str | None = None
    error: str | None = None


class QdrantManager:
    """
    Manages Qdrant vector database service lifecycle.

    Provides automatic service management with Docker-first approach
    and local binary fallback for environments without Docker.
    """

    def __init__(self) -> None:
        """Initialize Qdrant service manager."""
        self.container_name = "heimdall-shared-qdrant"
        self.default_config = QdrantConfig()
        self.default_port = 6333  # Fixed port for shared instance
        self.default_data_dir = Path("./data/qdrant")
        self.docker_client = None

        if DOCKER_AVAILABLE and docker is not None:
            try:
                self.docker_client = docker.from_env()
                # Test Docker connection
                self.docker_client.ping()
            except Exception:
                self.docker_client = None

    def start(
        self,
        port: int | None = None,
        data_dir: str | None = None,
        detach: bool = True,
        force_local: bool = False,
        wait_timeout: int = 30,
    ) -> bool:
        """
        Start shared Qdrant service.

        Args:
            port: Port to run Qdrant on (defaults to 6333 for shared instance)
            data_dir: Data directory path (ignored for Docker, uses shared volume)
            detach: Run in background
            force_local: Force local binary instead of Docker
            wait_timeout: Seconds to wait for startup

        Returns:
            bool: True if started successfully
        """
        # Use fixed port for shared instance
        if port is None:
            port = self.default_port

        # Check if already running
        status = self.get_status()
        if status.status == ServiceStatus.RUNNING:
            return True  # Shared instance is already running

        # Check port availability
        if self._is_port_in_use(port):
            raise RuntimeError(f"Port {port} is already in use")

        # Determine data directory (only used for local binary)
        if data_dir:
            data_path = Path(data_dir)
        else:
            data_path = self.default_data_dir

        # Try Docker first (unless forced local)
        if not force_local and self.docker_client:
            try:
                return self._start_docker_shared(detach, wait_timeout)
            except Exception as e:
                # Fall back to local binary
                print(f"Docker start failed ({e}), trying local binary...")
                data_path.mkdir(parents=True, exist_ok=True)

        # Try local binary
        data_path.mkdir(parents=True, exist_ok=True)
        return self._start_local(port, data_path, detach, wait_timeout)

    def stop(self) -> bool:
        """
        Stop shared Qdrant service.

        Returns:
            bool: True if stopped successfully
        """
        stopped_any = False

        # Try stopping shared container using docker-compose
        if self.docker_client:
            try:
                compose_file = (
                    Path(__file__).parent.parent
                    / "docker"
                    / "docker-compose.template.yml"
                )
                if compose_file.exists():
                    cmd = ["docker", "compose", "-f", str(compose_file), "down"]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        stopped_any = True
            except Exception:
                pass

            # Fallback: try stopping container directly
            try:
                container = self.docker_client.containers.get(self.container_name)
                container.stop(timeout=10)
                container.remove()
                stopped_any = True
            except Exception:  # docker.errors.NotFound or any other exception
                pass

        # Try stopping local process
        try:
            # Find Qdrant processes
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    if proc.info["name"] and "qdrant" in proc.info["name"].lower():
                        proc.terminate()
                        proc.wait(timeout=5)
                        stopped_any = True
                except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                    pass
        except Exception:
            pass

        return stopped_any

    def get_status(self) -> QdrantStatus:
        """
        Get current shared Qdrant service status.

        Returns:
            QdrantStatus: Current status information
        """
        # Check Docker container first
        if self.docker_client:
            try:
                container = self.docker_client.containers.get(self.container_name)
                if container.status == "running":
                    # Use fixed port for shared instance
                    port = self.default_port

                    # Calculate uptime from container start time
                    started_at = container.attrs["State"]["StartedAt"]
                    if started_at:
                        import datetime

                        start_time = datetime.datetime.fromisoformat(
                            started_at.replace("Z", "+00:00")
                        )
                        uptime = int(
                            (
                                datetime.datetime.now(datetime.UTC) - start_time
                            ).total_seconds()
                        )
                    else:
                        uptime = None

                    # Check health
                    health = self._check_health(port)

                    return QdrantStatus(
                        status=ServiceStatus.RUNNING,
                        port=port,
                        container_id=container.short_id,
                        uptime_seconds=uptime,
                        health_status="healthy" if health else "unhealthy",
                    )
            except Exception as e:  # docker.errors.NotFound or any other exception
                if "NotFound" in str(type(e)):
                    pass
                else:
                    return QdrantStatus(status=ServiceStatus.ERROR, error=str(e))

        # Check local process
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proc.info["name"] and "qdrant" in proc.info["name"].lower():
                    # Use fixed port for shared instance
                    port = self.default_port

                    health = self._check_health(port)

                    return QdrantStatus(
                        status=ServiceStatus.RUNNING,
                        port=port,
                        pid=proc.info["pid"],
                        health_status="healthy" if health else "unhealthy",
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return QdrantStatus(status=ServiceStatus.STOPPED)

    def get_logs(self, lines: int = 50, follow: bool = False) -> Iterator[str]:
        """
        Get shared Qdrant service logs.

        Args:
            lines: Number of lines to retrieve
            follow: Follow log output

        Yields:
            str: Log lines
        """
        # Try Docker logs first
        if self.docker_client:
            try:
                container = self.docker_client.containers.get(self.container_name)
                logs = container.logs(
                    stream=follow,
                    tail=lines,
                    follow=follow,
                    timestamps=True,
                )

                if follow:
                    for log_line in logs:
                        yield log_line.decode("utf-8")
                else:
                    for line in logs.decode("utf-8").split("\n"):
                        if line.strip():
                            yield line

                return

            except Exception:  # docker.errors.NotFound or any other exception
                pass

        # For local binary, logs would be in a file or systemd
        # This is a simplified implementation
        yield "Local binary logs not implemented yet"

    def _start_docker_shared(
        self,
        detach: bool,
        wait_timeout: int,
    ) -> bool:
        """Start shared Qdrant using docker-compose."""
        try:
            if self.docker_client is None:
                raise RuntimeError("Docker client not available")

            # Clean up old project-specific containers first
            self._cleanup_legacy_containers()

            # Ensure shared data directories exist
            from heimdall.cognitive_system.data_dirs import (
                ensure_data_directories,
                get_qdrant_data_dir,
            )

            ensure_data_directories()
            qdrant_data_dir = get_qdrant_data_dir()

            # Use docker-compose to start shared instance with bind mount
            compose_content = f"""
version: '3.8'
services:
  qdrant:
    image: qdrant/qdrant:v1.14.1
    container_name: heimdall-shared-qdrant
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - {qdrant_data_dir}:/qdrant/storage
    environment:
      - QDRANT__SERVICE__HTTP_PORT=6333
      - QDRANT__SERVICE__GRPC_PORT=6334
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 30s
      timeout: 10s
      retries: 3
""".strip()

            # Write compose file to temporary location
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False
            ) as f:
                f.write(compose_content)
                compose_file = Path(f.name)

            # Start using docker compose (try modern syntax first, then legacy)
            cmd_modern = [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "up",
                "-d",
                "qdrant",
            ]

            try:
                result = subprocess.run(
                    cmd_modern, capture_output=True, text=True, check=True
                )
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                raise RuntimeError(
                    f"Docker compose failed: {e}. Make sure Docker is installed and running."
                ) from e

            if result.returncode != 0:
                raise RuntimeError(f"Docker compose failed: {result.stderr}")

            # Wait for service to be ready
            return self._wait_for_ready(self.default_port, wait_timeout)

        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to start shared Qdrant with docker-compose: {e.stderr}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Failed to start shared Qdrant with Docker: {e}") from e

    def _start_local(
        self,
        port: int,
        data_path: Path,
        detach: bool,
        wait_timeout: int,
    ) -> bool:
        """Start Qdrant using local binary."""
        # Check if qdrant binary is available
        qdrant_path = shutil.which("qdrant")
        if not qdrant_path:
            raise RuntimeError(
                "Qdrant binary not found. Please install Qdrant or use Docker mode."
            )

        # Build command
        cmd = [
            qdrant_path,
            "--config-path",
            str(data_path / "config.yaml"),
            "--storage-path",
            str(data_path / "storage"),
        ]

        # Create basic config file
        config_path = data_path / "config.yaml"
        if not config_path.exists():
            config_content = f"""
service:
  http_port: {port}
  grpc_port: {port + 1}

storage:
  storage_path: {data_path / "storage"}
"""
            config_path.write_text(config_content)

        try:
            if detach:
                # Start as daemon process
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            else:
                # Start in foreground
                subprocess.run(cmd, check=True)

            # Wait for service to be ready
            return self._wait_for_ready(port, wait_timeout)

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to start Qdrant locally: {e}") from e

    def _wait_for_ready(self, port: int, timeout: int) -> bool:
        """Wait for Qdrant to be ready."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self._check_health(port):
                return True
            time.sleep(1)

        return False

    def _check_health(self, port: int) -> bool:
        """Check if Qdrant is healthy."""
        try:
            response = requests.get(
                f"http://localhost:{port}/",
                timeout=5,
            )
            return bool(response.status_code == 200)
        except Exception:
            return False

    def _cleanup_legacy_containers(self) -> None:
        """Clean up old project-specific containers to avoid conflicts."""
        if not self.docker_client:
            return

        try:
            # Find containers that match old naming pattern: heimdall-* or qdrant-*
            all_containers = self.docker_client.containers.list(all=True)
            legacy_containers = []

            for container in all_containers:
                name = container.name
                if (name.startswith("heimdall-") and name != self.container_name) or (
                    name.startswith("qdrant-") and name != self.container_name
                ):
                    legacy_containers.append(container)

            if legacy_containers:
                print(
                    f"Found {len(legacy_containers)} legacy project containers, cleaning up..."
                )
                for container in legacy_containers:
                    try:
                        print(f"  Stopping legacy container: {container.name}")
                        container.stop(timeout=5)
                        container.remove()
                    except Exception as e:
                        print(f"  Warning: Failed to remove {container.name}: {e}")

        except Exception as e:
            print(f"Warning: Failed to cleanup legacy containers: {e}")

    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is in use."""
        for conn in psutil.net_connections():
            if conn.laddr.port == port:
                return True
        return False


class ServiceManager:
    """
    Main service manager for all cognitive memory system services.

    Currently manages Qdrant, but extensible for other services.
    """

    def __init__(self) -> None:
        """Initialize service manager."""
        self.qdrant = QdrantManager()

    def start_all(self, config: dict | None = None) -> dict[str, bool]:
        """
        Start all required services.

        Args:
            config: Service configuration

        Returns:
            Dict[str, bool]: Service start results
        """
        results = {}

        # Start Qdrant
        try:
            qdrant_config = config.get("qdrant", {}) if config else {}
            results["qdrant"] = self.qdrant.start(**qdrant_config)
        except Exception:
            results["qdrant"] = False

        return results

    def stop_all(self) -> dict[str, bool]:
        """
        Stop all services.

        Returns:
            Dict[str, bool]: Service stop results
        """
        results = {}

        # Stop Qdrant
        try:
            results["qdrant"] = self.qdrant.stop()
        except Exception:
            results["qdrant"] = False

        return results

    def get_status_all(self) -> dict[str, QdrantStatus]:
        """
        Get status of all services.

        Returns:
            Dict[str, QdrantStatus]: Service statuses
        """
        return {
            "qdrant": self.qdrant.get_status(),
        }
