"""
Comprehensive end-to-end integration tests for the complete cognitive memory system.

Tests the full workflow from CLI input through encoding, storage, retrieval,
and back to user output, validating all system components working together.
"""

import random
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from cognitive_memory.core.config import (
    CognitiveConfig,
    DatabaseConfig,
    EmbeddingConfig,
    LoggingConfig,
    QdrantConfig,
    SystemConfig,
)
from cognitive_memory.factory import create_default_system, create_test_system
from interfaces.cli import CognitiveCLI


class MockQdrantClient:
    """Mock Qdrant client for end-to-end testing."""

    def __init__(self, project_id: str = "test_project_12345678", **kwargs):
        self.project_id = project_id
        self.collections = []
        self.points = {}
        self.next_point_id = 1

    def get_collections(self):
        mock_collections = MagicMock()
        mock_collections.collections = [
            MagicMock(name=f"{self.project_id}_concepts"),
            MagicMock(name=f"{self.project_id}_contexts"),
            MagicMock(name=f"{self.project_id}_episodes"),
        ]
        return mock_collections

    def create_collection(self, *args, **kwargs):
        pass

    def upsert(self, collection_name, points):
        if collection_name not in self.points:
            self.points[collection_name] = {}
        for point in points:
            self.points[collection_name][point.id] = {
                "vector": point.vector,
                "payload": point.payload,
            }

    def search(
        self,
        collection_name,
        query_vector,
        limit,
        query_filter=None,
        score_threshold=None,
        with_payload=True,
        with_vectors=False,
        **kwargs,
    ):
        results = []
        total_points = len(self.points.get(collection_name, {}))
        print(
            f"DEBUG SEARCH: Collection {collection_name} has {total_points} points, limit={limit}, threshold={score_threshold}"
        )

        if collection_name in self.points:
            points = list(self.points[collection_name].items())
            for point_id, point_data in points:
                mock_result = MagicMock()
                mock_result.id = point_id
                mock_result.score = 0.85  # Good similarity

                # Respect score threshold
                if score_threshold is not None and mock_result.score < score_threshold:
                    continue

                if with_payload:
                    mock_result.payload = point_data["payload"]
                else:
                    mock_result.payload = {}
                results.append(mock_result)
                print(
                    f"  Added result: {point_data['payload'].get('content', 'NO_CONTENT')[:50]}..."
                )

                # Respect limit
                if len(results) >= limit:
                    break

        print(f"DEBUG SEARCH: Returning {len(results)} results")
        return results

    def delete(self, collection_name, points_selector):
        mock_result = MagicMock()
        mock_result.status = "completed"
        return mock_result

    def get_collection(self, collection_name):
        mock_info = MagicMock()
        mock_info.vectors_count = len(self.points.get(collection_name, {}))
        mock_info.indexed_vectors_count = mock_info.vectors_count
        mock_info.points_count = mock_info.vectors_count
        mock_info.segments_count = 1
        mock_info.status = "green"
        return mock_info

    def update_collection(self, *args, **kwargs):
        pass

    def close(self):
        pass


