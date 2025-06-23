"""
Integration tests for the complete storage pipeline.

Tests the full integration of Qdrant vector storage, SQLite persistence,
dual memory system, and their interaction with the encoding system.
"""

import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from cognitive_memory.core.config import SystemConfig
from cognitive_memory.core.memory import CognitiveMemory
from cognitive_memory.encoding.cognitive_encoder import CognitiveEncoder
from cognitive_memory.storage import (
    MemoryType,
    create_dual_memory_system,
    create_hierarchical_storage,
)


class MockQdrantClient:
    """Mock Qdrant client for testing without external dependencies."""

    def __init__(self, project_id: str = "test_project_12345678", **kwargs):
        # Accept any keyword arguments to match QdrantClient signature
        self.project_id = project_id
        self.collections = []
        self.points = {}

    def get_collections(self):
        """Mock get collections."""
        mock_collections = MagicMock()
        mock_collections.collections = [
            MagicMock(name=f"{self.project_id}_concepts"),
            MagicMock(name=f"{self.project_id}_contexts"),
            MagicMock(name=f"{self.project_id}_episodes"),
        ]
        return mock_collections

    def create_collection(self, *args, **kwargs):
        """Mock create collection."""
        pass

    def upsert(self, collection_name, points):
        """Mock upsert."""
        if collection_name not in self.points:
            self.points[collection_name] = {}
        for point in points:
            self.points[collection_name][point.id] = point

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
        """Mock search with proper parameter handling and basic filtering."""
        # Return mock search results
        results = []
        if collection_name in self.points:
            points_to_search = self.points[collection_name]

            # Apply basic filtering if query_filter is provided
            filtered_points = []
            for point_id, point in points_to_search.items():
                include_point = True

                # Basic filter implementation for testing
                if query_filter and hasattr(query_filter, "must"):
                    for condition in query_filter.must:
                        if hasattr(condition, "key") and hasattr(condition, "match"):
                            filter_key = condition.key
                            filter_value = condition.match.value

                            # Check if point payload matches filter
                            if filter_key in point.payload:
                                if point.payload[filter_key] != filter_value:
                                    include_point = False
                                    break
                            else:
                                include_point = False
                                break

                if include_point:
                    filtered_points.append((point_id, point))

            # Return up to 'limit' results
            for point_id, point in filtered_points[:limit]:
                mock_result = MagicMock()
                mock_result.id = point_id
                mock_result.score = 0.9  # High similarity
                if with_payload:
                    mock_result.payload = point.payload
                else:
                    mock_result.payload = {}
                results.append(mock_result)
        return results

    def delete(self, collection_name, points_selector):
        """Mock delete."""
        mock_result = MagicMock()
        mock_result.status = MagicMock()
        mock_result.status.COMPLETED = "completed"
        mock_result.status = "completed"
        return mock_result

    def get_collection(self, collection_name):
        """Mock get collection info."""
        mock_info = MagicMock()
        mock_info.vectors_count = len(self.points.get(collection_name, {}))
        mock_info.indexed_vectors_count = mock_info.vectors_count
        mock_info.points_count = mock_info.vectors_count
        mock_info.segments_count = 1
        mock_info.status = "green"
        return mock_info

    def update_collection(self, *args, **kwargs):
        """Mock update collection."""
        pass

    def close(self):
        """Mock close."""
        pass


