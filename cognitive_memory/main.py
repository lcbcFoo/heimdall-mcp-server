"""
Main system initialization coordinator for the cognitive memory system.

This module provides the primary entry points for initializing the cognitive memory system
with different configuration profiles. It coordinates between configuration loading,
system factory creation, and health validation.
"""

import os
from typing import Any

from loguru import logger

from .core.cognitive_system import CognitiveMemorySystem
from .core.config import SystemConfig
from .factory import (
    InitializationError,
    create_default_system,
    create_system_from_config,
    validate_system_health,
)


def initialize_system(profile: str = "default") -> CognitiveMemorySystem:
    """
    Main system initialization entry point.

    Initializes the cognitive memory system using the specified profile.
    Profiles determine which configuration and implementation strategy to use.

    Args:
        profile: Initialization profile to use:
            - "default": Use default implementations with environment configuration
            - "development": Development-friendly settings (verbose logging, etc.)
            - "production": Production-optimized settings
            - "test": Lightweight test configuration

    Returns:
        CognitiveMemorySystem: Fully initialized and validated system

    Raises:
        InitializationError: If system initialization fails
    """
    logger.info("Initializing cognitive memory system", profile=profile)

    # Initialize shared data directories and environment variables
    try:
        from heimdall.cognitive_system.data_dirs import (
            ensure_models_available,
            initialize_shared_environment,
        )

        initialize_shared_environment()

        # Ensure models are available (download if necessary)
        ensure_models_available()
    except ImportError:
        # Graceful fallback if data_dirs module is not available
        logger.warning(
            "Shared data directories module not available, using legacy paths"
        )
    except Exception as e:
        logger.warning(f"Failed to ensure models are available: {e}")

    try:
        if profile == "default":
            system = create_default_system()

        elif profile == "development":
            # Development profile with enhanced logging
            config = SystemConfig.from_env()
            config.logging.level = "DEBUG"
            system = create_default_system(config)

        elif profile == "production":
            # Production profile with optimized settings
            config = SystemConfig.from_env()
            config.logging.level = "INFO"
            # Production might use different vector storage settings, etc.
            system = create_default_system(config)

        elif profile == "test":
            # Test profile with minimal resource usage
            config = SystemConfig.from_env()
            config.cognitive.max_activations = 10  # Reduce for faster tests
            config.logging.level = "WARNING"  # Reduce noise in tests
            system = create_default_system(config)

        else:
            raise InitializationError(f"Unknown initialization profile: {profile}")

        # Perform health check
        health_status = validate_system_health(system)
        if not health_status["healthy"]:
            error_summary = "; ".join(health_status["errors"])
            raise InitializationError(f"System health check failed: {error_summary}")

        logger.info(
            "Cognitive memory system initialized successfully",
            profile=profile,
            health_checks=len(health_status["checks"]),
        )

        return system

    except Exception as e:
        logger.error(
            "Failed to initialize cognitive memory system",
            profile=profile,
            error=str(e),
        )
        raise InitializationError(f"System initialization failed: {e}") from e


def initialize_with_config(config_path: str) -> CognitiveMemorySystem:
    """
    Initialize system with specific configuration file.

    Loads configuration from the specified file and creates a system
    with those settings. Supports .env files with plans for YAML/TOML.

    Args:
        config_path: Path to configuration file

    Returns:
        CognitiveMemorySystem: System initialized with file configuration

    Raises:
        InitializationError: If configuration loading or initialization fails
    """
    logger.info(
        "Initializing cognitive memory system with config file", config_path=config_path
    )

    if not os.path.exists(config_path):
        raise InitializationError(f"Configuration file not found: {config_path}")

    try:
        system = create_system_from_config(config_path)

        # Perform health check
        health_status = validate_system_health(system)
        if not health_status["healthy"]:
            error_summary = "; ".join(health_status["errors"])
            raise InitializationError(f"System health check failed: {error_summary}")

        logger.info(
            "Cognitive memory system initialized from config",
            config_path=config_path,
            health_checks=len(health_status["checks"]),
        )

        return system

    except Exception as e:
        logger.error(
            "Failed to initialize system with config",
            config_path=config_path,
            error=str(e),
        )
        raise InitializationError(f"Config-based initialization failed: {e}") from e


def get_system_info(system: CognitiveMemorySystem) -> dict[str, Any]:
    """
    Get detailed information about an initialized system.

    Args:
        system: Initialized cognitive memory system

    Returns:
        Dict containing system information and statistics
    """
    try:
        stats = system.get_memory_stats()

        info = {
            "system_type": type(system).__name__,
            "components": {
                "embedding_provider": type(system.embedding_provider).__name__,
                "vector_storage": type(system.vector_storage).__name__,
                "memory_storage": type(system.memory_storage).__name__,
                "connection_graph": type(system.connection_graph).__name__,
                "activation_engine": type(system.activation_engine).__name__,
                "bridge_discovery": type(system.bridge_discovery).__name__,
            },
            "configuration": stats.get("system_config", {}),
            "memory_counts": stats.get("memory_counts", {}),
            "storage_stats": stats.get("storage_stats", {}),
            "health_status": validate_system_health(system),
        }

        return info

    except Exception as e:
        logger.error("Failed to get system info", error=str(e))
        return {
            "error": str(e),
            "system_type": type(system).__name__ if system else "unknown",
        }


def graceful_shutdown(system: CognitiveMemorySystem) -> bool:
    """
    Perform graceful shutdown of the cognitive memory system.

    Ensures all components are properly closed and resources are cleaned up.

    Args:
        system: System to shut down

    Returns:
        bool: True if shutdown completed successfully
    """
    logger.info("Starting graceful system shutdown")

    try:
        shutdown_status = True

        # Close vector storage connections if applicable
        if hasattr(system.vector_storage, "close"):
            try:
                system.vector_storage.close()
                logger.debug("Vector storage closed successfully")
            except Exception as e:
                logger.warning("Failed to close vector storage", error=str(e))
                shutdown_status = False

        # Close database connections if applicable
        if hasattr(system.memory_storage, "close"):
            try:
                system.memory_storage.close()
                logger.debug("Memory storage closed successfully")
            except Exception as e:
                logger.warning("Failed to close memory storage", error=str(e))
                shutdown_status = False

        # Close connection graph if applicable
        if hasattr(system.connection_graph, "close"):
            try:
                system.connection_graph.close()
                logger.debug("Connection graph closed successfully")
            except Exception as e:
                logger.warning("Failed to close connection graph", error=str(e))
                shutdown_status = False

        if shutdown_status:
            logger.info("Graceful system shutdown completed successfully")
        else:
            logger.warning("System shutdown completed with warnings")

        return shutdown_status

    except Exception as e:
        logger.error("Failed to perform graceful shutdown", error=str(e))
        return False
