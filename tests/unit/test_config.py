"""
Unit tests for configuration system with project support.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml

from cognitive_memory.core.config import (
    SystemConfig,
    detect_project_config,
    get_project_id,
)


class TestProjectIdGeneration:
    """Test project ID generation functionality."""

    def test_project_id_format(self) -> None:
        """Test project ID has correct format."""
        project_id = get_project_id("/some/test/path")

        # Should be format: repo_name_hash8
        parts = project_id.split("_")
        assert len(parts) == 2
        assert parts[0] == "path"  # Last directory name
        assert len(parts[1]) == 8  # 8-character hash
        assert parts[1].isalnum()  # Hash should be alphanumeric

    def test_project_id_consistency(self) -> None:
        """Test project ID is consistent for same path."""
        path = "/test/consistent/path"
        id1 = get_project_id(path)
        id2 = get_project_id(path)
        assert id1 == id2

    def test_project_id_different_paths(self) -> None:
        """Test different paths generate different IDs."""
        id1 = get_project_id("/path/one")
        id2 = get_project_id("/path/two")
        assert id1 != id2

    def test_project_id_sanitizes_names(self) -> None:
        """Test project ID sanitizes special characters in repo names."""
        project_id = get_project_id("/test/my-project@2024")

        # Should contain sanitized repo name
        assert "my_project_2024" in project_id
        assert "@" not in project_id
        assert "-" not in project_id

        # Should end with 8-character hash
        parts = project_id.split("_")
        hash_part = parts[-1]
        assert len(hash_part) == 8
        assert hash_part.isalnum()

    def test_project_id_current_directory(self) -> None:
        """Test project ID generation from current directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            old_cwd = os.getcwd()
            try:
                os.chdir(temp_path)
                project_id = get_project_id()

                # Should use current directory
                assert temp_path.name.replace("-", "_") in project_id
            finally:
                os.chdir(old_cwd)


class TestProjectConfigDetection:
    """Test project configuration detection."""

    def test_no_config_files(self) -> None:
        """Test returns None when no config files exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            old_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                config = detect_project_config()
                assert config is None
            finally:
                os.chdir(old_cwd)

    def test_heimdall_yaml_config(self) -> None:
        """Test loading .heimdall/config.yaml."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            old_cwd = os.getcwd()

            try:
                os.chdir(temp_path)

                # Create .heimdall/config.yaml
                heimdall_dir = temp_path / ".heimdall"
                heimdall_dir.mkdir()

                config_data = {
                    "qdrant_url": "http://localhost:7000",
                    "monitoring": {
                        "target_path": "./test-docs",
                        "interval_seconds": 15.0,
                    },
                    "database": {"path": "./test.db"},
                }

                config_file = heimdall_dir / "config.yaml"
                config_file.write_text(yaml.dump(config_data))

                # Test detection
                detected = detect_project_config()

                assert detected is not None
                assert detected["QDRANT_URL"] == "http://localhost:7000"
                assert detected["MONITORING_TARGET_PATH"] == "./test-docs"
                assert detected["MONITORING_INTERVAL_SECONDS"] == "15.0"
                assert detected["SQLITE_PATH"] == "./test.db"

            finally:
                os.chdir(old_cwd)

    def test_legacy_docker_compose_config(self) -> None:
        """Test fallback to legacy docker-compose.yml."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            old_cwd = os.getcwd()

            try:
                os.chdir(temp_path)

                # Create .heimdall-mcp/docker-compose.yml (legacy)
                mcp_dir = temp_path / ".heimdall-mcp"
                mcp_dir.mkdir()

                compose_content = """
services:
  qdrant:
    ports:
      - "6631:6333"
