"""
System factory for creating cognitive memory system instances.

This module provides factory functions for creating configured cognitive memory systems
with proper dependency injection and validation. Supports default configurations,
test overrides, and configuration-driven component selection.
"""

import os
from typing import Any, cast

from loguru import logger

from .core.cognitive_system import CognitiveMemorySystem
from .core.config import SystemConfig
from .core.interfaces import (
    ActivationEngine,
    BridgeDiscovery,
    CognitiveSystem,
    ConnectionGraph,
    EmbeddingProvider,
    MemoryStorage,
    VectorStorage,
)
from .core.logging_setup import setup_logging

# Global flag to track logging configuration
_logging_configured = False


class InitializationError(Exception):
    """Raised when system initialization fails."""

    pass


def create_default_system(config: SystemConfig | None = None) -> CognitiveMemorySystem:
    """
    Create system with default implementations and sensible defaults.

    Uses the most stable and well-tested implementations for production use:
    - SentenceBERTProvider for embeddings
    - HierarchicalMemoryStorage for vector storage
    - MemoryMetadataStore and ConnectionGraphStore for persistence
    - BasicActivationEngine for memory activation
    - SimpleBridgeDiscovery for bridge discovery
    - CognitiveDimensionExtractor for multi-dimensional encoding

    Args:
        config: Optional system configuration. If None, loads from environment.

    Returns:
        CognitiveMemorySystem: Fully configured system instance

    Raises:
        InitializationError: If any component fails to initialize
    """
    logger.info("Creating default cognitive memory system")

    # Load configuration
    if config is None:
        try:
            config = SystemConfig.from_env()
        except Exception as e:
            raise InitializationError(f"Failed to load configuration: {e}") from e

    # Setup logging based on configuration (only if not already configured)
    # Check if logging has already been set up (e.g., by CLI early setup)
    global _logging_configured
    if not _logging_configured:
        setup_logging(config.logging)
        _logging_configured = True

    try:
        # Import factory functions
        from .encoding.sentence_bert import create_sentence_bert_provider
        from .retrieval.basic_activation import BasicActivationEngine
        from .retrieval.bridge_discovery import SimpleBridgeDiscovery
        from .storage.qdrant_storage import create_hierarchical_storage
        from .storage.sqlite_persistence import create_sqlite_persistence

        # Create embedding provider
        embedding_provider = create_sentence_bert_provider(
            model_name=config.embedding.model_name
        )

        # Validate embedding provider
        if not isinstance(embedding_provider, EmbeddingProvider):
            raise InitializationError(
                f"Embedding provider does not implement EmbeddingProvider interface: {type(embedding_provider)}"
            )

        # Create vector storage
        # Parse Qdrant URL to extract host and port
        from urllib.parse import urlparse

        parsed_url = urlparse(config.qdrant.url)
        host = parsed_url.hostname or "localhost"
        port = parsed_url.port or 6333

        vector_storage = create_hierarchical_storage(
            vector_size=config.embedding.embedding_dimension,
            project_id=config.project_id,
            host=host,
            port=port,
            prefer_grpc=config.qdrant.prefer_grpc,
        )

        # Validate vector storage
        if not isinstance(vector_storage, VectorStorage):
            raise InitializationError(
                f"Vector storage does not implement VectorStorage interface: {type(vector_storage)}"
            )

        # Create memory and connection storage
        memory_storage, connection_graph = create_sqlite_persistence(
            db_path=config.database.path
        )

        # Validate storage components
        if not isinstance(memory_storage, MemoryStorage):
            raise InitializationError(
                f"Memory storage does not implement MemoryStorage interface: {type(memory_storage)}"
            )

        if not isinstance(connection_graph, ConnectionGraph):
            raise InitializationError(
                f"Connection graph does not implement ConnectionGraph interface: {type(connection_graph)}"
            )

        # Create activation engine
        activation_engine = BasicActivationEngine(
            memory_storage=memory_storage, connection_graph=connection_graph
        )

        # Validate activation engine
        if not isinstance(activation_engine, ActivationEngine):
            raise InitializationError(
                f"Activation engine does not implement ActivationEngine interface: {type(activation_engine)}"
            )

        # Create bridge discovery
        bridge_discovery = SimpleBridgeDiscovery(memory_storage=memory_storage)

        # Validate bridge discovery
        if not isinstance(bridge_discovery, BridgeDiscovery):
            raise InitializationError(
                f"Bridge discovery does not implement BridgeDiscovery interface: {type(bridge_discovery)}"
            )

        # Create cognitive system
        cognitive_system = CognitiveMemorySystem(
            embedding_provider=embedding_provider,
            vector_storage=vector_storage,
            memory_storage=memory_storage,
            connection_graph=connection_graph,
            activation_engine=activation_engine,
            bridge_discovery=bridge_discovery,
            config=config,
        )

        # Final validation
        if not isinstance(cognitive_system, CognitiveSystem):
            raise InitializationError(
                f"Cognitive system does not implement CognitiveSystem interface: {type(cognitive_system)}"
            )

        logger.info(
            "Default cognitive memory system created successfully",
            embedding_model=config.embedding.model_name,
            qdrant_url=config.qdrant.url,
            database_path=config.database.path,
        )

        return cognitive_system

    except ImportError as e:
        raise InitializationError(f"Failed to import required component: {e}") from e
    except Exception as e:
        raise InitializationError(f"Failed to create default system: {e}") from e


