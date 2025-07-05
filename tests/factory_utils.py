"""
Test utilities for cognitive memory system factory testing.

Provides mock components, test systems, and utilities for testing
the factory pattern and system initialization.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np

from cognitive_memory.core.config import SystemConfig
from cognitive_memory.core.interfaces import (
    ActivationEngine,
    BridgeDiscovery,
    CognitiveSystem,
    ConnectionGraph,
    EmbeddingProvider,
    MemoryStorage,
    VectorStorage,
)
from cognitive_memory.core.memory import (
    ActivationResult,
    BridgeMemory,
    CognitiveMemory,
    SearchResult,
)

# Mock Components for Testing


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing factory pattern."""

    def __init__(self, vector_size: int = 512):
        self.vector_size = vector_size
        self.call_count = 0
        self.last_input = None

    def encode(self, text: str) -> np.ndarray:
        """Return deterministic embedding based on text hash."""
        self.call_count += 1
        self.last_input = text
        # Create deterministic embedding
        hash_val = hash(text) % 1000000
        np.random.seed(hash_val)
        return np.random.randn(self.vector_size)

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        """Return batch embeddings."""
        embeddings = [self.encode(text) for text in texts]
        return np.stack(embeddings)


class MockVectorStorage(VectorStorage):
    """Mock vector storage for testing factory pattern."""

    def __init__(self):
        self.stored_vectors: dict[str, np.ndarray] = {}
        self.stored_metadata: dict[str, dict[str, Any]] = {}
        self.search_results: list[SearchResult] = []
        self.call_counts = {"store": 0, "search": 0, "delete": 0, "update": 0}

    def store_vector(
        self, id: str, vector: np.ndarray, metadata: dict[str, Any]
    ) -> None:
        """Store vector with metadata."""
        self.call_counts["store"] += 1
        self.stored_vectors[id] = vector.copy()
        self.stored_metadata[id] = metadata.copy()

    def search_similar(
        self, query_vector: np.ndarray, k: int, filters: dict | None = None
    ) -> list[SearchResult]:
        """Return mock search results."""
        self.call_counts["search"] += 1
        return self.search_results[:k]

    def delete_vector(self, id: str) -> bool:
        """Delete vector."""
        self.call_counts["delete"] += 1
        if id in self.stored_vectors:
            del self.stored_vectors[id]
            del self.stored_metadata[id]
            return True
        return False

    def update_vector(
        self, id: str, vector: np.ndarray, metadata: dict[str, Any]
    ) -> bool:
        """Update an existing vector and its metadata."""
        self.call_counts["update"] += 1
        if id in self.stored_vectors:
            self.stored_vectors[id] = vector.copy()
            self.stored_metadata[id] = metadata.copy()
            return True
        return False

    def delete_vectors_by_ids(self, memory_ids: list[str]) -> list[str]:
        """Delete vectors by their IDs. Returns list of successfully deleted memory IDs."""
        self.call_counts["delete"] += len(memory_ids)
        successfully_deleted = []
        for memory_id in memory_ids:
            if memory_id in self.stored_vectors:
                del self.stored_vectors[memory_id]
                del self.stored_metadata[memory_id]
                successfully_deleted.append(memory_id)
        return successfully_deleted

    def get_collection_stats(self) -> dict[str, Any]:
        """Get collection statistics."""
        return {
            "vector_count": len(self.stored_vectors),
            "collection_size": sum(v.nbytes for v in self.stored_vectors.values()),
        }

    def clear_collection(self) -> None:
        """Clear all stored vectors."""
        self.stored_vectors.clear()
        self.stored_metadata.clear()


