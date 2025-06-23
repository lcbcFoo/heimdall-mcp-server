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

    def test_project_id_validation_security(self):
        """Test project ID validation rejects various attack vectors."""
        mock_client = Mock()
        manager = QdrantCollectionManager(mock_client, 384, "test_project_12345678")

        # Test valid project ID formats (should be accepted)
        valid_project_ids = [
            "simple_abc12345",
            "complex_name_def67890",
            "under_score_123abc45",
            "project123_789def01",
        ]

        for project_id in valid_project_ids:
            assert manager._validate_project_id_format(project_id), (
                f"Valid project ID rejected: {project_id}"
            )

        # Test invalid project ID formats (should be rejected)
        invalid_project_ids = [
            # No hash part
            "project_name",
            "simple",
            # Hash too short
            "project_1234567",
            "name_abc123",
            # Hash too long
            "project_123456789",
            "name_abcdef123",
            # Non-hex characters in hash
            "project_abcdefgh",
            "name_12345xyz",
            "test_123defgx",
            # No repo name
            "_12345678",
            "12345678",
            # Empty or invalid
            "",
            "_",
            "project_",
            # Invalid characters in repo name
            "project-name_12345678",  # hyphen not allowed
            "project name_12345678",  # space not allowed
            "project@name_12345678",  # @ not allowed
            # Legacy pattern that should be rejected
            "legacy_cognitive",
            "old_system_name",
        ]

        for project_id in invalid_project_ids:
            assert not manager._validate_project_id_format(project_id), (
                f"Invalid project ID accepted: {project_id}"
            )

    def test_extract_project_id_from_collection_security(self):
        """Test collection name parsing rejects malicious collections."""
        mock_client = Mock()
        manager = QdrantCollectionManager(mock_client, 384, "test_project_12345678")

        # Test valid collection names (should extract project ID)
        valid_collections = [
            ("simple_abc12345_concepts", "simple_abc12345"),
            ("complex_name_def67890_contexts", "complex_name_def67890"),
            ("under_score_123abc45_episodes", "under_score_123abc45"),
        ]

        for collection_name, expected_project_id in valid_collections:
            result = manager._extract_project_id_from_collection(collection_name)
            assert result == expected_project_id, (
                f"Failed to extract from: {collection_name}"
            )

        # Test invalid collection names (should return None)
        invalid_collections = [
            # Legacy collections
            "legacy_cognitive_concepts",
            "old_system_contexts",
            "random_name_episodes",
            # Wrong memory level
            "project_abc12345_invalid",
            "name_def67890_wrong",
            # No memory level
            "project_abc12345",
            "name_def67890_something",
            # Invalid project ID format
            "project_abcdefgh_concepts",  # non-hex hash
            "name_1234567_contexts",  # short hash
            "test_123456789_episodes",  # long hash
            "project-name_abc12345_concepts",  # invalid repo name
            # Malformed
            "_abc12345_concepts",
            "abc12345_concepts",
            "concepts",
            "",
            "invalid",
        ]

        for collection_name in invalid_collections:
            result = manager._extract_project_id_from_collection(collection_name)
            assert result is None, (
                f"Incorrectly extracted from: {collection_name} -> {result}"
            )

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

    def test_collection_naming_corner_cases(self):
        """Test collection naming for projects with names ending in memory level suffixes."""
        mock_client = Mock()
        vector_size = 384

        # Test projects that end with memory level names
        corner_case_projects = [
            "my_concepts_abc12345",  # Project name ends with "concepts"
            "something_episodes_def67890",  # Project name ends with "episodes"
            "test_contexts_123abc456",  # Project name ends with "contexts"
            "cognitive_concepts_789def012",  # Contains "concepts"
            "memory_episodes_456ghi789",  # Contains "episodes"
            "user_contexts_321jkl654",  # Contains "contexts"
        ]

        for project_id in corner_case_projects:
            manager = QdrantCollectionManager(mock_client, vector_size, project_id)

            # Verify collections are properly named
            for level in [0, 1, 2]:
                collection_name = manager.get_collection_name(level)
                expected_suffix = ["concepts", "contexts", "episodes"][level]
                expected_name = f"{project_id}_{expected_suffix}"

                assert collection_name == expected_name, (
                    f"Level {level} collection name incorrect: {collection_name} != {expected_name}"
                )

                # Verify collection name can be unambiguously parsed
                # When we split by underscore, the last part should be the memory level
                parts = collection_name.split("_")
                assert len(parts) >= 3, (
                    f"Collection name {collection_name} has too few parts"
                )
                assert parts[-1] == expected_suffix, (
                    f"Collection suffix incorrect: {parts[-1]} != {expected_suffix}"
                )

    def test_project_discovery_with_corner_cases(self):
        """Test project discovery handles projects with confusing names correctly."""
        mock_client = Mock()

        # Create collections that could be confusing when parsing project IDs
        mock_collection_objects = []
        collection_names = [
            # Normal cases
            "simple_project_abc12345_concepts",
            "simple_project_abc12345_contexts",
            "simple_project_abc12345_episodes",
            # Corner cases - projects ending with memory level names
            "my_concepts_def67890_concepts",  # Project: my_concepts_def67890
            "my_concepts_def67890_contexts",  # Project: my_concepts_def67890
            "my_concepts_def67890_episodes",  # Project: my_concepts_def67890
            "something_episodes_123abc45_concepts",  # Project: something_episodes_123abc45
            "something_episodes_123abc45_episodes",  # Project: something_episodes_123abc45
            "test_contexts_789def01_contexts",  # Project: test_contexts_789def01
            "test_contexts_789def01_episodes",  # Project: test_contexts_789def01
            # Complex cases with multiple underscores
            "very_complex_project_concepts_manager_456abc78_concepts",  # Project: very_complex_project_concepts_manager_456abc78
            "memory_episodes_tracker_app_321def65_episodes",  # Project: memory_episodes_tracker_app_321def65
            # Extremely tricky case: project name that looks like it contains a hash and memory level
            "some_project_d1000486_concepts_8f3e2a91_concepts",  # Project: some_project_d1000486_concepts_8f3e2a91
            "another_project_e2f8b4c9_episodes_7a5d1c3f_episodes",  # Project: another_project_e2f8b4c9_episodes_7a5d1c3f
            # Invalid/legacy collections (should be ignored)
            "legacy_cognitive_concepts",
            "random_collection_name",
            "not_memory_related",
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

        # Expected projects based on the collection names above
        # NOTE: legacy_cognitive_concepts should NOT be detected as a project because
        # "cognitive" is not a valid 8-character hash
        expected_projects = {
            "simple_project_abc12345",
            "my_concepts_def67890",
            "something_episodes_123abc45",
            "test_contexts_789def01",
            "very_complex_project_concepts_manager_456abc78",
            "memory_episodes_tracker_app_321def65",
            "some_project_d1000486_concepts_8f3e2a91",  # Tricky case
            "another_project_e2f8b4c9_episodes_7a5d1c3f",  # Tricky case
        }

        assert discovered_projects == expected_projects, (
            f"Project discovery failed. Expected: {expected_projects}, Got: {discovered_projects}"
        )

    def test_collection_cleanup_corner_cases(self):
        """Test collection cleanup works correctly with corner case project names."""
        mock_client = Mock()

        # Target project has confusing name
        target_project = "my_concepts_def67890"

        # Mock collections including target and other projects
        mock_collection_objects = []
        collection_names = [
            # Target project collections (should be deleted)
            f"{target_project}_concepts",
            f"{target_project}_contexts",
            f"{target_project}_episodes",
            # Other projects with similar names (should NOT be deleted)
            "my_concepts_abc12345_concepts",  # Different hash
            "my_concepts_abc12345_episodes",  # Different hash
            "another_concepts_def67890_concepts",  # Different base name
            "my_episodes_def67890_concepts",  # Different base name
            # Unrelated collections (should NOT be deleted)
            "other_project_123_concepts",
            "legacy_cognitive_concepts",
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
            mock_client, target_project
        )

        assert result is True

        # Verify only exact target project collections were deleted
        expected_deletions = [
            f"{target_project}_concepts",
            f"{target_project}_contexts",
            f"{target_project}_episodes",
        ]

        assert mock_client.delete_collection.call_count == 3
        for expected_name in expected_deletions:
            mock_client.delete_collection.assert_any_call(expected_name)
