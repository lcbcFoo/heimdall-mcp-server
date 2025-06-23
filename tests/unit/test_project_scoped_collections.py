"""
Unit tests for project-scoped collection functionality.

Tests the project identification and collection naming system used
for multi-project isolation in the shared Qdrant architecture.
"""

from unittest.mock import Mock

import pytest

from cognitive_memory.storage.qdrant_storage import QdrantCollectionManager


class TestProjectScopedCollections:
    """Test project-scoped collection naming and management."""

    def test_collection_naming_with_project_id(self):
        """Test that collections are named with project ID prefix."""
        mock_client = Mock()
        project_id = "myproject_abc12345"
        vector_size = 384

        manager = QdrantCollectionManager(mock_client, vector_size, project_id)

        # Check that collection names include project ID
        expected_collections = {
            0: f"{project_id}_concepts",
            1: f"{project_id}_contexts",
            2: f"{project_id}_episodes",
        }

        for level, expected_name in expected_collections.items():
            actual_name = manager.get_collection_name(level)
            assert actual_name == expected_name, (
                f"Level {level} collection name mismatch"
            )

    def test_project_isolation_different_ids(self):
        """Test that different project IDs create different collection names."""
        mock_client = Mock()
        vector_size = 384

        # Create managers for different projects
        project_a = "project_a_12345678"
        project_b = "project_b_87654321"

        manager_a = QdrantCollectionManager(mock_client, vector_size, project_a)
        manager_b = QdrantCollectionManager(mock_client, vector_size, project_b)

        # Verify isolation - no shared collection names
        for level in [0, 1, 2]:
            name_a = manager_a.get_collection_name(level)
            name_b = manager_b.get_collection_name(level)
            assert name_a != name_b, (
                f"Projects sharing collection name at level {level}"
            )
            assert project_a in name_a, f"Project A ID not in collection name: {name_a}"
            assert project_b in name_b, f"Project B ID not in collection name: {name_b}"

    def test_list_project_collections(self):
        """Test listing collections for a specific project."""
        mock_client = Mock()
        project_id = "test_project_12345678"

        # Mock collections response with mixed project collections
        mock_collection_objects = []
        collection_names = [
            f"{project_id}_concepts",
            f"{project_id}_contexts",
            f"{project_id}_episodes",
            "other_project_abc123_concepts",  # Different project
            "legacy_cognitive_concepts",  # Legacy naming
        ]

        for collection_name in collection_names:
            mock_obj = Mock()
            mock_obj.name = collection_name
            mock_collection_objects.append(mock_obj)

        mock_collections = Mock()
        mock_collections.collections = mock_collection_objects
        mock_client.get_collections.return_value = mock_collections

        manager = QdrantCollectionManager(mock_client, 384, project_id)
        project_collections = manager.list_project_collections()

        # Should only return collections for this project
        expected = [
            f"{project_id}_concepts",
            f"{project_id}_contexts",
            f"{project_id}_episodes",
        ]
        assert sorted(project_collections) == sorted(expected)

    def test_get_all_projects_discovery(self):
        """Test discovering all project IDs from existing collections."""
        mock_client = Mock()

        # Mock collections with multiple projects
        mock_collection_objects = []
        collection_names = [
            "project_a_12345678_concepts",
            "project_a_12345678_contexts",
            "project_b_87654321_episodes",
            "complex_name_with_underscores_abc12345_concepts",
            "random_collection_name",  # Should be ignored (no valid suffix)
            "not_a_memory_collection",  # Should be ignored (no valid suffix)
        ]

        for collection_name in collection_names:
            mock_obj = Mock()
            mock_obj.name = collection_name
            mock_collection_objects.append(mock_obj)

        mock_collections = Mock()
        mock_collections.collections = mock_collection_objects
        mock_client.get_collections.return_value = mock_collections

        manager = QdrantCollectionManager(mock_client, 384, "dummy_project")
        discovered_projects = manager.get_all_projects()

        expected_projects = {
            "project_a_12345678",
            "project_b_87654321",
            "complex_name_with_underscores_abc12345",
        }
        assert discovered_projects == expected_projects

    def test_delete_project_collections_classmethod(self):
        """Test deleting all collections for a specific project."""
        mock_client = Mock()
        project_id = "target_project_12345678"

        # Mock collections with target and other projects
        mock_collection_objects = []
        collection_names = [
            f"{project_id}_concepts",
            f"{project_id}_contexts",
            f"{project_id}_episodes",
            "other_project_abc123_concepts",  # Should not be deleted
            "another_project_def456_episodes",  # Should not be deleted
        ]

        for collection_name in collection_names:
            mock_obj = Mock()
            mock_obj.name = collection_name
            mock_collection_objects.append(mock_obj)

        mock_collections = Mock()
        mock_collections.collections = mock_collection_objects
        mock_client.get_collections.return_value = mock_collections

        # Test deletion
        result = QdrantCollectionManager.delete_project_collections(
            mock_client, project_id
        )

        assert result is True

        # Verify only target project collections were deleted
        expected_deletions = [
            f"{project_id}_concepts",
            f"{project_id}_contexts",
            f"{project_id}_episodes",
        ]

        assert mock_client.delete_collection.call_count == 3
        for expected_name in expected_deletions:
            mock_client.delete_collection.assert_any_call(expected_name)

    def test_invalid_memory_level_error(self):
        """Test that invalid memory levels raise appropriate errors."""
        mock_client = Mock()
        manager = QdrantCollectionManager(mock_client, 384, "test_project_12345678")

        # Valid levels should work
        for valid_level in [0, 1, 2]:
            try:
                manager.get_collection_name(valid_level)
            except ValueError:
                pytest.fail(f"Valid level {valid_level} raised ValueError")

        # Invalid levels should raise ValueError
        for invalid_level in [-1, 3, 99]:
            with pytest.raises(ValueError, match="Invalid memory level"):
                manager.get_collection_name(invalid_level)

    def test_project_id_storage(self):
        """Test that project ID is properly stored and accessible."""
        mock_client = Mock()
        project_id = "stored_project_98765432"

        manager = QdrantCollectionManager(mock_client, 384, project_id)

        assert manager.project_id == project_id
        assert hasattr(manager, "project_id"), (
            "QdrantCollectionManager should store project_id"
        )