def create_test_system(**overrides: Any) -> CognitiveMemorySystem:
    """
    Create system with test stubs and component overrides for testing.

    Allows selective override of any component for unit testing while
    using default implementations for non-overridden components.

    Args:
        **overrides: Component overrides as keyword arguments:
            - embedding_provider: EmbeddingProvider implementation
            - vector_storage: VectorStorage implementation
            - memory_storage: MemoryStorage implementation
            - connection_graph: ConnectionGraph implementation
            - activation_engine: ActivationEngine implementation
            - bridge_discovery: BridgeDiscovery implementation
            - config: SystemConfig instance

    Returns:
        CognitiveMemorySystem: System with overridden components

    Raises:
        InitializationError: If component validation fails
    """
    logger.info(
        "Creating test cognitive memory system", overrides=list(overrides.keys())
    )

    try:
        # Start with default system
        default_system = create_default_system(overrides.get("config"))

        # Override components as specified
        components = {
            "embedding_provider": default_system.embedding_provider,
            "vector_storage": default_system.vector_storage,
            "memory_storage": default_system.memory_storage,
            "connection_graph": default_system.connection_graph,
            "activation_engine": default_system.activation_engine,
            "bridge_discovery": default_system.bridge_discovery,
            "config": default_system.config,
        }

        # Apply overrides with validation
        for component_name, override_value in overrides.items():
            if component_name in components:
                # Validate interface compliance
                expected_interface = _get_expected_interface(component_name)
                if expected_interface and not isinstance(
                    override_value, expected_interface
                ):
                    raise InitializationError(
                        f"Override component '{component_name}' does not implement required interface "
                        f"{expected_interface.__name__}: {type(override_value)}"
                    )
                components[component_name] = override_value
                logger.debug(f"Overrode component: {component_name}")

        # Create system with potentially overridden components
        test_system = CognitiveMemorySystem(
            embedding_provider=cast(
                EmbeddingProvider, components["embedding_provider"]
            ),
            vector_storage=cast(VectorStorage, components["vector_storage"]),
            memory_storage=cast(MemoryStorage, components["memory_storage"]),
            connection_graph=cast(ConnectionGraph, components["connection_graph"]),
            activation_engine=cast(ActivationEngine, components["activation_engine"]),
            bridge_discovery=cast(BridgeDiscovery, components["bridge_discovery"]),
            config=cast(SystemConfig, components["config"]),
        )

        logger.info(
            "Test cognitive memory system created successfully",
            overridden_components=list(overrides.keys()),
        )

        return test_system

    except Exception as e:
        raise InitializationError(f"Failed to create test system: {e}") from e


