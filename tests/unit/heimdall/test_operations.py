#!/usr/bin/env python3
"""
Unit tests for CognitiveOperations class.

Tests the pure operations layer without any interface dependencies.
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from cognitive_memory.core.memory import BridgeMemory, CognitiveMemory

# Add project root to path to find heimdall module
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Direct import of the operations module
operations_path = project_root / "heimdall" / "operations.py"
spec = importlib.util.spec_from_file_location("heimdall.operations", operations_path)
operations_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operations_module)
CognitiveOperations = operations_module.CognitiveOperations


class TestCognitiveOperations:
    """Test suite for CognitiveOperations class."""

    @pytest.fixture
    def mock_cognitive_system(self):
        """Create a mock cognitive system for testing."""
        return Mock()

    @pytest.fixture
    def operations(self, mock_cognitive_system):
        """Create CognitiveOperations instance with mocked system."""
        return CognitiveOperations(mock_cognitive_system)

    def test_init(self, mock_cognitive_system):
        """Test CognitiveOperations initialization."""
        ops = CognitiveOperations(mock_cognitive_system)
        assert ops.cognitive_system is mock_cognitive_system

    class TestStoreExperience:
        """Tests for store_experience method."""

        def test_store_experience_success(self, operations, mock_cognitive_system):
            """Test successful experience storage."""
            # Arrange
            mock_cognitive_system.store_experience.return_value = "mem_123"
            text = "This is a test experience"
            context = {"source": "test"}

            # Act
            result = operations.store_experience(text, context)

            # Assert
            assert result["success"] is True
            assert result["memory_id"] == "mem_123"
            assert result["hierarchy_level"] == 2  # Default to episodes
            assert result["memory_type"] == "episodic"
            assert result["error"] is None
            mock_cognitive_system.store_experience.assert_called_once_with(
                text, context
            )

        def test_store_experience_with_context_hierarchy(
            self, operations, mock_cognitive_system
        ):
            """Test experience storage with hierarchy level in context."""
            # Arrange
            mock_cognitive_system.store_experience.return_value = "mem_456"
            text = "This is a concept"
            context = {"hierarchy_level": 0, "memory_type": "semantic"}

            # Act
            result = operations.store_experience(text, context)

            # Assert
            assert result["success"] is True
            assert result["memory_id"] == "mem_456"
            assert result["hierarchy_level"] == 0
            assert result["memory_type"] == "semantic"
            assert result["error"] is None

        def test_store_experience_with_json_context(
            self, operations, mock_cognitive_system
        ):
            """Test experience storage with JSON context string."""
            # Arrange
            mock_cognitive_system.store_experience.return_value = "mem_789"
            text = "Test with JSON context"
            context_json = '{"source": "json_test", "hierarchy_level": 1}'

            # Act
            result = operations.store_experience(text, context_json=context_json)

            # Assert
            assert result["success"] is True
            assert result["memory_id"] == "mem_789"
            assert result["hierarchy_level"] == 1
            mock_cognitive_system.store_experience.assert_called_once_with(
                text, {"source": "json_test", "hierarchy_level": 1}
            )

        def test_store_experience_empty_text(self, operations, mock_cognitive_system):
            """Test storage failure with empty text."""
            # Act
            result = operations.store_experience("")

            # Assert
            assert result["success"] is False
            assert result["memory_id"] is None
            assert result["hierarchy_level"] is None
            assert result["memory_type"] is None
            assert result["error"] == "Empty text provided"
            mock_cognitive_system.store_experience.assert_not_called()

        def test_store_experience_whitespace_only(
            self, operations, mock_cognitive_system
        ):
            """Test storage failure with whitespace-only text."""
            # Act
            result = operations.store_experience("   \t\n  ")

            # Assert
            assert result["success"] is False
            assert result["error"] == "Empty text provided"
            mock_cognitive_system.store_experience.assert_not_called()

        def test_store_experience_invalid_json_context(
            self, operations, mock_cognitive_system
        ):
            """Test storage failure with invalid JSON context."""
            # Act
            result = operations.store_experience("test", context_json="{invalid json")

            # Assert
            assert result["success"] is False
            assert result["memory_id"] is None
            assert "Invalid JSON context" in result["error"]
            mock_cognitive_system.store_experience.assert_not_called()

        def test_store_experience_system_returns_none(
            self, operations, mock_cognitive_system
        ):
            """Test storage failure when system returns None."""
            # Arrange
            mock_cognitive_system.store_experience.return_value = None

            # Act
            result = operations.store_experience("test text")

            # Assert
            assert result["success"] is False
            assert result["memory_id"] is None
            assert (
                "Failed to store experience - no memory ID returned" in result["error"]
            )

        def test_store_experience_system_exception(
            self, operations, mock_cognitive_system
        ):
            """Test storage failure when system raises exception."""
            # Arrange
            mock_cognitive_system.store_experience.side_effect = Exception(
                "System error"
            )

            # Act
            result = operations.store_experience("test text")

            # Assert
            assert result["success"] is False
            assert result["memory_id"] is None
            assert result["error"] == "System error"

    class TestRetrieveMemories:
        """Tests for retrieve_memories method."""

        def test_retrieve_memories_success(self, operations, mock_cognitive_system):
            """Test successful memory retrieval."""
            # Arrange
            mock_memory1 = Mock(spec=CognitiveMemory)
            mock_memory2 = Mock(spec=CognitiveMemory)
            mock_bridge = Mock(spec=BridgeMemory)

            mock_cognitive_system.retrieve_memories.return_value = {
                "core": [mock_memory1],
                "peripheral": [mock_memory2],
                "bridge": [mock_bridge],
            }

            # Act
            result = operations.retrieve_memories("test query", limit=5)

            # Assert
            assert result["success"] is True
            assert result["query"] == "test query"
            assert result["total_count"] == 3
            assert len(result["core"]) == 1
            assert len(result["peripheral"]) == 1
            assert len(result["bridge"]) == 1
            assert result["error"] is None
            mock_cognitive_system.retrieve_memories.assert_called_once_with(
                query="test query",
                types=["core", "peripheral", "bridge"],
                max_results=5,
            )

        def test_retrieve_memories_custom_types(
            self, operations, mock_cognitive_system
        ):
            """Test memory retrieval with custom types."""
            # Arrange
            mock_memory = Mock(spec=CognitiveMemory)
            mock_cognitive_system.retrieve_memories.return_value = {
                "core": [mock_memory],
                "peripheral": [],
                "bridge": [],
            }

            # Act
            result = operations.retrieve_memories("test", types=["core"], limit=10)

            # Assert
            assert result["success"] is True
            assert result["total_count"] == 1
            mock_cognitive_system.retrieve_memories.assert_called_once_with(
                query="test", types=["core"], max_results=10
            )

        def test_retrieve_memories_empty_query(self, operations, mock_cognitive_system):
            """Test retrieval failure with empty query."""
            # Act
            result = operations.retrieve_memories("")

            # Assert
            assert result["success"] is False
            assert result["total_count"] == 0
            assert result["error"] == "Empty query provided"
            assert result["core"] == []
            assert result["peripheral"] == []
            assert result["bridge"] == []
            mock_cognitive_system.retrieve_memories.assert_not_called()

        def test_retrieve_memories_whitespace_query(
            self, operations, mock_cognitive_system
        ):
            """Test retrieval failure with whitespace-only query."""
            # Act
            result = operations.retrieve_memories("   \t  ")

            # Assert
            assert result["success"] is False
            assert result["error"] == "Empty query provided"
            mock_cognitive_system.retrieve_memories.assert_not_called()

        def test_retrieve_memories_missing_keys(
            self, operations, mock_cognitive_system
        ):
            """Test handling of missing result keys."""
            # Arrange
            mock_memory = Mock()
            mock_cognitive_system.retrieve_memories.return_value = {
                "core": [mock_memory],
                # Missing peripheral and bridge keys
            }

            # Act
            result = operations.retrieve_memories("test")

            # Assert
            assert result["success"] is True
            assert result["total_count"] == 1
            assert len(result["core"]) == 1
            assert result["core"][0] is mock_memory
            assert result["peripheral"] == []  # Should default to empty list
            assert result["bridge"] == []  # Should default to empty list

        def test_retrieve_memories_system_exception(
            self, operations, mock_cognitive_system
        ):
            """Test retrieval failure when system raises exception."""
            # Arrange
            mock_cognitive_system.retrieve_memories.side_effect = Exception(
                "Retrieval error"
            )

            # Act
            result = operations.retrieve_memories("test query")

            # Assert
            assert result["success"] is False
            assert result["total_count"] == 0
            assert result["error"] == "Retrieval error"
            assert all(result[key] == [] for key in ["core", "peripheral", "bridge"])

    class TestGetSystemStatus:
        """Tests for get_system_status method."""

        def test_get_system_status_basic(self, operations, mock_cognitive_system):
            """Test basic system status retrieval."""
            # Arrange
            mock_stats = {
                "memory_counts": {"level_0": 10, "level_1": 20, "level_2": 30},
                "system_config": {"activation_threshold": 0.7},
                "storage_stats": {"vectors_count": 60},
                "embedding_info": {"model_name": "test-model"},
            }
            mock_cognitive_system.get_memory_stats.return_value = mock_stats

            # Act
            result = operations.get_system_status(detailed=False)

            # Assert
            assert result["success"] is True
            assert result["memory_counts"] == {
                "level_0": 10,
                "level_1": 20,
                "level_2": 30,
            }
            assert result["error"] is None
            # Should not include detailed info when detailed=False
            assert "system_config" not in result
            assert "storage_stats" not in result
            assert "embedding_info" not in result

        def test_get_system_status_detailed(self, operations, mock_cognitive_system):
            """Test detailed system status retrieval."""
            # Arrange
            mock_stats = {
                "memory_counts": {"level_0": 10},
                "system_config": {"activation_threshold": 0.7},
                "storage_stats": {"vectors_count": 60},
                "embedding_info": {"model_name": "test-model"},
            }
            mock_cognitive_system.get_memory_stats.return_value = mock_stats

            # Act
            result = operations.get_system_status(detailed=True)

            # Assert
            assert result["success"] is True
            assert result["memory_counts"] == {"level_0": 10}
            assert result["system_config"] == {"activation_threshold": 0.7}
            assert result["storage_stats"] == {"vectors_count": 60}
            assert result["embedding_info"] == {"model_name": "test-model"}
            assert result["error"] is None

        def test_get_system_status_missing_keys(
            self, operations, mock_cognitive_system
        ):
            """Test status retrieval with missing stat keys."""
            # Arrange
            mock_cognitive_system.get_memory_stats.return_value = {}

            # Act
            result = operations.get_system_status(detailed=True)

            # Assert
            assert result["success"] is True
            assert result["memory_counts"] == {}
            assert result["system_config"] == {}
            assert result["storage_stats"] == {}
            assert result["embedding_info"] == {}

        def test_get_system_status_exception(self, operations, mock_cognitive_system):
            """Test status failure when system raises exception."""
            # Arrange
            mock_cognitive_system.get_memory_stats.side_effect = Exception(
                "Status error"
            )

            # Act
            result = operations.get_system_status(detailed=True)

            # Assert
            assert result["success"] is False
            assert result["memory_counts"] == {}
            assert result["system_config"] == {}
            assert result["storage_stats"] == {}
            assert result["embedding_info"] == {}
            assert result["error"] == "Status error"

    class TestConsolidateMemories:
        """Tests for consolidate_memories method."""

        def test_consolidate_memories_success(self, operations, mock_cognitive_system):
            """Test successful memory consolidation."""
            # Arrange
            mock_results = {
                "total_episodic": 100,
                "consolidated": 15,
                "failed": 2,
                "skipped": 83,
            }
            mock_cognitive_system.consolidate_memories.return_value = mock_results

            # Act
            result = operations.consolidate_memories(dry_run=False)

            # Assert
            assert result["success"] is True
            assert result["total_episodic"] == 100
            assert result["consolidated"] == 15
            assert result["failed"] == 2
            assert result["skipped"] == 83
            assert result["dry_run"] is False
            assert result["error"] is None

        def test_consolidate_memories_dry_run(self, operations, mock_cognitive_system):
            """Test consolidation with dry run flag."""
            # Arrange
            mock_results = {
                "total_episodic": 50,
                "consolidated": 5,
                "failed": 0,
                "skipped": 45,
            }
            mock_cognitive_system.consolidate_memories.return_value = mock_results

            # Act
            result = operations.consolidate_memories(dry_run=True)

            # Assert
            assert result["success"] is True
            assert result["dry_run"] is True
            # Note: Current implementation doesn't support actual dry run in system
            mock_cognitive_system.consolidate_memories.assert_called_once()

        def test_consolidate_memories_missing_keys(
            self, operations, mock_cognitive_system
        ):
            """Test consolidation with missing result keys."""
            # Arrange
            mock_cognitive_system.consolidate_memories.return_value = {}

            # Act
            result = operations.consolidate_memories()

            # Assert
            assert result["success"] is True
            assert result["total_episodic"] == 0
            assert result["consolidated"] == 0
            assert result["failed"] == 0
            assert result["skipped"] == 0

        def test_consolidate_memories_exception(
            self, operations, mock_cognitive_system
        ):
            """Test consolidation failure when system raises exception."""
            # Arrange
            mock_cognitive_system.consolidate_memories.side_effect = Exception(
                "Consolidation error"
            )

            # Act
            result = operations.consolidate_memories()

            # Assert
            assert result["success"] is False
            assert result["total_episodic"] == 0
            assert result["consolidated"] == 0
            assert result["failed"] == 0
            assert result["skipped"] == 0
            assert result["error"] == "Consolidation error"
            assert result["dry_run"] is False

    class TestLoadMemories:
        """Tests for load_memories method."""

        def test_load_memories_unsupported_loader(self, operations):
            """Test load_memories with unsupported loader type."""
            # Act
            result = operations.load_memories(
                "/path/to/file", loader_type="unsupported"
            )

            # Assert
            assert result["success"] is False
            assert result["memories_loaded"] == 0
            assert "Unsupported loader type: unsupported" in result["error"]
            assert result["dry_run"] is False

        @patch("cognitive_memory.core.config.get_config")
        @patch("cognitive_memory.loaders.MarkdownMemoryLoader")
        def test_load_memories_markdown_single_file_success(
            self, mock_loader_class, mock_get_config, operations, mock_cognitive_system
        ):
            """Test successful markdown file loading."""
            # Arrange
            mock_config = Mock()
            mock_config.cognitive = Mock()
            mock_get_config.return_value = mock_config

            mock_loader = Mock()
            mock_loader.validate_source.return_value = True
            mock_loader_class.return_value = mock_loader

            mock_results = {
                "success": True,
                "memories_loaded": 10,
                "connections_created": 5,
                "processing_time": 1.5,
                "hierarchy_distribution": {"L0": 2, "L1": 3, "L2": 5},
                "memories_failed": 0,
                "connections_failed": 0,
            }
            mock_cognitive_system.load_memories_from_source.return_value = mock_results

            # Act
            with patch.object(operations_module, "Path") as mock_path:
                mock_path_obj = Mock()
                mock_path_obj.is_dir.return_value = False
                mock_path.return_value = mock_path_obj

                result = operations.load_memories(
                    "/path/to/file.md", loader_type="markdown"
                )

            # Assert
            assert result["success"] is True
            assert result["memories_loaded"] == 10
            assert result["connections_created"] == 5
            assert result["processing_time"] == 1.5
            assert result["hierarchy_distribution"] == {"L0": 2, "L1": 3, "L2": 5}
            assert result["files_processed"] == ["/path/to/file.md"]
            assert result["error"] is None

        @patch("cognitive_memory.core.config.get_config")
        @patch("cognitive_memory.loaders.MarkdownMemoryLoader")
        def test_load_memories_validation_failure(
            self, mock_loader_class, mock_get_config, operations, mock_cognitive_system
        ):
            """Test load_memories with validation failure."""
            # Arrange
            mock_config = Mock()
            mock_get_config.return_value = mock_config

            mock_loader = Mock()
            mock_loader.validate_source.return_value = False
            mock_loader_class.return_value = mock_loader

            # Act
            with patch.object(operations_module, "Path") as mock_path:
                mock_path_obj = Mock()
                mock_path_obj.is_dir.return_value = False
                mock_path.return_value = mock_path_obj

                result = operations.load_memories("/invalid/file.md")

            # Assert
            assert result["success"] is False
            assert "Source validation failed" in result["error"]
            mock_cognitive_system.load_memories_from_source.assert_not_called()

        @patch("cognitive_memory.core.config.get_config")
        @patch("cognitive_memory.loaders.MarkdownMemoryLoader")
        def test_load_memories_dry_run(
            self, mock_loader_class, mock_get_config, operations, mock_cognitive_system
        ):
            """Test load_memories in dry run mode."""
            # Arrange
            mock_config = Mock()
            mock_get_config.return_value = mock_config

            mock_loader = Mock()
            mock_loader.validate_source.return_value = True

            # Create mock memories
            mock_memory1 = Mock()
            mock_memory1.hierarchy_level = 0
            mock_memory2 = Mock()
            mock_memory2.hierarchy_level = 2

            mock_loader.load_from_source.return_value = [mock_memory1, mock_memory2]
            mock_loader.extract_connections.return_value = ["conn1", "conn2"]
            mock_loader_class.return_value = mock_loader

            # Act
            with patch.object(operations_module, "Path") as mock_path:
                mock_path_obj = Mock()
                mock_path_obj.is_dir.return_value = False
                mock_path.return_value = mock_path_obj

                result = operations.load_memories("/path/to/file.md", dry_run=True)

            # Assert
            assert result["success"] is True
            assert result["memories_loaded"] == 2
            assert result["connections_created"] == 2
            assert result["hierarchy_distribution"] == {"L0": 1, "L1": 0, "L2": 1}
            assert result["dry_run"] is True
            # Should not call actual loading when dry_run=True
            mock_cognitive_system.load_memories_from_source.assert_not_called()

        @patch("cognitive_memory.core.config.get_config")
        @patch("cognitive_memory.loaders.MarkdownMemoryLoader")
        @patch("os.walk")
        def test_load_memories_directory_recursive(
            self,
            mock_walk,
            mock_loader_class,
            mock_get_config,
            operations,
            mock_cognitive_system,
        ):
            """Test directory loading with recursive option."""
            # Arrange
            mock_config = Mock()
            mock_get_config.return_value = mock_config

            mock_loader = Mock()
            mock_loader.validate_source.return_value = True
            mock_loader.get_supported_extensions.return_value = [".md"]
            mock_loader_class.return_value = mock_loader

            # Mock directory walking
            mock_walk.return_value = [
                ("/path/to/dir", [], ["file1.md", "file2.md", "ignore.txt"])
            ]

            mock_results = {
                "success": True,
                "memories_loaded": 5,
                "connections_created": 2,
                "processing_time": 1.0,
                "hierarchy_distribution": {"L0": 1, "L1": 2, "L2": 2},
                "memories_failed": 0,
                "connections_failed": 0,
            }
            mock_cognitive_system.load_memories_from_source.return_value = mock_results

            # Act
            # Let Path work normally - it's fine to use real Path objects
            result = operations.load_memories("/path/to/dir", recursive=True)

            # Assert
            assert result["success"] is True
            assert result["memories_loaded"] == 5  # Single directory processing result
            assert (
                result["connections_created"] == 2
            )  # Single directory processing result
            assert (
                len(result["files_processed"]) == 1
            )  # Directory treated as single source

        @patch("cognitive_memory.core.config.get_config")
        @patch("cognitive_memory.loaders.MarkdownMemoryLoader")
        def test_load_memories_directory_not_recursive(
            self, mock_loader_class, mock_get_config, operations, mock_cognitive_system
        ):
            """Test directory loading without recursive option."""
            # Arrange
            mock_config = Mock()
            mock_get_config.return_value = mock_config

            mock_loader = Mock()
            mock_loader_class.return_value = mock_loader

            # Act
            with patch.object(operations_module, "Path") as mock_path:
                mock_path_obj = Mock()
                mock_path_obj.is_dir.return_value = True
                mock_path_obj.__truediv__ = lambda self, other: Mock(
                    exists=lambda: False
                )
                mock_path.return_value = mock_path_obj

                result = operations.load_memories("/path/to/dir", recursive=False)

            # Assert
            assert result["success"] is False
            assert "Use recursive=True" in result["error"]
            mock_cognitive_system.load_memories_from_source.assert_not_called()

        @patch("cognitive_memory.core.config.get_config")
        @patch("cognitive_memory.loaders.GitHistoryLoader")
        def test_load_memories_git_loader(
            self,
            mock_git_loader_class,
            mock_get_config,
            operations,
            mock_cognitive_system,
        ):
            """Test load_memories with git loader."""
            # Arrange
            mock_config = Mock()
            mock_get_config.return_value = mock_config

            mock_loader = Mock()
            mock_loader.validate_source.return_value = True
            mock_git_loader_class.return_value = mock_loader

            mock_results = {
                "success": True,
                "memories_loaded": 25,
                "connections_created": 10,
                "processing_time": 5.0,
                "hierarchy_distribution": {"L0": 5, "L1": 10, "L2": 10},
                "memories_failed": 0,
                "connections_failed": 0,
            }
            mock_cognitive_system.load_memories_from_source.return_value = mock_results

            # Act
            with patch.object(operations_module, "Path") as mock_path:
                mock_path_obj = Mock()
                mock_path_obj.is_dir.return_value = True
                mock_path_obj.__truediv__ = lambda self, other: Mock(
                    exists=lambda: True
                )  # .git exists
                mock_path.return_value = mock_path_obj

                result = operations.load_memories("/path/to/repo", loader_type="git")

            # Assert
            assert result["success"] is True
            assert result["memories_loaded"] == 25
            mock_git_loader_class.assert_called_once_with(
                mock_config.cognitive, mock_cognitive_system
            )

        def test_load_git_patterns(self, operations, mock_cognitive_system):
            """Test load_git_patterns method delegates to load_memories."""
            # Act
            with patch.object(operations, "load_memories") as mock_load_memories:
                mock_load_memories.return_value = {
                    "success": True,
                    "memories_loaded": 10,
                }

                result = operations.load_git_patterns(
                    "/repo/path", dry_run=True, time_window="6m"
                )

            # Assert
            mock_load_memories.assert_called_once_with(
                source_path="/repo/path",
                loader_type="git",
                dry_run=True,
                time_window="6m",
            )
            assert result == {"success": True, "memories_loaded": 10}

    class TestProcessingHelpers:
        """Tests for internal processing helper methods."""

        def test_process_single_source_dry_run_exception(self, operations):
            """Test _process_single_source with exception during dry run."""
            # Arrange
            mock_loader = Mock()
            mock_loader.validate_source.return_value = True
            mock_loader.load_from_source.side_effect = Exception("Dry run error")

            # Act
            result = operations._process_single_source(
                mock_loader, "/path/file.md", dry_run=True
            )

            # Assert
            assert result["success"] is False
            assert result["error"] == "Dry run error"
            assert result["dry_run"] is True

        def test_process_single_source_actual_loading_exception(
            self, operations, mock_cognitive_system
        ):
            """Test _process_single_source with exception during actual loading."""
            # Arrange
            mock_loader = Mock()
            mock_loader.validate_source.return_value = True
            mock_cognitive_system.load_memories_from_source.side_effect = Exception(
                "Loading error"
            )

            # Act
            result = operations._process_single_source(
                mock_loader, "/path/file.md", dry_run=False
            )

            # Assert
            assert result["success"] is False
            assert result["error"] == "Loading error"
            assert result["dry_run"] is False

        @patch.object(operations_module, "os")
        def test_process_directory_no_files_found(self, mock_os, operations):
            """Test _process_directory when no supported files are found."""
            # Arrange
            mock_loader = Mock()
            mock_loader.get_supported_extensions.return_value = [".md"]
            mock_os.walk.return_value = [
                ("/path", [], ["file.txt", "other.pdf"])
            ]  # No .md files

            source_path_obj = Path("/path")

            # Act
            result = operations._process_directory(
                mock_loader, source_path_obj, False, True
            )

            # Assert
            assert result["success"] is False
            assert "No .md files found" in result["error"]
            assert result["files_processed"] == []

        @patch.object(operations_module, "os")
        def test_process_directory_file_validation_failure(self, mock_os, operations):
            """Test _process_directory with file validation failures."""
            # Arrange
            mock_loader = Mock()
            mock_loader.get_supported_extensions.return_value = [".md"]
            mock_loader.validate_source.return_value = (
                False  # All files fail validation
            )
            mock_os.walk.return_value = [("/path", [], ["valid.md"])]

            source_path_obj = Path("/path")

            # Act
            result = operations._process_directory(
                mock_loader, source_path_obj, False, True
            )

            # Assert
            assert result["success"] is False  # Fails when validation fails
            assert result["memories_loaded"] == 0
            assert result["files_processed"] == []

        @patch.object(operations_module, "os")
        def test_process_directory_mixed_success_failure(
            self, mock_os, operations, mock_cognitive_system
        ):
            """Test _process_directory with mixed success and failure results."""
            # Arrange
            mock_loader = Mock()
            mock_loader.get_supported_extensions.return_value = [".md"]
            mock_loader.validate_source.return_value = True
            mock_os.walk.return_value = [("/path", [], ["success.md", "failure.md"])]

            # Mock different results for different files
            def mock_load_side_effect(loader, file_path, **kwargs):
                if "success.md" in file_path:
                    return {
                        "success": True,
                        "memories_loaded": 5,
                        "connections_created": 2,
                        "processing_time": 1.0,
                        "hierarchy_distribution": {"L0": 1, "L1": 2, "L2": 2},
                        "memories_failed": 0,
                        "connections_failed": 0,
                    }
                else:
                    return {"success": False}

            mock_cognitive_system.load_memories_from_source.side_effect = (
                mock_load_side_effect
            )

            source_path_obj = Path("/path")

            # Act
            # Don't mock Path since it breaks path operations - let the real Path work
            result = operations._process_directory(
                mock_loader, source_path_obj, False, True
            )

            # Assert
            assert result["success"] is False  # Overall failure due to one file failing
            assert result["memories_loaded"] == 5  # Only from successful file
            assert result["connections_created"] == 2
            assert result["error"] == "Some files failed to process"
            assert len(result["files_processed"]) == 2
