"""
Git repository memory loader for the cognitive memory system.

This module implements a MemoryLoader for git repositories, storing individual
commits as memories with metadata for retrieval and connection analysis.
Each commit becomes a cognitive memory with full context and file changes.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from ..core.config import CognitiveConfig
from ..core.interfaces import MemoryLoader
from ..core.memory import CognitiveMemory
from ..git_analysis.commit_loader import CommitLoader


class GitHistoryLoader(MemoryLoader):
    """
    Memory loader for git repositories.

    Stores individual git commits as cognitive memories with metadata for
    retrieval and connection analysis. Each commit becomes a memory with
    full context including file changes and author information.
    """

    def __init__(self, config: CognitiveConfig, cognitive_system: Any = None):
        """
        Initialize the git history loader.

        Args:
            config: Cognitive configuration parameters
            cognitive_system: Optional CognitiveSystem instance for operations
        """
        self.config = config
        self.cognitive_system = cognitive_system

        # Initialize commit loader
        self.commit_loader = CommitLoader(config, cognitive_system)

        logger.info("GitHistoryLoader initialized for git commit storage")

    def load_from_source(
        self, source_path: str, **kwargs: Any
    ) -> list[CognitiveMemory]:
        """
        Load cognitive memories from git commits with automatic incremental behavior.

        Always checks for existing processed commits and loads only new commits
        when possible. Falls back to full history for fresh repositories.

        Args:
            source_path: Path to the git repository
            **kwargs: Additional parameters (max_commits, since_date, etc.)
                     Note: since_commit parameter will be automatically set for incremental loading

        Returns:
            List of CognitiveMemory objects created from git commits
        """
        # Always check for existing state first (unless explicitly disabled)
        force_full_load = kwargs.get("force_full_load", False)

        if not force_full_load:
            try:
                last_processed = self.get_latest_processed_commit(source_path)

                if last_processed:
                    commit_hash, last_timestamp = last_processed
                    logger.info(
                        f"Found existing git state, loading incrementally since commit {commit_hash[:8]}",
                        repo_path=source_path,
                        last_commit=commit_hash,
                        last_timestamp=last_timestamp,
                    )

                    # Set since_commit for incremental loading
                    kwargs["since_commit"] = commit_hash
                else:
                    logger.info(
                        "No existing git state found, performing full history load",
                        repo_path=source_path,
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to check existing git state, falling back to full load: {e}",
                    repo_path=source_path,
                )
        else:
            logger.info(
                "Force full load requested, skipping incremental check",
                repo_path=source_path,
            )

        return self.commit_loader.load_from_source(source_path, **kwargs)

    def extract_connections(
        self, memories: list[CognitiveMemory]
    ) -> list[tuple[str, str, float, str]]:
        """
        Extract connections between git commit memories.

        Identifies relationships between commits based on shared files,
        authors, and temporal proximity.

        Args:
            memories: List of commit memories to analyze for connections

        Returns:
            List of tuples: (source_id, target_id, strength, connection_type)
        """
        return self.commit_loader.extract_connections(memories)

    def validate_source(self, source_path: str) -> bool:
        """
        Validate that the source is a readable git repository.

        Args:
            source_path: Path to validate

        Returns:
            True if source is valid for this loader
        """
        return self.commit_loader.validate_source(source_path)

    def get_supported_extensions(self) -> list[str]:
        """
        Get list of file extensions supported by this loader.

        Returns:
            Empty list since git repositories are identified by .git directory
        """
        return self.commit_loader.get_supported_extensions()

    def get_latest_processed_commit(
        self, repo_path: str
    ) -> tuple[str, datetime] | None:
        """
        Query SQLite to find most recent git commit memory for this repository.

        This method enables incremental git loading by tracking what commits
        have already been processed and stored as memories.

        Args:
            repo_path: Path to the git repository

        Returns:
            Tuple of (commit_hash, timestamp) for the latest processed commit,
            or None if no git commits have been processed yet
        """
        if not self.cognitive_system:
            logger.warning("No cognitive system available for state tracking")
            return None

        # Validate repository path for state isolation
        try:
            repo_path_abs = str(Path(repo_path).resolve())
            if not self.validate_source(repo_path_abs):
                logger.error(f"Invalid git repository for state tracking: {repo_path}")
                return None
        except Exception as e:
            logger.error(f"Failed to validate repository path: {e}")
            return None

        try:
            # Access the SQLite storage through the cognitive system
            if not hasattr(self.cognitive_system, "memory_storage"):
                logger.warning("No memory_storage available in cognitive system")
                return None

            storage = self.cognitive_system.memory_storage
            if not storage:
                logger.warning("memory_storage is None in cognitive system")
                return None

            # Query for git commit memories - use the database manager directly
            if not hasattr(storage, "db_manager"):
                logger.warning("No database manager available in storage")
                return None

            db_manager = storage.db_manager
            if not db_manager:
                logger.warning("database manager is None in storage")
                return None

            with db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Query for the most recent git commit memory
                cursor.execute("""
                    SELECT id, created_at, timestamp
                    FROM memories
                    WHERE id LIKE 'git::commit::%'
                    ORDER BY created_at DESC
                    LIMIT 1
                """)

                row = cursor.fetchone()
                if not row:
                    logger.debug("No existing git commit memories found")
                    return None

                # Extract commit hash from memory ID format: git::commit::<hash>
                memory_id = row["id"]
                commit_hash = self._extract_commit_hash_from_memory_id(memory_id)

                if not commit_hash:
                    logger.warning(
                        f"Failed to extract commit hash from memory ID: {memory_id}"
                    )
                    return None

                # Use the memory's original timestamp, fallback to created_at
                timestamp_val = (
                    row["timestamp"] if row["timestamp"] else row["created_at"]
                )

                # Convert timestamp to datetime
                if isinstance(timestamp_val, int | float):
                    memory_timestamp = datetime.fromtimestamp(timestamp_val)
                else:
                    # Assume it's already a datetime or Julian day
                    memory_timestamp = datetime.now()  # Fallback

                logger.debug(
                    f"Found latest processed commit: {commit_hash} at {memory_timestamp}",
                    repo_path=repo_path_abs,
                )

                return (commit_hash, memory_timestamp)

        except Exception as e:
            logger.error(f"Failed to query latest processed commit: {e}")
            return None

    def _extract_commit_hash_from_memory_id(self, memory_id: str) -> str | None:
        """
        Extract commit hash from deterministic memory ID format.

        Args:
            memory_id: Memory ID in format 'git::commit::<hash>'

        Returns:
            Commit hash string or None if extraction fails
        """
        try:
            # Expected format: git::commit::<hash>
            if not memory_id.startswith("git::commit::"):
                return None

            commit_hash = memory_id[len("git::commit::") :]

            # Basic validation: git commit hashes are typically 40 characters (SHA-1)
            # or 64 characters (SHA-256), hexadecimal
            if len(commit_hash) not in [40, 64]:
                logger.warning(f"Unexpected commit hash length: {len(commit_hash)}")
                return None

            # Validate hexadecimal characters
            try:
                int(commit_hash, 16)
            except ValueError:
                logger.warning(f"Invalid hexadecimal commit hash: {commit_hash}")
                return None

            return commit_hash

        except Exception as e:
            logger.error(f"Failed to extract commit hash from memory ID: {e}")
            return None