"""
                compose_file = mcp_dir / "docker-compose.yml"
                compose_file.write_text(compose_content)

                # Test detection
                detected = detect_project_config()

                assert detected is not None
                assert detected["QDRANT_URL"] == "http://localhost:6631"

            finally:
                os.chdir(old_cwd)

    def test_heimdall_yaml_precedence(self) -> None:
        """Test .heimdall/config.yaml takes precedence over docker-compose."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            old_cwd = os.getcwd()

            try:
                os.chdir(temp_path)

                # Create both config files
                heimdall_dir = temp_path / ".heimdall"
                heimdall_dir.mkdir()
                mcp_dir = temp_path / ".heimdall-mcp"
                mcp_dir.mkdir()

                # YAML config (should take precedence)
                config_data = {"qdrant_url": "http://localhost:8000"}
                yaml_file = heimdall_dir / "config.yaml"
                yaml_file.write_text(yaml.dump(config_data))

                # Docker compose config
                compose_content = (
                    '''services:\n  qdrant:\n    ports:\n      - "6631:6333"'''
                )
                compose_file = mcp_dir / "docker-compose.yml"
                compose_file.write_text(compose_content)

                # Test detection - should use YAML
                detected = detect_project_config()

                assert detected is not None
                assert (
                    detected["QDRANT_URL"] == "http://localhost:8000"
                )  # From YAML, not docker-compose

            finally:
                os.chdir(old_cwd)

    def test_invalid_yaml_fallback(self) -> None:
        """Test fallback to docker-compose when YAML is invalid."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            old_cwd = os.getcwd()

            try:
                os.chdir(temp_path)

                # Create invalid YAML and valid docker-compose
                heimdall_dir = temp_path / ".heimdall"
                heimdall_dir.mkdir()
                mcp_dir = temp_path / ".heimdall-mcp"
                mcp_dir.mkdir()

                # Invalid YAML
                yaml_file = heimdall_dir / "config.yaml"
                yaml_file.write_text("invalid: yaml: content: [")

                # Valid docker-compose
                compose_content = (
                    '''services:\n  qdrant:\n    ports:\n      - "6632:6333"'''
                )
                compose_file = mcp_dir / "docker-compose.yml"
                compose_file.write_text(compose_content)

                # Should fall back to docker-compose
                detected = detect_project_config()

                assert detected is not None
                assert detected["QDRANT_URL"] == "http://localhost:6632"

            finally:
                os.chdir(old_cwd)


class TestSystemConfigWithProject:
    """Test SystemConfig with project integration."""

    def test_system_config_includes_project_id(self) -> None:
        """Test SystemConfig automatically includes project ID."""
        config = SystemConfig.from_env()

        assert config.project_id != ""
        assert "_" in config.project_id  # Should have repo_name_hash format

    def test_system_config_to_dict_includes_project(self) -> None:
        """Test config dictionary includes project information."""
        config = SystemConfig.from_env()
        config_dict = config.to_dict()

        assert "system" in config_dict
        assert "project_id" in config_dict["system"]
        assert config_dict["system"]["project_id"] == config.project_id

    @patch.dict(os.environ, {"QDRANT_URL": "http://localhost:9000"})
    def test_project_config_overrides_env(self) -> None:
        """Test project config doesn't override existing environment variables."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            old_cwd = os.getcwd()

            try:
                os.chdir(temp_path)

                # Create .heimdall/config.yaml with different URL
                heimdall_dir = temp_path / ".heimdall"
                heimdall_dir.mkdir()

                config_data = {"qdrant_url": "http://localhost:7777"}
                yaml_file = heimdall_dir / "config.yaml"
                yaml_file.write_text(yaml.dump(config_data))

                # Environment variable should take precedence
                config = SystemConfig.from_env()
                assert config.qdrant.url == "http://localhost:9000"

            finally:
                os.chdir(old_cwd)

    def test_project_config_sets_when_no_env(self) -> None:
        """Test project config is used when no environment variable exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            old_cwd = os.getcwd()

            try:
                os.chdir(temp_path)

                # Create .heimdall/config.yaml
                heimdall_dir = temp_path / ".heimdall"
                heimdall_dir.mkdir()

                config_data = {"qdrant_url": "http://localhost:8888"}
                yaml_file = heimdall_dir / "config.yaml"
                yaml_file.write_text(yaml.dump(config_data))

                # Ensure QDRANT_URL is not in environment
                old_qdrant_url = os.environ.pop("QDRANT_URL", None)
                try:
                    config = SystemConfig.from_env()
                    assert config.qdrant.url == "http://localhost:8888"
                finally:
                    if old_qdrant_url:
                        os.environ["QDRANT_URL"] = old_qdrant_url

            finally:
                os.chdir(old_cwd)