class MockMemoryStorage(MemoryStorage):
    """Mock memory storage for testing factory pattern."""

    def __init__(self):
        self.stored_memories: dict[str, CognitiveMemory] = {}
        self.call_counts = {
            "store": 0,
            "retrieve": 0,
            "update": 0,
            "delete": 0,
            "get_by_level": 0,
        }

    def store_memory(self, memory: CognitiveMemory) -> bool:
        """Store memory."""
        self.call_counts["store"] += 1
        self.stored_memories[memory.id] = memory
        return True

    def retrieve_memory(self, memory_id: str) -> CognitiveMemory | None:
        """Retrieve memory by ID."""
        self.call_counts["retrieve"] += 1
        return self.stored_memories.get(memory_id)

    def update_memory(self, memory: CognitiveMemory) -> bool:
        """Update existing memory."""
        self.call_counts["update"] += 1
        if memory.id in self.stored_memories:
            self.stored_memories[memory.id] = memory
            return True
        return False

    def delete_memory(self, memory_id: str) -> bool:
        """Delete memory."""
        self.call_counts["delete"] += 1
        if memory_id in self.stored_memories:
            del self.stored_memories[memory_id]
            return True
        return False

    def get_memories_by_level(self, level: int) -> list[CognitiveMemory]:
        """Get all memories at a specific hierarchy level."""
        self.call_counts["get_by_level"] += 1
        return [m for m in self.stored_memories.values() if m.hierarchy_level == level]

    def get_memory_stats(self) -> dict[str, Any]:
        """Get memory storage statistics."""
        return {
            "total_memories": len(self.stored_memories),
            "episodic_count": len(
                [
                    m
                    for m in self.stored_memories.values()
                    if m.memory_type == "episodic"
                ]
            ),
            "semantic_count": len(
                [
                    m
                    for m in self.stored_memories.values()
                    if m.memory_type == "semantic"
                ]
            ),
        }

    def get_memories_by_source_path(self, source_path: str) -> list[CognitiveMemory]:
        """Get memories by source file path from metadata."""
        return [
            m
            for m in self.stored_memories.values()
            if hasattr(m, "source_path") and m.source_path == source_path
        ]

    def delete_memories_by_source_path(self, source_path: str) -> int:
        """Delete all memories associated with a source file path. Returns count of deleted memories."""
        to_delete = [
            memory_id
            for memory_id, memory in self.stored_memories.items()
            if hasattr(memory, "source_path") and memory.source_path == source_path
        ]
        for memory_id in to_delete:
            del self.stored_memories[memory_id]
        return len(to_delete)

    def get_memories_by_tags(self, tags: list[str]) -> list[CognitiveMemory]:
        """Get memories that have any of the specified tags."""
        return [
            m
            for m in self.stored_memories.values()
            if hasattr(m, "tags") and any(tag in getattr(m, "tags", []) for tag in tags)
        ]

    def delete_memories_by_tags(self, tags: list[str]) -> int:
        """Delete memories that have any of the specified tags. Returns count of deleted memories."""
        to_delete = [
            memory_id
            for memory_id, memory in self.stored_memories.items()
            if hasattr(memory, "tags")
            and any(tag in getattr(memory, "tags", []) for tag in tags)
        ]
        for memory_id in to_delete:
            del self.stored_memories[memory_id]
        return len(to_delete)

    def delete_memories_by_ids(self, memory_ids: list[str]) -> int:
        """Delete memories by their IDs. Returns count of deleted memories."""
        deleted_count = 0
        for memory_id in memory_ids:
            if memory_id in self.stored_memories:
                del self.stored_memories[memory_id]
                deleted_count += 1
        return deleted_count


class MockConnectionGraph(ConnectionGraph):
    """Mock connection graph for testing factory pattern."""

    def __init__(self):
        self.connections: dict[str, list[CognitiveMemory]] = {}
        self.connection_strengths: dict[tuple[str, str], float] = {}
        self.connection_types: dict[tuple[str, str], str] = {}
        self.call_counts = {"add": 0, "get": 0}
        self.stored_memories: dict[str, CognitiveMemory] = {}

    def add_connection(
        self,
        source_id: str,
        target_id: str,
        strength: float,
        connection_type: str = "associative",
    ) -> bool:
        """Add connection between memories."""
        self.call_counts["add"] += 1
        self.connection_strengths[(source_id, target_id)] = strength
        self.connection_types[(source_id, target_id)] = connection_type
        return True

    def get_connections(
        self, memory_id: str, min_strength: float = 0.0
    ) -> list[CognitiveMemory]:
        """Get connected memories above minimum strength threshold."""
        self.call_counts["get"] += 1
        connected_memories = []
        for (source_id, target_id), strength in self.connection_strengths.items():
            if source_id == memory_id and strength >= min_strength:
                if target_id in self.stored_memories:
                    connected_memories.append(self.stored_memories[target_id])
        return connected_memories

    def update_connection_strength(
        self, source_id: str, target_id: str, new_strength: float
    ) -> bool:
        """Update the strength of an existing connection."""
        key = (source_id, target_id)
        if key in self.connection_strengths:
            self.connection_strengths[key] = new_strength
            return True
        return False

    def remove_connection(self, source_id: str, target_id: str) -> bool:
        """Remove a connection between memories."""
        key = (source_id, target_id)
        if key in self.connection_strengths:
            del self.connection_strengths[key]
            del self.connection_types[key]
            return True
        return False

    def add_memory_for_connections(self, memory: CognitiveMemory) -> None:
        """Add memory to support connection queries."""
        self.stored_memories[memory.id] = memory

    def get_graph_stats(self) -> dict[str, Any]:
        """Get graph statistics."""
        return {
            "node_count": len(self.stored_memories),
            "edge_count": len(self.connection_strengths),
            "average_degree": len(self.connection_strengths)
            / max(len(self.stored_memories), 1),
        }


