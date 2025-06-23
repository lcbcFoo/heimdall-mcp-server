"""
Configuration management for the cognitive memory system.

This module provides centralized configuration management using environment
variables and .env files as specified in the technical architecture.
"""

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import yaml
from dotenv import load_dotenv
from loguru import logger

if TYPE_CHECKING:
    from .memory import CognitiveMemory


def get_project_id(path: str | Path | None = None) -> str:
    """
    Generate project ID from directory path.

    Creates a deterministic project identifier in the format: {repo_name}_{hash8}
    where hash8 is the first 8 characters of the SHA256 hash of the absolute path.

    Args:
        path: Directory path to generate ID from. If None, uses current working directory.

    Returns:
        str: Project ID in format "repo_name_hash8"
    """
    if path is None:
        path = Path.cwd()
    else:
        path = Path(path)

    # Use absolute path for consistent hashing
    abs_path = path.resolve()

    # Generate hash from absolute path
    path_hash = hashlib.sha256(str(abs_path).encode()).hexdigest()[:8]

    # Extract repo name from directory
    repo_name = abs_path.name

    # Sanitize repo name for collection naming (replace non-alphanumeric with underscore)
    repo_name = re.sub(r"[^a-zA-Z0-9]", "_", repo_name)

    return f"{repo_name}_{path_hash}"


def detect_container_environment() -> bool:
    """
    Detect if running inside a container environment.

    Checks for common container indicators:
    - Docker environment file (/.dockerenv)
    - Docker cgroup indicators
    - Container environment variables

    Returns:
        bool: True if running in a container, False otherwise
    """
    container_indicators = [
        os.path.exists("/.dockerenv"),
        os.path.exists("/proc/1/cgroup") and "docker" in open("/proc/1/cgroup").read(),
        os.environ.get("CONTAINER") is not None,
        os.environ.get("PROJECT_ID") is not None,  # Our container sets this
    ]
    return any(container_indicators)


def detect_project_config() -> dict[str, str] | None:
    """
    Detect project-specific configuration from .heimdall/config.yaml or legacy Docker Compose.

    Looks for:
    1. .heimdall/config.yaml (new format)
    2. .heimdall-mcp/docker-compose.yml (legacy format)

    Returns:
        dict with project config overrides, or None if no project setup found
    """
    # Check for new .heimdall/config.yaml format first
    heimdall_config = Path(".heimdall/config.yaml")
    if heimdall_config.exists():
        try:
            config_data = yaml.safe_load(heimdall_config.read_text())
            if config_data and isinstance(config_data, dict):
                # Convert YAML config to environment variable format
                env_overrides = {}

                # Map qdrant_url to QDRANT_URL
                if "qdrant_url" in config_data:
                    env_overrides["QDRANT_URL"] = config_data["qdrant_url"]

                # Map monitoring settings
                if "monitoring" in config_data and isinstance(
                    config_data["monitoring"], dict
                ):
                    monitoring = config_data["monitoring"]
                    if "target_path" in monitoring:
                        env_overrides["MONITORING_TARGET_PATH"] = monitoring[
                            "target_path"
                        ]
                    if "interval_seconds" in monitoring:
                        env_overrides["MONITORING_INTERVAL_SECONDS"] = str(
                            monitoring["interval_seconds"]
                        )

                # Map database settings
                if "database" in config_data and isinstance(
                    config_data["database"], dict
                ):
                    database = config_data["database"]
                    if "path" in database:
                        env_overrides["SQLITE_PATH"] = database["path"]

                if env_overrides:
                    logger.debug(
                        f"Loaded project config from .heimdall/config.yaml: {list(env_overrides.keys())}"
                    )
                    return env_overrides

        except Exception as e:
            logger.warning(f"Failed to parse .heimdall/config.yaml: {e}")

    # Fall back to legacy Docker Compose detection
    compose_file = Path(".heimdall-mcp/docker-compose.yml")
    if not compose_file.exists():
        return None

    try:
        content = compose_file.read_text()

        # Extract port mapping: "6631:6333" -> external port 6631
        port_match = re.search(r'"(\d+):6333"', content)
        if port_match:
            external_port = port_match.group(1)
            project_config = {"QDRANT_URL": f"http://localhost:{external_port}"}
            logger.debug(
                f"Detected project-specific Qdrant port from docker-compose: {external_port}"
            )
            return project_config

    except Exception as e:
        logger.warning(f"Failed to parse project Docker Compose: {e}")

    return None


