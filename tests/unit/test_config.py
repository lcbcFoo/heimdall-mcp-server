"""
Unit tests for configuration system with project support.
"""

import os
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
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

    @pytest.mark.parametrize(
        "path",
        [
            "/path/to/my_concepts",
            "/path/to/something_episodes",
            "/path/to/test_contexts",
            "/path/to/concepts_project",
            "/path/to/episodes_tracker",
            "/path/to/contexts_manager",
            "/path/to/cognitive_concepts",
            "/path/to/memory_episodes",
            "/path/to/user_contexts",
        ],
    )
    def test_project_id_corner_cases_collection_names(self, path: str) -> None:
        """Test project ID generation for projects with names that could create collection name ambiguity."""
        project_id = get_project_id(path)

        # Verify project ID format: {repo_name}_{hash8} where repo_name can contain underscores
        parts = project_id.split("_")
        assert len(parts) >= 2, f"Expected at least 2 parts for {path}, got {parts}"

        # Last part should be 8-character hash
        hash_part = parts[-1]
        assert len(hash_part) == 8, (
            f"Expected 8-character hash, got {len(hash_part)} for {hash_part}"
        )
        assert hash_part.isalnum(), f"Hash should be alphanumeric, got {hash_part}"

        # Repo name is everything except the last part
        repo_name = "_".join(parts[:-1])
        expected_repo_name = Path(path).name
        assert repo_name == expected_repo_name, (
            f"Expected repo name {expected_repo_name}, got {repo_name}"
        )

        # Test that collections can be properly generated and parsed
        potential_collections = [
            f"{project_id}_concepts",
            f"{project_id}_contexts",
            f"{project_id}_episodes",
        ]

        # Verify each collection name can be unambiguously parsed back to project ID
        for collection_name in potential_collections:
            collection_parts = collection_name.split("_")
            # Should have at least 3 parts: {...}_{hash8}_{memory_level}
            assert len(collection_parts) >= 3, (
                f"Collection {collection_name} has too few parts: {collection_parts}"
            )
            # Last part should be a valid memory level
            assert collection_parts[-1] in ["concepts", "contexts", "episodes"], (
                f"Invalid suffix in {collection_name}"
            )
            # Should be able to recover project ID by removing last part
            recovered_project_id = "_".join(collection_parts[:-1])
            assert recovered_project_id == project_id, (
                f"Failed to recover project ID: {recovered_project_id} != {project_id}"
            )

    @pytest.mark.parametrize(
        "path",
        [
            "/path/to/my_complex_project_concepts",
            "/path/to/very_long_name_with_episodes",
            "/path/to/under_score_heavy_contexts_app",
            "/path/to/test_concepts_and_episodes_manager",
        ],
    )
    def test_project_id_with_multiple_underscores(self, path: str) -> None:
        """Test project ID generation for complex repo names with multiple underscores."""
        project_id = get_project_id(path)

        # Should still follow repo_name_hash8 format
        parts = project_id.split("_")
        assert len(parts) == 2, f"Expected exactly 2 parts, got {parts}"

        # Last part should be 8-character hash
        hash_part = parts[1]
        assert len(hash_part) == 8, f"Expected 8-character hash, got {len(hash_part)}"
        assert hash_part.isalnum(), f"Hash should be alphanumeric, got {hash_part}"

        # First part should be the sanitized repo name
        repo_name = Path(path).name
        expected_repo_name = re.sub(r"[^a-zA-Z0-9]", "_", repo_name)
        assert parts[0] == expected_repo_name, (
            f"Expected {expected_repo_name}, got {parts[0]}"
        )

    def test_project_id_hash_like_name_collision(self) -> None:
        """Test extremely tricky corner case: project name that looks like it contains a hash."""
        # This is the worst case: a project name that looks like another project's ID
        tricky_path = "/path/to/some_project_d1000486_concepts"
        project_id = get_project_id(tricky_path)

        # Project ID will be: some_project_d1000486_concepts_{actual_hash8}
        parts = project_id.split("_")
        assert len(parts) == 5, f"Expected 5 parts for tricky case, got {parts}"

        # Verify the actual hash (last part) is 8 chars
        actual_hash = parts[-1]
        assert len(actual_hash) == 8, f"Hash should be 8 chars, got {len(actual_hash)}"
        assert actual_hash.isalnum(), f"Hash should be alphanumeric, got {actual_hash}"

        # Verify the hash is NOT "d1000486" (that's part of the repo name)
        assert actual_hash != "d1000486", "Hash collision with repo name component"

        # Test collection generation and parsing
        collection_name = f"{project_id}_concepts"
        # Should be: some_project_d1000486_concepts_{actual_hash}_concepts
        collection_parts = collection_name.split("_")
        assert collection_parts[-1] == "concepts", "Should end with concepts"

        # Test recovery of project ID from collection name
        recovered_project_id = "_".join(collection_parts[:-1])
        assert recovered_project_id == project_id, (
            f"Recovery failed: {recovered_project_id} != {project_id}"
        )

        # The critical test: ensure this doesn't get confused with a simpler project
        # If there were a project at "/path/to/some_project" with hash "d1000486",
        # its collection would be: some_project_d1000486_concepts
        # Our collection is: some_project_d1000486_concepts_{actual_hash}_concepts
        # These are clearly different and won't be confused

        simple_project_collection = "some_project_d1000486_concepts"
        assert collection_name != simple_project_collection, (
            "Hash-like name created collision"
        )
        assert len(collection_name.split("_")) > len(
            simple_project_collection.split("_")
        ), "Should have more parts"


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