class MockActivationEngine(ActivationEngine):
    """Mock activation engine for testing factory pattern."""

    def __init__(self):
        self.activation_result: ActivationResult = ActivationResult()
        self.call_count = 0

    def activate_memories(
        self, context: np.ndarray, threshold: float, max_activations: int = 50
    ) -> ActivationResult:
        """Return mock activation result."""
        self.call_count += 1
        return self.activation_result


class MockBridgeDiscovery(BridgeDiscovery):
    """Mock bridge discovery for testing factory pattern."""

    def __init__(self):
        self.bridge_results: list[BridgeMemory] = []
        self.call_count = 0

    def discover_bridges(
        self, context: np.ndarray, activated: list[CognitiveMemory], k: int = 5
    ) -> list[BridgeMemory]:
        """Return mock bridge results."""
        self.call_count += 1
        return self.bridge_results[:k]


class MockCognitiveSystem(CognitiveSystem):
    """Mock cognitive system for testing factory pattern."""

    def __init__(self):
        self.stored_experiences: list[str] = []
        self.search_results: list[SearchResult] = []
        self.activation_results: list[ActivationResult] = []
        self.call_counts = {"store": 0, "retrieve": 0, "activate": 0, "consolidate": 0}

    def store_experience(
        self, content: str, context: dict[str, Any] | None = None
    ) -> str:
        """Store experience and return ID."""
        self.call_counts["store"] += 1
        experience_id = f"exp_{len(self.stored_experiences)}"
        self.stored_experiences.append(content)
        return experience_id

    def retrieve_memories(
        self, query: str, max_results: int = 10
    ) -> list[SearchResult]:
        """Return mock search results."""
        self.call_counts["retrieve"] += 1
        return self.search_results[:max_results]

    def activate_memory_network(
        self, query: str, max_results: int = 10
    ) -> list[ActivationResult]:
        """Return mock activation results."""
        self.call_counts["activate"] += 1
        return self.activation_results[:max_results]

    def consolidate_memories(self) -> dict[str, Any]:
        """Return mock consolidation results."""
        self.call_counts["consolidate"] += 1
        return {"consolidated": len(self.stored_experiences)}

    def get_memory_stats(self) -> dict[str, Any]:
        """Return mock memory statistics."""
        return {
            "total_experiences": len(self.stored_experiences),
            "system_type": "mock",
        }


# Factory Test Utilities


def create_mock_system() -> MockCognitiveSystem:
    """
    Create system with all mock components for unit testing.

    Returns:
        MockCognitiveSystem: Fully mocked system for isolated unit tests
    """
    return MockCognitiveSystem()


def create_partial_mock_system(**real_components) -> dict[str, Any]:
    """
    Create system components with selective real/mock component mixing.

    Args:
        **real_components: Real components to use instead of mocks

    Returns:
        Dict with components ready for factory injection
    """
    components = {
        "embedding_provider": MockEmbeddingProvider(),
        "vector_storage": MockVectorStorage(),
        "memory_storage": MockMemoryStorage(),
        "connection_graph": MockConnectionGraph(),
        "activation_engine": MockActivationEngine(),
        "bridge_discovery": MockBridgeDiscovery(),
    }

    # Override with real components
    components.update(real_components)

    return components


@dataclass
class FactoryTestResult:
    """Results from factory testing operations."""

    success: bool
    system: CognitiveSystem | None
    error: str | None
    component_types: dict[str, str]
    validation_results: dict[str, bool]