class TestStoragePipelineIntegration:
    """Test complete storage pipeline integration."""

    @pytest.fixture
    def mock_encoder(self):
        """Create a mock cognitive encoder for testing."""
        # Get dimensions from config
        config = SystemConfig.from_env()
        vector_size = config.embedding.embedding_dimension

        encoder = MagicMock(spec=CognitiveEncoder)

        # Mock encode method to return realistic vectors
        def mock_encode(text):
            # Return a vector with configured dimensions based on text hash
            hash_val = hash(text) % 1000
            vector = np.random.rand(vector_size) * 0.1 + (hash_val / 1000.0)
            return vector

        encoder.encode.side_effect = mock_encode
        encoder.encode_batch.side_effect = lambda texts: np.stack(
            [mock_encode(t) for t in texts]
        )

        return encoder

    @pytest.fixture
    def storage_pipeline(self, mock_encoder):
        """Create a complete storage pipeline for testing."""
        # Get dimensions from config
        config = SystemConfig.from_env()
        vector_size = config.embedding.embedding_dimension

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        # Create dual memory system (includes SQLite)
        dual_memory = create_dual_memory_system(db_path)

        # Mock Qdrant for vector storage
        with patch(
            "cognitive_memory.storage.qdrant_storage.QdrantClient", MockQdrantClient
        ):
            vector_storage = create_hierarchical_storage(
                vector_size=vector_size, project_id="test_project_12345678"
            )

        yield {
            "encoder": mock_encoder,
            "dual_memory": dual_memory,
            "vector_storage": vector_storage,
            "db_path": db_path,
        }

        Path(db_path).unlink(missing_ok=True)

    def test_end_to_end_memory_storage(self, storage_pipeline):
        """Test complete end-to-end memory storage workflow."""
        encoder = storage_pipeline["encoder"]
        dual_memory = storage_pipeline["dual_memory"]
        vector_storage = storage_pipeline["vector_storage"]

        # Create test experience
        experience_text = "I had a productive meeting with the AI research team today"

        # Encode the experience
        cognitive_embedding = encoder.encode(experience_text)

        # Create cognitive memory
        memory = CognitiveMemory(
            id="e2e_test_001",
            content=experience_text,
            memory_type="episodic",
            hierarchy_level=2,
            dimensions={
                "emotional": {"valence": 0.7, "arousal": 0.6},
                "temporal": {"recency": 0.9, "duration": 0.4},
                "contextual": {"location": 0.5, "topic": 0.8},
                "social": {"persons": 0.8, "relationships": 0.6},
            },
            timestamp=datetime.fromtimestamp(time.time()),
            strength=0.8,
            access_count=0,
            tags=["meeting", "AI", "research", "productive"],
        )

        # Store in dual memory system
        assert dual_memory.store_experience(memory)

        # Store vector representation
        metadata = {
            "memory_id": memory.id,
            "content": memory.content,
            "memory_type": memory.memory_type,
            "hierarchy_level": memory.hierarchy_level,
            "timestamp": memory.timestamp,
            "strength": memory.strength,
            "access_count": memory.access_count,
            "dimensions": memory.dimensions,
        }

        vector_storage.store_vector(memory.id, cognitive_embedding, metadata)

        # Verify storage in dual memory
        retrieved_memory = dual_memory.access_memory(memory.id)
        assert retrieved_memory is not None
        assert retrieved_memory.content == experience_text
        assert retrieved_memory.memory_type == "episodic"

        # Verify vector search
        query_embedding = encoder.encode("AI research team meeting")
        search_results = vector_storage.search_similar(query_embedding, k=5)

        assert len(search_results) > 0
        assert any(result.memory.id == memory.id for result in search_results)

    def test_hierarchical_memory_levels(self, storage_pipeline):
        """Test storage and retrieval across different hierarchy levels."""
        encoder = storage_pipeline["encoder"]
        dual_memory = storage_pipeline["dual_memory"]
        vector_storage = storage_pipeline["vector_storage"]

        # Create memories at different hierarchy levels
        memories = [
            # Level 0: Concept
            CognitiveMemory(
                id="concept_001",
                content="Artificial intelligence is transforming how we work",
                memory_type="semantic",
                hierarchy_level=0,
                dimensions={},
                timestamp=datetime.fromtimestamp(time.time()),
                strength=0.9,
                access_count=10,
            ),
            # Level 1: Context
            CognitiveMemory(
                id="context_001",
                content="AI research meetings typically involve technical discussions",
                memory_type="semantic",
                hierarchy_level=1,
                dimensions={},
                timestamp=datetime.fromtimestamp(time.time()),
                strength=0.8,
                access_count=5,
            ),
            # Level 2: Episode
            CognitiveMemory(
                id="episode_001",
                content="Today's AI meeting covered neural network architectures",
                memory_type="episodic",
                hierarchy_level=2,
                dimensions={},
                timestamp=datetime.fromtimestamp(time.time()),
                strength=0.7,
                access_count=1,
            ),
        ]

        # Store all memories
        for memory in memories:
            if memory.memory_type == "episodic":
                dual_memory.store_experience(memory)
            else:
                dual_memory.store_knowledge(memory)

            # Store vector representation
            embedding = encoder.encode(memory.content)
            metadata = {
                "memory_id": memory.id,
                "content": memory.content,
                "memory_type": memory.memory_type,
                "hierarchy_level": memory.hierarchy_level,
                "timestamp": memory.timestamp,
                "strength": memory.strength,
                "access_count": memory.access_count,
                "dimensions": memory.dimensions,
            }
            vector_storage.store_vector(memory.id, embedding, metadata)

        # Test level-specific searches
        for level in [0, 1, 2]:
            query_embedding = encoder.encode("AI research")
            level_results = vector_storage.search_by_level(
                query_embedding, level=level, k=5
            )

            # Should only return results from the specified level
            if level_results:
                assert all(
                    result.memory.hierarchy_level == level for result in level_results
                )

    def test_dual_memory_consolidation_workflow(self, storage_pipeline):
        """Test the complete dual memory consolidation workflow."""
        encoder = storage_pipeline["encoder"]
        dual_memory = storage_pipeline["dual_memory"]
        vector_storage = storage_pipeline["vector_storage"]

        # Create an episodic memory that's accessed frequently
        memory = CognitiveMemory(
            id="consolidation_test_001",
            content="Regular team standups improve project coordination",
            memory_type="episodic",
            hierarchy_level=2,
            dimensions={},
            timestamp=datetime.fromtimestamp(
                time.time() - (7 * 24 * 3600)
            ),  # 1 week old
            strength=0.8,
            access_count=0,
            tags=["standup", "team", "coordination"],
        )

        # Store in dual memory and vector storage
        dual_memory.store_experience(memory)

        embedding = encoder.encode(memory.content)
        metadata = {
            "memory_id": memory.id,
            "content": memory.content,
            "memory_type": memory.memory_type,
            "hierarchy_level": memory.hierarchy_level,
            "timestamp": memory.timestamp,
            "strength": memory.strength,
            "access_count": memory.access_count,
            "dimensions": memory.dimensions,
        }
        vector_storage.store_vector(memory.id, embedding, metadata)

        # Access the memory multiple times to build consolidation score
        for _ in range(5):
            dual_memory.access_memory(memory.id)
            time.sleep(0.01)  # Small delay between accesses

        # Trigger consolidation
        consolidation_stats = dual_memory.consolidate_memories()

        # Check consolidation results
        assert "candidates_identified" in consolidation_stats
        assert "memories_consolidated" in consolidation_stats

        # If consolidation occurred, verify semantic version was created
        if consolidation_stats["memories_consolidated"] > 0:
            semantic_id = f"{memory.id}_semantic"
            semantic_memory = dual_memory.access_memory(semantic_id)

            if semantic_memory:
                assert semantic_memory.memory_type == MemoryType.SEMANTIC.value
                assert semantic_memory.content == memory.content

    def test_vector_search_with_metadata_filtering(self, storage_pipeline):
        """Test vector search with metadata filtering."""
        encoder = storage_pipeline["encoder"]
        dual_memory = storage_pipeline["dual_memory"]
        vector_storage = storage_pipeline["vector_storage"]

        # Create memories with different types and tags
        memories = [
            CognitiveMemory(
                id="filter_test_001",
                content="Machine learning algorithms for prediction",
                memory_type="semantic",
                hierarchy_level=1,
                dimensions={},
                timestamp=datetime.fromtimestamp(time.time()),
                strength=0.9,
                access_count=5,
                tags=["ML", "algorithms", "prediction"],
            ),
            CognitiveMemory(
                id="filter_test_002",
                content="Deep learning neural networks architecture",
                memory_type="semantic",
                hierarchy_level=1,
                dimensions={},
                timestamp=datetime.fromtimestamp(time.time()),
                strength=0.8,
                access_count=3,
                tags=["DL", "neural", "architecture"],
            ),
            CognitiveMemory(
                id="filter_test_003",
                content="Attended machine learning conference last week",
                memory_type="episodic",
                hierarchy_level=2,
                dimensions={},
                timestamp=datetime.fromtimestamp(time.time()),
                strength=0.7,
                access_count=1,
                tags=["ML", "conference", "event"],
            ),
        ]

        # Store all memories
        for memory in memories:
            if memory.memory_type == "episodic":
                dual_memory.store_experience(memory)
            else:
                dual_memory.store_knowledge(memory)

            embedding = encoder.encode(memory.content)
            metadata = {
                "memory_id": memory.id,
                "content": memory.content,
                "memory_type": memory.memory_type,
                "hierarchy_level": memory.hierarchy_level,
                "timestamp": memory.timestamp,
                "strength": memory.strength,
                "access_count": memory.access_count,
            }
            vector_storage.store_vector(memory.id, embedding, metadata)

        # Test filtered search by memory type
        query_embedding = encoder.encode("machine learning")

        # Search only semantic memories
        semantic_results = vector_storage.search_similar(
            query_embedding, k=5, filters={"memory_type": "semantic"}
        )

        # Should only return semantic memories
        for result in semantic_results:
            assert result.memory.memory_type == "semantic"

        # Search only episodic memories
        episodic_results = vector_storage.search_similar(
            query_embedding, k=5, filters={"memory_type": "episodic"}
        )

        # Should only return episodic memories
        for result in episodic_results:
            assert result.memory.memory_type == "episodic"

    def test_memory_lifecycle_management(self, storage_pipeline):
        """Test complete memory lifecycle including decay and cleanup."""
        encoder = storage_pipeline["encoder"]
        dual_memory = storage_pipeline["dual_memory"]
        vector_storage = storage_pipeline["vector_storage"]

        # Create old episodic memory
        old_memory = CognitiveMemory(
            id="lifecycle_test_001",
            content="Old episodic memory for lifecycle test",
            memory_type="episodic",
            hierarchy_level=2,
            dimensions={},
            timestamp=datetime.fromtimestamp(
                time.time() - (40 * 24 * 3600)
            ),  # 40 days old
            strength=0.1,  # Very weak
            access_count=0,
        )

        # Create recent semantic memory
        recent_memory = CognitiveMemory(
            id="lifecycle_test_002",
            content="Recent semantic knowledge for lifecycle test",
            memory_type="semantic",
            hierarchy_level=1,
            dimensions={},
            timestamp=datetime.fromtimestamp(
                time.time() - (1 * 24 * 3600)
            ),  # 1 day old
            strength=0.9,
            access_count=10,
        )

        # Store both memories
        dual_memory.store_experience(old_memory)
        dual_memory.store_knowledge(recent_memory)

        for memory in [old_memory, recent_memory]:
            embedding = encoder.encode(memory.content)
            metadata = {
                "memory_id": memory.id,
                "content": memory.content,
                "memory_type": memory.memory_type,
                "hierarchy_level": memory.hierarchy_level,
                "timestamp": memory.timestamp,
                "strength": memory.strength,
                "access_count": memory.access_count,
                "dimensions": memory.dimensions,
            }
            vector_storage.store_vector(memory.id, embedding, metadata)

        # Run memory cleanup
        cleanup_stats = dual_memory.cleanup_expired_memories()

        # Check cleanup results
        assert "episodic_cleaned" in cleanup_stats
        assert "semantic_cleaned" in cleanup_stats

        # Verify old episodic memory might be cleaned
        # (depending on exact implementation and thresholds)
        _old_retrieved = dual_memory.access_memory(old_memory.id)

        # Recent semantic memory should still exist
        recent_retrieved = dual_memory.access_memory(recent_memory.id)
        assert recent_retrieved is not None

    def test_storage_statistics_and_monitoring(self, storage_pipeline):
        """Test storage statistics collection and monitoring."""
        encoder = storage_pipeline["encoder"]
        dual_memory = storage_pipeline["dual_memory"]
        vector_storage = storage_pipeline["vector_storage"]

        # Create various types of memories
        memories = [
            CognitiveMemory(
                id=f"stats_test_{i:03d}",
                content=f"Test memory {i} for statistics",
                memory_type="episodic" if i % 2 == 0 else "semantic",
                hierarchy_level=i % 3,
                dimensions={},
                timestamp=datetime.fromtimestamp(
                    time.time() - (i * 3600)
                ),  # Different ages
                strength=0.5 + (i % 5) * 0.1,  # Different strengths
                access_count=i % 10,  # Different access counts
                tags=[f"tag_{i}", "statistics", "test"],
            )
            for i in range(10)
        ]

        # Store all memories
        for memory in memories:
            if memory.memory_type == "episodic":
                dual_memory.store_experience(memory)
            else:
                dual_memory.store_knowledge(memory)

            embedding = encoder.encode(memory.content)
            metadata = {
                "memory_id": memory.id,
                "content": memory.content,
                "memory_type": memory.memory_type,
                "hierarchy_level": memory.hierarchy_level,
                "timestamp": memory.timestamp,
                "strength": memory.strength,
                "access_count": memory.access_count,
                "dimensions": memory.dimensions,
            }
            vector_storage.store_vector(memory.id, embedding, metadata)

        # Get dual memory statistics
        dual_stats = dual_memory.get_memory_stats()

        assert "episodic" in dual_stats
        assert "semantic" in dual_stats
        assert "consolidation" in dual_stats
        assert "access_patterns" in dual_stats

        # Check episodic stats
        episodic_stats = dual_stats["episodic"]
        assert "total_memories" in episodic_stats
        assert "average_strength" in episodic_stats
        assert episodic_stats["total_memories"] > 0

        # Check semantic stats
        semantic_stats = dual_stats["semantic"]
        assert "total_memories" in semantic_stats
        assert "average_strength" in semantic_stats
        assert semantic_stats["total_memories"] > 0

        # Get vector storage statistics
        vector_stats = vector_storage.get_storage_stats()

        for level in [0, 1, 2]:
            level_key = f"level_{level}"
            assert level_key in vector_stats
            assert "collection_name" in vector_stats[level_key]
            assert "vectors_count" in vector_stats[level_key]

    def test_error_handling_and_resilience(self, storage_pipeline):
        """Test error handling and system resilience."""
        encoder = storage_pipeline["encoder"]
        dual_memory = storage_pipeline["dual_memory"]
        vector_storage = storage_pipeline["vector_storage"]

        # Test handling of invalid memory data
        invalid_memory = CognitiveMemory(
            id="",  # Invalid empty ID
            content="Test memory with invalid data",
            memory_type="unknown_type",  # Invalid type
            hierarchy_level=5,  # Invalid level
            dimensions={},
            timestamp=datetime.fromtimestamp(time.time()),
            strength=2.0,  # Invalid strength > 1.0
            access_count=-1,  # Invalid negative count
        )

        # Storage should handle invalid data gracefully
        try:
            dual_memory.store_experience(invalid_memory)
        except Exception as e:
            # Should either succeed with sanitized data or fail gracefully
            assert isinstance(e, ValueError | TypeError)

        # Test retrieval of non-existent memory
        non_existent = dual_memory.access_memory("non_existent_id")
        assert non_existent is None

        # Test vector storage with invalid vector dimensions
        try:
            # Use half the configured dimension as wrong size
            config = SystemConfig.from_env()
            wrong_size = config.embedding.embedding_dimension // 2
            invalid_vector = np.random.rand(wrong_size)  # Wrong dimension
            metadata = {"memory_id": "test", "hierarchy_level": 2}
            vector_storage.store_vector("test_invalid", invalid_vector, metadata)
        except ValueError:
            # Should raise ValueError for wrong dimensions
            pass

        # Test search with empty results
        empty_query = encoder.encode("")  # Empty text
        empty_results = vector_storage.search_similar(empty_query, k=5)
        assert isinstance(empty_results, list)  # Should return empty list, not error