def create_system_from_config(config_path: str) -> CognitiveMemorySystem:
    """
    Create system from configuration file with custom implementations.

    Loads configuration from specified file and creates system with
    components selected based on configuration parameters.

    Args:
        config_path: Path to configuration file

    Returns:
        CognitiveMemorySystem: Configured system instance

    Raises:
        InitializationError: If configuration loading or system creation fails
    """
    logger.info("Creating cognitive memory system from config", config_path=config_path)

    if not os.path.exists(config_path):
        raise InitializationError(f"Configuration file not found: {config_path}")

    try:
        # Load environment variables from config file if it's .env
        if config_path.endswith(".env"):
            from dotenv import load_dotenv

            load_dotenv(config_path, override=True)
            config = SystemConfig.from_env()
        else:
            # For now, only support .env files
            # Future: support YAML, TOML, JSON configurations
            raise InitializationError(
                f"Unsupported configuration file format: {config_path}"
            )

        # Create system with loaded configuration
        return create_default_system(config)

    except Exception as e:
        raise InitializationError(f"Failed to create system from config: {e}") from e


def _get_expected_interface(component_name: str) -> type | None:
    """Get the expected interface type for a component name."""
    interface_map = {
        "embedding_provider": EmbeddingProvider,
        "vector_storage": VectorStorage,
        "memory_storage": MemoryStorage,
        "connection_graph": ConnectionGraph,
        "activation_engine": ActivationEngine,
        "bridge_discovery": BridgeDiscovery,
        "config": SystemConfig,
    }
    return interface_map.get(component_name)


def validate_system_health(
    system: CognitiveSystem, skip_memory_tests: bool = False
) -> dict[str, Any]:
    """
    Perform health checks on a cognitive system instance.

    Args:
        system: CognitiveSystem instance to validate
        skip_memory_tests: If True, skip tests that create/modify memories

    Returns:
        Dict with health check results
    """
    logger.info("Performing system health check", skip_memory_tests=skip_memory_tests)

    health_status: dict[str, Any] = {"healthy": True, "checks": {}, "errors": []}

    try:
        # Test basic system stats
        system.get_memory_stats()
        health_status["checks"]["stats"] = "✓ System stats accessible"

        # Skip memory tests if requested (e.g., in test environments)
        if not skip_memory_tests:
            # Test embedding with simple text
            test_memory_id = system.store_experience("Health check test memory")
            if test_memory_id:
                health_status["checks"]["storage"] = "✓ Memory storage functional"

                # Test retrieval
                results = system.retrieve_memories("health check", max_results=1)
                if results:
                    health_status["checks"]["retrieval"] = (
                        "✓ Memory retrieval functional"
                    )
                else:
                    health_status["checks"]["retrieval"] = (
                        "⚠ Memory retrieval returned no results"
                    )

                # Clean up test memory
                try:
                    system.delete_memory_by_id(test_memory_id)
                    logger.debug(
                        "Cleaned up health check test memory", memory_id=test_memory_id
                    )
                except Exception as cleanup_error:
                    logger.warning(
                        "Failed to cleanup health check memory",
                        error=str(cleanup_error),
                    )
            else:
                health_status["healthy"] = False
                health_status["checks"]["storage"] = "✗ Memory storage failed"
                health_status["errors"].append("Failed to store test memory")
        else:
            health_status["checks"]["storage"] = "⚠ Memory tests skipped (test mode)"
            health_status["checks"]["retrieval"] = "⚠ Memory tests skipped (test mode)"

    except Exception as e:
        health_status["healthy"] = False
        health_status["errors"].append(f"Health check failed: {e}")
        logger.error("System health check failed", error=str(e))

    logger.info("System health check completed", healthy=health_status["healthy"])

    return health_status