def run_factory_creation_test(factory_func, *args, **kwargs) -> FactoryTestResult:
    """
    Test factory function creation with comprehensive validation.

    Args:
        factory_func: Factory function to test
        *args: Arguments for factory function
        **kwargs: Keyword arguments for factory function

    Returns:
        FactoryTestResult: Comprehensive test results
    """
    try:
        system = factory_func(*args, **kwargs)

        # Validate system creation
        if system is None:
            return FactoryTestResult(
                success=False,
                system=None,
                error="Factory returned None",
                component_types={},
                validation_results={},
            )

        # Check component types
        component_types = {}
        validation_results = {}

        if hasattr(system, "embedding_provider"):
            component_types["embedding_provider"] = type(
                system.embedding_provider
            ).__name__
            validation_results["embedding_provider"] = isinstance(
                system.embedding_provider, EmbeddingProvider
            )

        if hasattr(system, "vector_storage"):
            component_types["vector_storage"] = type(system.vector_storage).__name__
            validation_results["vector_storage"] = isinstance(
                system.vector_storage, VectorStorage
            )

        if hasattr(system, "memory_storage"):
            component_types["memory_storage"] = type(system.memory_storage).__name__
            validation_results["memory_storage"] = isinstance(
                system.memory_storage, MemoryStorage
            )

        if hasattr(system, "connection_graph"):
            component_types["connection_graph"] = type(system.connection_graph).__name__
            validation_results["connection_graph"] = isinstance(
                system.connection_graph, ConnectionGraph
            )

        if hasattr(system, "activation_engine"):
            component_types["activation_engine"] = type(
                system.activation_engine
            ).__name__
            validation_results["activation_engine"] = isinstance(
                system.activation_engine, ActivationEngine
            )

        if hasattr(system, "bridge_discovery"):
            component_types["bridge_discovery"] = type(system.bridge_discovery).__name__
            validation_results["bridge_discovery"] = isinstance(
                system.bridge_discovery, BridgeDiscovery
            )

        # Test basic functionality
        try:
            stats = system.get_memory_stats()
            validation_results["basic_functionality"] = isinstance(stats, dict)
        except Exception as e:
            validation_results["basic_functionality"] = False
            validation_results["functionality_error"] = str(e)

        return FactoryTestResult(
            success=True,
            system=system,
            error=None,
            component_types=component_types,
            validation_results=validation_results,
        )

    except Exception as e:
        return FactoryTestResult(
            success=False,
            system=None,
            error=str(e),
            component_types={},
            validation_results={},
        )


def validate_interface_compliance(
    component: Any, expected_interface: type
) -> tuple[bool, list[str]]:
    """
    Validate that a component implements the expected interface.

    Args:
        component: Component to validate
        expected_interface: Expected interface class

    Returns:
        Tuple of (is_compliant, missing_methods)
    """
    if not isinstance(component, expected_interface):
        return False, [f"Component is not instance of {expected_interface.__name__}"]

    missing_methods = []
    for method_name in dir(expected_interface):
        if not method_name.startswith("_") and callable(
            getattr(expected_interface, method_name, None)
        ):
            if not hasattr(component, method_name) or not callable(
                getattr(component, method_name)
            ):
                missing_methods.append(method_name)

    return len(missing_methods) == 0, missing_methods


def create_test_config_override(**overrides) -> SystemConfig:
    """
    Create test configuration with specific overrides.

    Args:
        **overrides: Configuration parameters to override

    Returns:
        SystemConfig: Modified test configuration
    """
    config = SystemConfig.from_env()

    # Apply overrides using dataclass replace functionality
    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return config


# Mock dependency injection utilities


class MockDependencyProvider:
    """Provides mock dependencies for testing factory patterns."""

    def __init__(self):
        self.provided_components: dict[str, Any] = {}
        self.call_counts: dict[str, int] = {}

    def get_component(self, component_type: str) -> Any:
        """Get mock component by type."""
        self.call_counts[component_type] = self.call_counts.get(component_type, 0) + 1

        if component_type in self.provided_components:
            return self.provided_components[component_type]

        # Default mock components
        mock_components = {
            "embedding_provider": MockEmbeddingProvider(),
            "vector_storage": MockVectorStorage(),
            "memory_storage": MockMemoryStorage(),
            "connection_graph": MockConnectionGraph(),
            "activation_engine": MockActivationEngine(),
            "bridge_discovery": MockBridgeDiscovery(),
        }

        return mock_components.get(component_type)

    def override_component(self, component_type: str, component: Any) -> None:
        """Override a specific component."""
        self.provided_components[component_type] = component

    def reset(self) -> None:
        """Reset all overrides and counters."""
        self.provided_components.clear()
        self.call_counts.clear()