@dataclass
class QdrantConfig:
    """Configuration for Qdrant vector database."""

    url: str = "http://localhost:6333"
    api_key: str | None = None
    timeout: int = 30
    prefer_grpc: bool = False

    def get_port(self) -> int:
        """Extract port number from URL."""
        from urllib.parse import urlparse

        parsed = urlparse(self.url)
        return parsed.port or 6333

    def get_host(self) -> str:
        """Extract host from URL."""
        from urllib.parse import urlparse

        parsed = urlparse(self.url)
        return parsed.hostname or "localhost"

    @classmethod
    def from_env(cls) -> "QdrantConfig":
        """Create configuration from environment variables."""
        return cls(
            url=os.getenv("QDRANT_URL", cls.url),
            api_key=os.getenv("QDRANT_API_KEY"),
            timeout=int(os.getenv("QDRANT_TIMEOUT", str(cls.timeout))),
            prefer_grpc=os.getenv("QDRANT_PREFER_GRPC", "false").lower() == "true",
        )


@dataclass
class DatabaseConfig:
    """Configuration for SQLite database."""

    path: str = "./data/cognitive_memory.db"
    backup_interval_hours: int = 24
    enable_wal_mode: bool = True

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create configuration from environment variables."""
        return cls(
            path=os.getenv("SQLITE_PATH", cls.path),
            backup_interval_hours=int(
                os.getenv("DB_BACKUP_INTERVAL", str(cls.backup_interval_hours))
            ),
            enable_wal_mode=os.getenv("DB_ENABLE_WAL", "true").lower() == "true",
        )


@dataclass
class EmbeddingConfig:
    """Configuration for embedding models."""

    model_name: str = "all-MiniLM-L6-v2"
    model_cache_dir: str = "./data/models"
    embedding_dimension: int = 384  # Sentence-BERT semantic embedding dimension
    batch_size: int = 32
    device: str = "auto"  # auto, cpu, cuda

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        """Create configuration from environment variables."""
        return cls(
            model_name=os.getenv("SENTENCE_BERT_MODEL", cls.model_name),
            model_cache_dir=os.getenv("MODEL_CACHE_DIR", cls.model_cache_dir),
            embedding_dimension=int(
                os.getenv("EMBEDDING_DIMENSION", str(cls.embedding_dimension))
            ),
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", str(cls.batch_size))),
            device=os.getenv("EMBEDDING_DEVICE", cls.device),
        )


@dataclass
class CognitiveConfig:
    """Configuration for cognitive processing parameters."""

    # Activation and retrieval parameters
    activation_threshold: float = 0.7
    bridge_discovery_k: int = 5
    max_activations: int = 50
    consolidation_threshold: int = 100

    # Activity tracking parameters for context-aware decay
    activity_window_days: int = 30
    max_commits_per_day: int = 3
    max_accesses_per_day: int = 100
    activity_commit_weight: float = 0.6
    activity_access_weight: float = 0.4
    high_activity_threshold: float = 0.7
    low_activity_threshold: float = 0.2
    high_activity_multiplier: float = 2.0
    normal_activity_multiplier: float = 1.0
    low_activity_multiplier: float = 0.1

    # Content-type decay profiles (multipliers applied to base decay rate)
    # Based on DETERMINISTIC source_type detection from memory metadata
    decay_profiles: dict[str, float] = field(
        default_factory=lambda: {
            # Source-based content types (deterministic)
            "git_commit": 1.2,  # Moderate-fast decay (code becomes outdated)
            "session_lesson": 0.2,  # Very slow decay (insights persist)
            "store_memory": 1.0,  # Normal decay (general experiences)
            "documentation": 0.2,  # Slow decay (docs stay relevant)
            "manual_entry": 1.0,  # Normal decay (default)
            # Hierarchy level fallbacks (when source_type missing)
            "L0_concept": 0.3,  # Concepts decay very slowly
            "L1_context": 0.8,  # Context moderately
            "L2_episode": 1.0,  # Episodes at base rate
        }
    )

    # File monitoring parameters
    monitoring_enabled: bool = True
    monitoring_interval_seconds: float = 5.0
    monitoring_batch_size: int = 10
    monitoring_ignore_patterns: set[str] = field(
        default_factory=lambda: {".git", "node_modules", "__pycache__", ".pytest_cache"}
    )

    # File synchronization parameters
    sync_enabled: bool = True
    sync_atomic_operations: bool = True
    sync_continue_on_error: bool = True
    sync_max_retry_attempts: int = 3
    sync_retry_delay_seconds: float = 1.0

    # Date-based ranking parameters
    similarity_closeness_threshold: float = 0.05
    modification_date_weight: float = 0.3
    modification_recency_decay_days: float = 30.0

    # Dimension weights for fusion
    emotional_weight: float = 0.2
    temporal_weight: float = 0.15
    contextual_weight: float = 0.25
    social_weight: float = 0.1

    # Cognitive dimension sizes - ONLY place magic numbers should be defined
    emotional_dimensions: int = 4
    temporal_dimensions: int = 3
    contextual_dimensions: int = 6
    social_dimensions: int = 3

    # Memory loading parameters
    max_tokens_per_chunk: int = 1000
    code_block_lines: int = 8
    strength_floor: float = 0.3
    min_memory_tokens: int = 100
    min_meaningful_words: int = 20
    max_merge_children: int = 5
    max_hierarchical_depth: int = 4
    max_connections_per_memory: int = 10

    # Base connection weights
    hierarchical_weight: float = 0.80
    sequential_weight: float = 0.70
    associative_weight: float = 0.35

    # Relevance scoring weights (must sum to 1.0)
    semantic_alpha: float = 0.45
    lexical_beta: float = 0.25
    structural_gamma: float = 0.15
    explicit_delta: float = 0.15

    @classmethod
    def from_env(cls) -> "CognitiveConfig":
        """Create configuration from environment variables."""
        config = cls(
            activation_threshold=float(
                os.getenv("ACTIVATION_THRESHOLD", str(cls.activation_threshold))
            ),
            bridge_discovery_k=int(
                os.getenv("BRIDGE_DISCOVERY_K", str(cls.bridge_discovery_k))
            ),
            max_activations=int(os.getenv("MAX_ACTIVATIONS", str(cls.max_activations))),
            consolidation_threshold=int(
                os.getenv("CONSOLIDATION_THRESHOLD", str(cls.consolidation_threshold))
            ),
            similarity_closeness_threshold=float(
                os.getenv(
                    "SIMILARITY_CLOSENESS_THRESHOLD",
                    str(cls.similarity_closeness_threshold),
                )
            ),
            modification_date_weight=float(
                os.getenv("MODIFICATION_DATE_WEIGHT", str(cls.modification_date_weight))
            ),
            modification_recency_decay_days=float(
                os.getenv(
                    "MODIFICATION_RECENCY_DECAY_DAYS",
                    str(cls.modification_recency_decay_days),
                )
            ),
            emotional_weight=float(
                os.getenv("EMOTIONAL_WEIGHT", str(cls.emotional_weight))
            ),
            temporal_weight=float(
                os.getenv("TEMPORAL_WEIGHT", str(cls.temporal_weight))
            ),
            contextual_weight=float(
                os.getenv("CONTEXTUAL_WEIGHT", str(cls.contextual_weight))
            ),
            social_weight=float(os.getenv("SOCIAL_WEIGHT", str(cls.social_weight))),
            emotional_dimensions=int(
                os.getenv("EMOTIONAL_DIMENSIONS", str(cls.emotional_dimensions))
            ),
            temporal_dimensions=int(
                os.getenv("TEMPORAL_DIMENSIONS", str(cls.temporal_dimensions))
            ),
            contextual_dimensions=int(
                os.getenv("CONTEXTUAL_DIMENSIONS", str(cls.contextual_dimensions))
            ),
            social_dimensions=int(
                os.getenv("SOCIAL_DIMENSIONS", str(cls.social_dimensions))
            ),
            max_tokens_per_chunk=int(
                os.getenv("MAX_TOKENS_PER_CHUNK", str(cls.max_tokens_per_chunk))
            ),
            code_block_lines=int(
                os.getenv("CODE_BLOCK_LINES", str(cls.code_block_lines))
            ),
            strength_floor=float(os.getenv("STRENGTH_FLOOR", str(cls.strength_floor))),
            hierarchical_weight=float(
                os.getenv("HIERARCHICAL_WEIGHT", str(cls.hierarchical_weight))
            ),
            sequential_weight=float(
                os.getenv("SEQUENTIAL_WEIGHT", str(cls.sequential_weight))
            ),
            associative_weight=float(
                os.getenv("ASSOCIATIVE_WEIGHT", str(cls.associative_weight))
            ),
            semantic_alpha=float(os.getenv("SEMANTIC_ALPHA", str(cls.semantic_alpha))),
            lexical_beta=float(os.getenv("LEXICAL_BETA", str(cls.lexical_beta))),
            structural_gamma=float(
                os.getenv("STRUCTURAL_GAMMA", str(cls.structural_gamma))
            ),
            explicit_delta=float(os.getenv("EXPLICIT_DELTA", str(cls.explicit_delta))),
            activity_window_days=int(
                os.getenv("ACTIVITY_WINDOW_DAYS", str(cls.activity_window_days))
            ),
            max_commits_per_day=int(
                os.getenv("MAX_COMMITS_PER_DAY", str(cls.max_commits_per_day))
            ),
            max_accesses_per_day=int(
                os.getenv("MAX_ACCESSES_PER_DAY", str(cls.max_accesses_per_day))
            ),
            activity_commit_weight=float(
                os.getenv("ACTIVITY_COMMIT_WEIGHT", str(cls.activity_commit_weight))
            ),
            activity_access_weight=float(
                os.getenv("ACTIVITY_ACCESS_WEIGHT", str(cls.activity_access_weight))
            ),
            high_activity_threshold=float(
                os.getenv("HIGH_ACTIVITY_THRESHOLD", str(cls.high_activity_threshold))
            ),
            low_activity_threshold=float(
                os.getenv("LOW_ACTIVITY_THRESHOLD", str(cls.low_activity_threshold))
            ),
            high_activity_multiplier=float(
                os.getenv("HIGH_ACTIVITY_MULTIPLIER", str(cls.high_activity_multiplier))
            ),
            normal_activity_multiplier=float(
                os.getenv(
                    "NORMAL_ACTIVITY_MULTIPLIER", str(cls.normal_activity_multiplier)
                )
            ),
            low_activity_multiplier=float(
                os.getenv("LOW_ACTIVITY_MULTIPLIER", str(cls.low_activity_multiplier))
            ),
            monitoring_enabled=os.getenv("MONITORING_ENABLED", "true").lower()
            == "true",
            monitoring_interval_seconds=float(
                os.getenv(
                    "MONITORING_INTERVAL_SECONDS", str(cls.monitoring_interval_seconds)
                )
            ),
            monitoring_batch_size=int(
                os.getenv("MONITORING_BATCH_SIZE", str(cls.monitoring_batch_size))
            ),
            sync_enabled=os.getenv("SYNC_ENABLED", "true").lower() == "true",
            sync_atomic_operations=os.getenv("SYNC_ATOMIC_OPERATIONS", "true").lower()
            == "true",
            sync_continue_on_error=os.getenv("SYNC_CONTINUE_ON_ERROR", "true").lower()
            == "true",
            sync_max_retry_attempts=int(
                os.getenv("SYNC_MAX_RETRY_ATTEMPTS", str(cls.sync_max_retry_attempts))
            ),
            sync_retry_delay_seconds=float(
                os.getenv("SYNC_RETRY_DELAY_SECONDS", str(cls.sync_retry_delay_seconds))
            ),
        )

        # Update decay profiles with environment variable overrides
        config.decay_profiles = config._parse_decay_profiles()

        # Parse monitoring ignore patterns from environment
        ignore_patterns_env = os.getenv("MONITORING_IGNORE_PATTERNS")
        if ignore_patterns_env:
            config.monitoring_ignore_patterns = {
                pattern.strip() for pattern in ignore_patterns_env.split(",")
            }

        return config

    def _parse_decay_profiles(self) -> dict[str, float]:
        """Parse decay profiles from environment variables."""
        # Start with defaults
        profiles = {
            "git_commit": 1.2,
            "session_lesson": 0.2,
            "store_memory": 1.0,
            "documentation": 0.2,
            "manual_entry": 1.0,
            "L0_concept": 0.3,
            "L1_context": 0.8,
            "L2_episode": 1.0,
        }

        # Override with environment variables if set
        env_mapping = {
            "DECAY_PROFILE_GIT_COMMIT": "git_commit",
            "DECAY_PROFILE_SESSION_LESSON": "session_lesson",
            "DECAY_PROFILE_STORE_MEMORY": "store_memory",
            "DECAY_PROFILE_DOCUMENTATION": "documentation",
            "DECAY_PROFILE_MANUAL_ENTRY": "manual_entry",
            "DECAY_PROFILE_L0_CONCEPT": "L0_concept",
            "DECAY_PROFILE_L1_CONTEXT": "L1_context",
            "DECAY_PROFILE_L2_EPISODE": "L2_episode",
        }

        for env_var, profile_key in env_mapping.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                try:
                    profiles[profile_key] = float(env_value)
                except ValueError:
                    logger.warning(
                        f"Invalid decay profile value for {env_var}: {env_value}"
                    )

        return profiles

    def detect_content_type(self, memory: "CognitiveMemory") -> str:
        """
        Deterministic content-type detection based on memory creation source.
        NO pattern matching - relies on explicit source_type set by creators.

        Args:
            memory: CognitiveMemory object with metadata

        Returns:
            str: Content type key for decay profile lookup
        """
        # Primary: Use explicit source_type from metadata
        if hasattr(memory, "metadata") and memory.metadata:
            source_type = memory.metadata.get("source_type")
            if (
                source_type
                and isinstance(source_type, str)
                and source_type in self.decay_profiles
            ):
                return cast(str, source_type)

        # Fallback: Use hierarchy level if source_type missing
        if hasattr(memory, "hierarchy_level"):
            hierarchy_level = memory.hierarchy_level
            # Only use valid hierarchy levels (0, 1, 2)
            if 0 <= hierarchy_level <= 2:
                level_key = f"L{hierarchy_level}_{['concept', 'context', 'episode'][hierarchy_level]}"
                return level_key if level_key in self.decay_profiles else "manual_entry"

        # Final fallback
        return "manual_entry"

    def get_total_cognitive_dimensions(self) -> int:
        """Get total number of cognitive dimensions."""
        return (
            self.emotional_dimensions
            + self.temporal_dimensions
            + self.contextual_dimensions
            + self.social_dimensions
        )


@dataclass
class LoggingConfig:
    """Configuration for logging system."""

    level: str = "INFO"
    format: str = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    log_file: str | None = None
    rotate_size: str = "10 MB"
    retention: str = "7 days"

    @classmethod
    def from_env(cls) -> "LoggingConfig":
        """Create configuration from environment variables."""
        return cls(
            level=os.getenv("LOG_LEVEL", cls.level),
            format=os.getenv("LOG_FORMAT", cls.format),
            log_file=os.getenv("LOG_FILE"),
            rotate_size=os.getenv("LOG_ROTATE_SIZE", cls.rotate_size),
            retention=os.getenv("LOG_RETENTION", cls.retention),
        )


@dataclass
class SystemConfig:
    """Master configuration for the cognitive memory system."""

    qdrant: QdrantConfig
    database: DatabaseConfig
    embedding: EmbeddingConfig
    cognitive: CognitiveConfig
    logging: LoggingConfig

    # System-wide settings
    debug: bool = False
    max_memory_usage_mb: int = 1024
    cleanup_interval_hours: int = 24

    # Project identification
    project_id: str = ""

    @classmethod
    def from_env(cls, env_file: str | None = None) -> "SystemConfig":
        """Create complete system configuration from environment."""
        # Load .env file if specified or if default exists
        if env_file:
            load_dotenv(env_file)
        else:
            default_env = Path(".env")
            if default_env.exists():
                load_dotenv(default_env)

        # Detect project-specific configuration
        project_config = detect_project_config()
        if project_config:
            # Temporarily set project config in environment (lower precedence than existing env vars)
            for key, value in project_config.items():
                if key not in os.environ:  # Only set if not already defined
                    os.environ[key] = value
                    logger.debug(f"Using project-specific config: {key}={value}")

        # Generate project ID for this configuration
        project_id = get_project_id()

        return cls(
            qdrant=QdrantConfig.from_env(),
            database=DatabaseConfig.from_env(),
            embedding=EmbeddingConfig.from_env(),
            cognitive=CognitiveConfig.from_env(),
            logging=LoggingConfig.from_env(),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            max_memory_usage_mb=int(os.getenv("MAX_MEMORY_USAGE_MB", "1024")),
            cleanup_interval_hours=int(os.getenv("CLEANUP_INTERVAL_HOURS", "24")),
            project_id=project_id,
        )

    def validate(self) -> bool:
        """Validate configuration and check for required resources."""
        errors = []

        # Check database directory
        db_dir = Path(self.database.path).parent
        if not db_dir.exists():
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")
            except Exception as e:
                errors.append(f"Cannot create database directory {db_dir}: {e}")

        # Check model cache directory
        model_dir = Path(self.embedding.model_cache_dir)
        if not model_dir.exists():
            try:
                model_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created model cache directory: {model_dir}")
            except Exception as e:
                errors.append(f"Cannot create model cache directory {model_dir}: {e}")

        # Validate cognitive parameters
        if not 0.0 <= self.cognitive.activation_threshold <= 1.0:
            errors.append("Activation threshold must be between 0.0 and 1.0")

        if self.cognitive.bridge_discovery_k <= 0:
            errors.append("Bridge discovery K must be positive")

        if self.cognitive.max_activations <= 0:
            errors.append("Max activations must be positive")

        # Check dimension weights sum to reasonable range
        total_weight = (
            self.cognitive.emotional_weight
            + self.cognitive.temporal_weight
            + self.cognitive.contextual_weight
            + self.cognitive.social_weight
        )
        if total_weight > 1.0:
            logger.warning(
                f"Dimension weights sum to {total_weight:.2f}, consider normalizing"
            )

        # Validate memory loading parameters
        if self.cognitive.max_tokens_per_chunk <= 0:
            errors.append("Max tokens per chunk must be positive")

        if self.cognitive.code_block_lines <= 0:
            errors.append("Code block lines must be positive")

        if not 0.0 <= self.cognitive.strength_floor <= 1.0:
            errors.append("Strength floor must be between 0.0 and 1.0")

        # Validate connection weights
        if not 0.0 <= self.cognitive.hierarchical_weight <= 1.0:
            errors.append("Hierarchical weight must be between 0.0 and 1.0")
        if not 0.0 <= self.cognitive.sequential_weight <= 1.0:
            errors.append("Sequential weight must be between 0.0 and 1.0")
        if not 0.0 <= self.cognitive.associative_weight <= 1.0:
            errors.append("Associative weight must be between 0.0 and 1.0")

        # Validate relevance scoring weights sum to 1.0
        relevance_sum = (
            self.cognitive.semantic_alpha
            + self.cognitive.lexical_beta
            + self.cognitive.structural_gamma
            + self.cognitive.explicit_delta
        )
        if abs(relevance_sum - 1.0) > 0.01:
            errors.append(f"Relevance weights must sum to 1.0, got {relevance_sum:.3f}")

        # Validate activity tracking parameters
        if self.cognitive.activity_window_days <= 0:
            errors.append("Activity window days must be positive")

        if self.cognitive.max_commits_per_day <= 0:
            errors.append("Max commits per day must be positive")

        if self.cognitive.max_accesses_per_day <= 0:
            errors.append("Max accesses per day must be positive")

        # Validate activity weights sum to 1.0
        activity_weights_sum = (
            self.cognitive.activity_commit_weight
            + self.cognitive.activity_access_weight
        )
        if abs(activity_weights_sum - 1.0) > 0.01:
            errors.append(
                f"Activity weights must sum to 1.0, got {activity_weights_sum:.3f}"
            )

        # Validate activity thresholds
        if not 0.0 <= self.cognitive.low_activity_threshold <= 1.0:
            errors.append("Low activity threshold must be between 0.0 and 1.0")

        if not 0.0 <= self.cognitive.high_activity_threshold <= 1.0:
            errors.append("High activity threshold must be between 0.0 and 1.0")

        if (
            self.cognitive.low_activity_threshold
            >= self.cognitive.high_activity_threshold
        ):
            errors.append(
                "Low activity threshold must be less than high activity threshold"
            )

        # Validate activity multipliers
        if self.cognitive.high_activity_multiplier <= 0:
            errors.append("High activity multiplier must be positive")

        if self.cognitive.normal_activity_multiplier <= 0:
            errors.append("Normal activity multiplier must be positive")

        if self.cognitive.low_activity_multiplier <= 0:
            errors.append("Low activity multiplier must be positive")

        # Validate monitoring parameters
        if self.cognitive.monitoring_interval_seconds <= 0:
            errors.append("Monitoring interval must be positive")

        if self.cognitive.monitoring_batch_size <= 0:
            errors.append("Monitoring batch size must be positive")

        if errors:
            for error in errors:
                logger.error(f"Configuration error: {error}")
            return False

        logger.info("Configuration validation passed")
        return True

    def get_final_embedding_dimension(self) -> int:
        """Get final embedding dimension (semantic + cognitive)."""
        return (
            self.embedding.embedding_dimension
            + self.cognitive.get_total_cognitive_dimensions()
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary for logging/debugging."""
        return {
            "qdrant": {
                "url": self.qdrant.url,
                "timeout": self.qdrant.timeout,
                "prefer_grpc": self.qdrant.prefer_grpc,
                "api_key_set": self.qdrant.api_key is not None,
            },
            "database": {
                "path": self.database.path,
                "backup_interval_hours": self.database.backup_interval_hours,
                "enable_wal_mode": self.database.enable_wal_mode,
            },
            "embedding": {
                "model_name": self.embedding.model_name,
                "model_cache_dir": self.embedding.model_cache_dir,
                "embedding_dimension": self.embedding.embedding_dimension,
                "batch_size": self.embedding.batch_size,
                "device": self.embedding.device,
            },
            "cognitive": {
                "activation_threshold": self.cognitive.activation_threshold,
                "bridge_discovery_k": self.cognitive.bridge_discovery_k,
                "max_activations": self.cognitive.max_activations,
                "consolidation_threshold": self.cognitive.consolidation_threshold,
                "dimension_weights": {
                    "emotional": self.cognitive.emotional_weight,
                    "temporal": self.cognitive.temporal_weight,
                    "contextual": self.cognitive.contextual_weight,
                    "social": self.cognitive.social_weight,
                },
            },
            "logging": {
                "level": self.logging.level,
                "log_file": self.logging.log_file,
                "rotate_size": self.logging.rotate_size,
                "retention": self.logging.retention,
            },
            "system": {
                "debug": self.debug,
                "max_memory_usage_mb": self.max_memory_usage_mb,
                "cleanup_interval_hours": self.cleanup_interval_hours,
                "project_id": self.project_id,
            },
        }


def get_config(env_file: str | None = None) -> SystemConfig:
    """
    Get system configuration, loading from environment variables and .env file.

    Args:
        env_file: Optional path to .env file. If None, looks for .env in current directory.

    Returns:
        SystemConfig: Complete system configuration

    Raises:
        ValueError: If configuration validation fails
    """
    config = SystemConfig.from_env(env_file)

    if not config.validate():
        raise ValueError("Configuration validation failed. Check logs for details.")

    return config