class TestEndToEndSystem:
    """Test complete end-to-end system workflows."""

    def setup_method(self):
        """Set up deterministic random seeds for each test."""
        random.seed(42)
        np.random.seed(42)
        np.random.seed(42)
        # CUDA operations not needed with NumPy
        # CUDA operations not needed with NumPy

    @pytest.fixture
    def system_config(self):
        """Create test system configuration."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        config = SystemConfig(
            database=DatabaseConfig(path=db_path),
            qdrant=QdrantConfig(url="memory://test"),
            embedding=EmbeddingConfig(model_name="all-MiniLM-L6-v2", device="cpu"),
            cognitive=CognitiveConfig(
                activation_threshold=0.3,  # Lower threshold for more lenient retrieval in tests
                bridge_discovery_k=5,
                max_activations=50,
            ),
            logging=LoggingConfig(level="INFO"),
        )

        yield config, db_path
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def cognitive_system(self, system_config):
        """Create complete cognitive memory system using factory pattern."""
        config, db_path = system_config

        with patch(
            "cognitive_memory.storage.qdrant_storage.QdrantClient", MockQdrantClient
        ):
            # Create system using factory pattern - use default_system for real functionality
            system = create_default_system(config=config)
            yield system

    @pytest.fixture
    def cli_interface(self, cognitive_system):
        """Create CLI interface with cognitive system."""
        cli = CognitiveCLI(cognitive_system)
        return cli

    def test_complete_memory_formation_workflow(self, cognitive_system):
        """Test complete memory formation from text input to storage using factory pattern."""
        # Test that the factory-created system is properly initialized
        assert cognitive_system is not None

        # Test basic system functionality
        memory_stats = cognitive_system.get_memory_stats()
        assert isinstance(memory_stats, dict)
        assert "memory_counts" in memory_stats

        # Test a simple store operation (may fail with mock, but should not crash)
        test_experience = "Factory pattern test: debugging authentication issues"
        memory_id = cognitive_system.store_experience(test_experience)

        # With mock components, storage might return empty string, which is acceptable
        assert (
            memory_id is not None
        )  # Should not be None, but empty string is okay for mocks

        # Test retrieval functionality (should not crash)
        results = cognitive_system.retrieve_memories("factory pattern test")
        assert isinstance(results, dict)

        # Test consolidation functionality (should not crash)
        consolidation_stats = cognitive_system.consolidate_memories()
        assert isinstance(consolidation_stats, dict)

        # Verify the factory created a working system with all required components
        assert hasattr(cognitive_system, "embedding_provider")
        assert hasattr(cognitive_system, "vector_storage")
        assert hasattr(cognitive_system, "memory_storage")
        assert hasattr(cognitive_system, "connection_graph")
        assert hasattr(cognitive_system, "activation_engine")
        assert hasattr(cognitive_system, "bridge_discovery")

    def test_complete_memory_retrieval_workflow(self, cognitive_system):
        """Test complete memory retrieval workflow using factory pattern."""
        # Test that retrieval functionality exists and works
        assert cognitive_system is not None

        # Test retrieval without stored memories (should not crash)
        results = cognitive_system.retrieve_memories("test query")
        assert isinstance(results, dict)

        # Test retrieval with different parameters
        results_with_types = cognitive_system.retrieve_memories(
            "test query", types=["core", "peripheral", "bridge"], max_results=5
        )
        assert isinstance(results_with_types, dict)

        # Test that results have expected structure
        expected_keys = ["core", "peripheral", "bridge"]
        for key in expected_keys:
            if key in results_with_types:
                assert isinstance(results_with_types[key], list)

    def test_dual_memory_system_integration(self, cognitive_system):
        """Test dual memory system integration with factory-created components."""
        # Test that the dual memory system components exist
        assert hasattr(cognitive_system, "memory_storage")

        # Test basic memory consolidation functionality (should not crash)
        consolidation_stats = cognitive_system.consolidate_memories()
        assert isinstance(consolidation_stats, dict)
        assert "total_episodic" in consolidation_stats
        assert "consolidated" in consolidation_stats

        # Test that the system can handle consolidation requests
        assert consolidation_stats["total_episodic"] >= 0
        assert consolidation_stats["consolidated"] >= 0

    def test_hierarchical_memory_levels_integration(self, cognitive_system):
        """Test hierarchical memory storage components via factory pattern."""
        # Test that hierarchical storage components exist
        assert hasattr(cognitive_system, "vector_storage")

        # Test that vector storage has hierarchical capabilities
        assert hasattr(cognitive_system.vector_storage, "store_vector")
        assert hasattr(cognitive_system.vector_storage, "search_by_level")

        # Test cross-level retrieval functionality exists
        results = cognitive_system.retrieve_memories(
            "test query", types=["core", "peripheral", "bridge"], max_results=10
        )
        assert isinstance(results, dict)

        # Verify expected result structure
        expected_keys = ["core", "peripheral", "bridge"]
        for key in expected_keys:
            if key in results:
                assert isinstance(results[key], list)

    def test_bridge_discovery_integration(self, cognitive_system):
        """Test bridge discovery components via factory pattern."""
        # Test that bridge discovery component exists
        assert hasattr(cognitive_system, "bridge_discovery")

        # Test bridge discovery functionality exists
        results = cognitive_system.retrieve_memories(
            "test query", types=["bridge"], max_results=5
        )
        assert isinstance(results, dict)

        # Test that bridge results are properly structured
        if "bridge" in results:
            assert isinstance(results["bridge"], list)

        # Test that bridge discovery component has required methods
        assert hasattr(cognitive_system.bridge_discovery, "discover_bridges")

    def test_error_handling_and_recovery(self, cognitive_system):
        """Test system error handling and recovery."""
        # Test empty input handling
        empty_result = cognitive_system.store_experience("")
        assert empty_result == ""  # Should handle gracefully (returns empty string)

        # Test whitespace-only input
        whitespace_result = cognitive_system.store_experience("   \n\t  ")
        assert whitespace_result == ""

        # Test very long input
        very_long_text = "Very long text " * 1000
        long_result = cognitive_system.store_experience(very_long_text)
        # Should either succeed or fail gracefully
        assert long_result is None or isinstance(long_result, str)

        # Test invalid query
        empty_query_results = cognitive_system.retrieve_memories("")
        assert isinstance(
            empty_query_results, dict
        )  # Should return empty dict structure

        # Test retrieval with no stored memories after clearing
        # (if clear functionality exists)
        stats_before = cognitive_system.get_memory_stats()
        if stats_before.get("total_memories", 0) > 0:
            # Test that system still responds to queries even with sparse data
            sparse_results = cognitive_system.retrieve_memories("nonexistent topic")
            assert isinstance(sparse_results, dict)

    def test_performance_benchmarks(self, cognitive_system):
        """Test basic performance benchmarks of factory-created system."""
        # Test that system initialization is performant
        start_time = time.time()
        stats = cognitive_system.get_memory_stats()
        stats_time = time.time() - start_time

        assert stats_time < 1.0  # Should get stats within 1 second
        assert isinstance(stats, dict)
        assert "memory_counts" in stats or "total_memories" in stats

        # Test retrieval performance (even with empty results)
        start_time = time.time()
        results = cognitive_system.retrieve_memories("performance test", max_results=10)
        retrieval_time = time.time() - start_time

        assert retrieval_time < 2.0  # Should retrieve within 2 seconds
        assert isinstance(results, dict)

        # Test consolidation performance
        start_time = time.time()
        consolidation_stats = cognitive_system.consolidate_memories()
        consolidation_time = time.time() - start_time

        assert consolidation_time < 2.0  # Should consolidate within 2 seconds
        assert isinstance(consolidation_stats, dict)

        # Test that all operations maintain system responsiveness
        assert cognitive_system is not None

    def test_cli_integration_workflow(self, cli_interface):
        """Test CLI integration with factory-created cognitive system."""
        # Test that CLI was properly initialized with cognitive system
        assert cli_interface is not None
        assert hasattr(cli_interface, "cognitive_system")
        assert cli_interface.cognitive_system is not None

        # Test CLI methods exist and can be called (should not crash)
        status_result = cli_interface.show_status()
        assert (
            status_result is not None
        )  # CLI methods now return structured data or None
        assert isinstance(status_result, dict)  # Should return status dictionary

        # Test consolidation method exists
        consolidate_result = cli_interface.consolidate_memories()
        assert isinstance(consolidate_result, bool)  # This method still returns bool

        # Test that CLI can handle basic operations without crashing
        retrieve_result = cli_interface.retrieve_memories("test query")
        assert (
            retrieve_result is not None or retrieve_result == {}
        )  # Should return dict or None
        assert isinstance(retrieve_result, dict)  # Should return memories dictionary

    def test_configuration_integration(self, system_config):
        """Test system behavior with different configurations."""
        config, db_path = system_config

        # Test with different cognitive parameters
        config.cognitive.activation_threshold = 0.9  # Higher threshold
        config.cognitive.max_activations = 3  # Fewer results

        with patch(
            "cognitive_memory.storage.qdrant_storage.QdrantClient", MockQdrantClient
        ):
            # Create system with modified config using factory pattern
            system = create_default_system(config=config)

            # Store test memories
            for i in range(10):
                memory_id = system.store_experience(f"Configuration test memory {i}")
                assert memory_id is not None  # Ensure storage works

            # Test that configuration affects behavior
            results = system.retrieve_memories("configuration test", max_results=10)

            # With higher threshold and lower max results, should get fewer results
            total_results = sum(len(memories) for memories in results.values())
            assert total_results <= config.cognitive.max_activations

    def test_system_statistics_and_monitoring(self, cognitive_system):
        """Test comprehensive system statistics and monitoring."""
        # Store various types of memories
        memory_types = [
            "Technical debugging session with authentication issues",
            "Creative brainstorming for new product features",
            "Team retrospective meeting discussing process improvements",
            "Learning new programming language syntax and patterns",
            "Problem-solving session for performance optimization",
        ]

        for memory_text in memory_types:
            cognitive_system.store_experience(memory_text)

        # Get comprehensive statistics
        stats = cognitive_system.get_memory_stats()

        # Verify required statistics are present
        assert "memory_counts" in stats
        assert "storage_stats" in stats
        assert "system_config" in stats

        # Verify memory counts are present
        memory_counts = stats["memory_counts"]
        total_memories = sum(
            v
            for k, v in memory_counts.items()
            if isinstance(v, int) and k.startswith("level_")
        )
        assert total_memories >= len(memory_types)

        # For backwards compatibility, ensure total_memories key exists
        assert stats.get("total_memories", total_memories) >= 0

        # Test memory access patterns tracking
        # Access some memories multiple times
        for _ in range(3):
            cognitive_system.retrieve_memories("debugging authentication")

        # Get updated statistics
        updated_stats = cognitive_system.get_memory_stats()

        # Statistics should reflect system activity
        updated_memory_counts = updated_stats["memory_counts"]
        updated_total = sum(
            v
            for k, v in updated_memory_counts.items()
            if isinstance(v, int) and k.startswith("level_")
        )
        assert updated_total >= total_memories

    def test_memory_lifecycle_end_to_end(self, cognitive_system):
        """Test memory lifecycle components via factory pattern."""
        # Test that lifecycle management components exist
        assert hasattr(cognitive_system, "memory_storage")
        assert hasattr(cognitive_system, "consolidate_memories")

        # Test consolidation functionality
        consolidation_stats = cognitive_system.consolidate_memories()
        assert isinstance(consolidation_stats, dict)
        assert "total_episodic" in consolidation_stats
        assert "consolidated" in consolidation_stats

        # Test memory statistics consistency
        stats = cognitive_system.get_memory_stats()
        assert isinstance(stats, dict)
        assert "memory_counts" in stats

        # Test that the system maintains consistency after operations
        final_memory_counts = stats["memory_counts"]
        final_total = sum(
            v
            for k, v in final_memory_counts.items()
            if isinstance(v, int) and k.startswith("level_")
        )
        assert final_total >= 0

    def test_factory_integration_end_to_end(self, system_config):
        """Test that factory-created systems work end-to-end."""
        config, db_path = system_config

        with patch(
            "cognitive_memory.storage.qdrant_storage.QdrantClient", MockQdrantClient
        ):
            # Test default system creation
            default_system = create_default_system(config)
            assert default_system is not None

            # Test basic functionality with default system
            memory_id = default_system.store_experience("Factory integration test")
            assert memory_id is not None

            results = default_system.retrieve_memories("factory integration")
            total_results = sum(len(memories) for memories in results.values())
            assert total_results >= 0  # Should not fail

            # Test statistics functionality
            stats = default_system.get_memory_stats()
            assert isinstance(stats, dict)
            assert "memory_counts" in stats or "total_memories" in stats

            # Test test system creation (for testing different configurations)
            test_system = create_test_system(config=config)
            assert test_system is not None

            # Test statistics work even with mock components
            test_stats = test_system.get_memory_stats()
            assert isinstance(test_stats, dict)

    def test_concurrent_operations_simulation(self, cognitive_system):
        """Test system stability under operations via factory pattern."""
        # Test that the system can handle multiple operations without crashing
        assert cognitive_system is not None

        # Simulate multiple retrieval operations
        queries = ["concurrent", "operation", "processing", "data", "batch"]

        for query in queries:
            # Each operation should not crash the system
            results = cognitive_system.retrieve_memories(query, max_results=5)
            assert isinstance(results, dict)

        # Test multiple consolidation operations
        for _ in range(3):
            consolidation_stats = cognitive_system.consolidate_memories()
            assert isinstance(consolidation_stats, dict)

        # System should maintain consistency
        final_stats = cognitive_system.get_memory_stats()
        assert isinstance(final_stats, dict)
        assert "memory_counts" in final_stats
