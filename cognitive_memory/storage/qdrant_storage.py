"""
Qdrant vector storage implementation for cognitive memory system.

This module implements hierarchical memory storage using Qdrant vector database
with 3-tier collections: L0 (concepts), L1 (contexts), L2 (episodes).
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from ..core.config import QdrantConfig
from ..core.interfaces import VectorStorage
from ..core.memory import CognitiveMemory, SearchResult


@dataclass
class CollectionConfig:
    """Configuration for a Qdrant collection."""

    name: str
    vector_size: int
    distance: Distance
    on_disk_payload: bool = True
    replication_factor: int = 1
    write_consistency_factor: int = 1
    optimizers_indexing_threshold: int = 20000
    segments_number: int = 2


class QdrantCollectionManager:
    """Manages Qdrant collections for hierarchical memory storage."""

    def __init__(self, client: QdrantClient, vector_size: int, project_id: str):
        """Initialize collection manager with project-scoped collections."""
        self.client = client
        self.vector_size = vector_size
        self.project_id = project_id
        self.collections = {
            0: CollectionConfig(
                name=f"{project_id}_concepts",
                vector_size=vector_size,
                distance=Distance.COSINE,
            ),
            1: CollectionConfig(
                name=f"{project_id}_contexts",
                vector_size=vector_size,
                distance=Distance.COSINE,
            ),
            2: CollectionConfig(
                name=f"{project_id}_episodes",
                vector_size=vector_size,
                distance=Distance.COSINE,
            ),
        }

    def initialize_collections(self) -> bool:
        """Initialize all hierarchical collections."""
        try:
            for level, config in self.collections.items():
                if not self._collection_exists(config.name):
                    self._create_collection(config)
                    logger.info(
                        f"Created collection for level {level}", collection=config.name
                    )
                else:
                    logger.debug(
                        f"Collection already exists for level {level}",
                        collection=config.name,
                    )
            return True
        except Exception as e:
            logger.error("Failed to initialize collections", error=str(e))
            return False

    def _collection_exists(self, collection_name: str) -> bool:
        """Check if collection exists."""
        try:
            collections = self.client.get_collections().collections
            return any(c.name == collection_name for c in collections)
        except Exception:
            return False

    def _create_collection(self, config: CollectionConfig) -> None:
        """Create a single collection with optimization settings."""
        self.client.create_collection(
            collection_name=config.name,
            vectors_config=VectorParams(
                size=config.vector_size,
                distance=config.distance,
                on_disk=config.on_disk_payload,
            ),
            replication_factor=config.replication_factor,
            write_consistency_factor=config.write_consistency_factor,
            optimizers_config=models.OptimizersConfigDiff(
                indexing_threshold=config.optimizers_indexing_threshold,
                memmap_threshold=config.optimizers_indexing_threshold,
            ),
            shard_number=config.segments_number,
        )

    def get_collection_name(self, level: int) -> str:
        """Get collection name for memory level."""
        if level not in self.collections:
            raise ValueError(f"Invalid memory level: {level}")
        return self.collections[level].name

    def delete_all_collections(self) -> bool:
        """Delete all collections for this project (used for cleanup)."""
        try:
            for config in self.collections.values():
                if self._collection_exists(config.name):
                    self.client.delete_collection(config.name)
                    logger.info("Deleted collection", collection=config.name)
            return True
        except Exception as e:
            logger.error("Failed to delete collections", error=str(e))
            return False

    def list_project_collections(self) -> list[str]:
        """List all collections for this project."""
        try:
            all_collections = self.client.get_collections().collections
            project_collections = [
                c.name
                for c in all_collections
                if c.name.startswith(f"{self.project_id}_")
            ]
            return project_collections
        except Exception as e:
            logger.error("Failed to list project collections", error=str(e))
            return []

    def get_all_projects(self) -> set[str]:
        """Discover all project IDs from existing collections."""
        try:
            all_collections = self.client.get_collections().collections
            projects = set()
            for collection in all_collections:
                project_id = self._extract_project_id_from_collection(collection.name)
                if project_id:
                    projects.add(project_id)
            return projects
        except Exception as e:
            logger.error("Failed to discover projects", error=str(e))
            return set()

    def _extract_project_id_from_collection(self, collection_name: str) -> str | None:
        """
        Extract and validate project ID from collection name.

        Expected format: {project_id}_{memory_level}
        where project_id must end with an 8-character hexadecimal hash.

        Args:
            collection_name: Collection name to parse

        Returns:
            Valid project ID if found, None otherwise
        """
        if not collection_name or "_" not in collection_name:
            return None

        parts = collection_name.split("_")

        # Must have at least 2 parts and last part must be valid memory level
        if len(parts) < 2 or parts[-1] not in ["concepts", "contexts", "episodes"]:
            return None

        # Rejoin all parts except the last one to get potential project_id
        potential_project_id = "_".join(parts[:-1])

        # Validate project ID format: must end with 8-character hex hash
        if self._validate_project_id_format(potential_project_id):
            return potential_project_id

        return None

    def _validate_project_id_format(self, project_id: str) -> bool:
        """
        Validate project ID format for security and consistency.

        Expected format: {repo_name}_{hash8}
        where hash8 is exactly 8 hexadecimal characters.

        Args:
            project_id: Project ID to validate

        Returns:
            True if project ID matches expected format
        """
        if not project_id or "_" not in project_id:
            return False

        # Split into parts and check last part is 8-char hex hash
        parts = project_id.split("_")
        if len(parts) < 2:
            return False

        # Last part must be exactly 8-character hexadecimal hash
        hash_part = parts[-1]
        if len(hash_part) != 8:
            return False

        # Validate hexadecimal format
        try:
            int(hash_part, 16)
        except ValueError:
            return False

        # Validate repo_name part (everything except hash)
        repo_name = "_".join(parts[:-1])
        if not repo_name or len(repo_name) == 0:
            return False

        # Repo name should only contain alphanumeric and underscores (per config.py sanitization)
        import re

        if not re.match(r"^[a-zA-Z0-9_]+$", repo_name):
            return False

        return True

    @classmethod
    def delete_project_collections(cls, client: QdrantClient, project_id: str) -> bool:
        """Delete all collections for a specific project."""
        try:
            all_collections = client.get_collections().collections
            deleted_count = 0
            for collection in all_collections:
                if collection.name.startswith(f"{project_id}_"):
                    client.delete_collection(collection.name)
                    logger.info(
                        "Deleted project collection",
                        project_id=project_id,
                        collection=collection.name,
                    )
                    deleted_count += 1

            logger.info(
                "Project collections cleanup completed",
                project_id=project_id,
                deleted_count=deleted_count,
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to delete project collections",
                project_id=project_id,
                error=str(e),
            )
            return False


class VectorSearchEngine:
    """Sophisticated vector search with metadata filtering."""

    def __init__(
        self, client: QdrantClient, collection_manager: QdrantCollectionManager
    ):
        """Initialize search engine."""
        self.client = client
        self.collection_manager = collection_manager

    def search_level(
        self,
        level: int,
        query_vector: np.ndarray,
        k: int,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[SearchResult]:
        """Search within a specific memory level."""
        collection_name = self.collection_manager.get_collection_name(level)

        # Convert tensor to list for Qdrant
        query_list = (
            query_vector.tolist()
            if isinstance(query_vector, np.ndarray)
            else query_vector
        )

        # Build filter conditions
        filter_conditions = None
        if filters:
            filter_conditions = models.Filter(
                must=[
                    models.FieldCondition(key=key, match=models.MatchValue(value=value))
                    for key, value in filters.items()
                ]
            )

        try:
            search_result = self.client.search(
                collection_name=collection_name,
                query_vector=query_list,
                limit=k,
                query_filter=filter_conditions,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False,
            )

            results = []
            for point in search_result:
                # Extract CognitiveMemory from payload
                payload = point.payload
                if payload is None:
                    continue
                memory = CognitiveMemory(
                    id=payload.get("memory_id", str(point.id)),
                    content=payload.get("content", ""),
                    memory_type=payload.get("memory_type", "unknown"),
                    hierarchy_level=payload.get("hierarchy_level", level),
                    dimensions=payload.get("dimensions", {}),
                    timestamp=payload.get("timestamp", 0.0),
                    strength=payload.get("strength", 1.0),
                    access_count=payload.get("access_count", 0),
                )

                results.append(
                    SearchResult(
                        memory=memory,
                        similarity_score=point.score,
                        metadata={"collection": collection_name},
                    )
                )

            logger.debug(
                "Vector search completed",
                level=level,
                collection=collection_name,
                results_count=len(results),
                query_filters=filters,
            )

            return results

        except Exception as e:
            logger.error(
                "Vector search failed",
                level=level,
                collection=collection_name,
                error=str(e),
            )
            return []

    def search_cross_level(
        self,
        query_vector: np.ndarray,
        k_per_level: int,
        levels: list[int] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[int, list[SearchResult]]:
        """Search across multiple memory levels."""
        if levels is None:
            levels = [0, 1, 2]  # All levels

        results = {}
        for level in levels:
            level_results = self.search_level(
                level=level, query_vector=query_vector, k=k_per_level, filters=filters
            )
            results[level] = level_results

        return results


class HierarchicalMemoryStorage(VectorStorage):
    """
    Qdrant-based hierarchical memory storage system.

    Implements the VectorStorage interface with 3-tier hierarchical collections
    optimized for cognitive memory patterns and retrieval.
    """

    def __init__(
        self,
        vector_size: int,
        project_id: str,
        host: str | None = None,
        port: int | None = None,
        grpc_port: int | None = None,
        prefer_grpc: bool = True,
        timeout: int | None = None,
    ):
        """
        Initialize hierarchical memory storage.

        Args:
            vector_size: Dimension of embedding vectors (from configuration)
            project_id: Project identifier for collection namespacing
            host: Qdrant server host (defaults to config)
            port: Qdrant HTTP port (defaults to config)
            grpc_port: Qdrant gRPC port (defaults to config port + 1)
            prefer_grpc: Whether to prefer gRPC connection
            timeout: Connection timeout in seconds (defaults to config)
        """
        # Use defaults from config if not provided
        default_config = QdrantConfig()
        self.host = host or default_config.get_host()
        self.port = port or default_config.get_port()
        self.grpc_port = grpc_port or (self.port + 1)
        self.timeout = timeout or default_config.timeout
        self.vector_size = vector_size
        self.project_id = project_id

        # Initialize Qdrant client
        try:
            self.client = QdrantClient(
                host=self.host,
                port=self.port,
                grpc_port=self.grpc_port,
                prefer_grpc=prefer_grpc,
                timeout=self.timeout,
            )
            logger.info(
                "Connected to Qdrant server",
                host=host,
                port=port,
                grpc_port=grpc_port,
                prefer_grpc=prefer_grpc,
            )
        except Exception as e:
            logger.error("Failed to connect to Qdrant server", error=str(e))
            raise

        # Initialize collection manager and search engine
        self.collection_manager = QdrantCollectionManager(
            self.client, vector_size, project_id
        )
        self.search_engine = VectorSearchEngine(self.client, self.collection_manager)

        # Initialize collections
        if not self.collection_manager.initialize_collections():
            raise RuntimeError("Failed to initialize Qdrant collections")

    def store_vector(
        self, id: str, vector: np.ndarray | list[float], metadata: dict[str, Any]
    ) -> None:
        """
        Store a vector with associated metadata in appropriate hierarchy level.

        Args:
            id: Unique identifier for the vector
            vector: Cognitive embedding vector (dimension must match configured vector_size)
            metadata: Associated metadata including hierarchy_level
        """
        if not isinstance(vector, np.ndarray):
            vector = np.array(vector, dtype=np.float32)

        # Validate vector dimensions
        if vector.shape[-1] != self.vector_size:
            raise ValueError(
                f"Expected {self.vector_size}-dimensional vector, got {vector.shape[-1]}"
            )

        # Extract hierarchy level from metadata
        hierarchy_level = metadata.get("hierarchy_level", 2)  # Default to episodes
        if hierarchy_level not in [0, 1, 2]:
            raise ValueError(f"Invalid hierarchy level: {hierarchy_level}")

        # Get collection name for the level
        collection_name = self.collection_manager.get_collection_name(hierarchy_level)

        # Convert vector to list
        vector_list = vector.tolist() if vector.ndim == 1 else vector.flatten().tolist()

        # Create point structure
        point = PointStruct(id=id, vector=vector_list, payload=metadata)

        try:
            # Store in Qdrant
            self.client.upsert(collection_name=collection_name, points=[point])

            logger.debug(
                "Vector stored successfully",
                id=id,
                level=hierarchy_level,
                collection=collection_name,
                metadata_keys=list(metadata.keys()),
            )

        except Exception as e:
            logger.error(
                "Failed to store vector",
                id=id,
                level=hierarchy_level,
                collection=collection_name,
                error=str(e),
            )
            raise

    def search_similar(
        self, query_vector: np.ndarray, k: int, filters: dict | None = None
    ) -> list[SearchResult]:
        """
        Search for similar vectors across all hierarchy levels.

        Args:
            query_vector: Query vector for similarity search
            k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of SearchResult objects sorted by score
        """
        # Search across all levels
        k_per_level = max(1, k // 3)  # Distribute k across levels
        cross_level_results = self.search_engine.search_cross_level(
            query_vector=query_vector, k_per_level=k_per_level, filters=filters
        )

        # Combine and sort results
        all_results = []
        for results in cross_level_results.values():
            all_results.extend(results)

        # Sort by score (descending) and limit to k
        all_results.sort(key=lambda x: x.score, reverse=True)
        return all_results[:k]

    def search_by_level(
        self,
        query_vector: np.ndarray,
        level: int,
        k: int,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        """Search within a specific hierarchy level."""
        return self.search_engine.search_level(
            level=level, query_vector=query_vector, k=k, filters=filters
        )

    def delete_vector(self, id: str) -> bool:
        """
        Delete a vector by ID across all collections.

        Args:
            id: Vector ID to delete

        Returns:
            True if deleted, False otherwise
        """
        success = False

        for level in [0, 1, 2]:
            collection_name = self.collection_manager.get_collection_name(level)
            try:
                result = self.client.delete(
                    collection_name=collection_name,
                    points_selector=models.PointIdsList(points=[id]),
                )
                if result.status == models.UpdateStatus.COMPLETED:
                    success = True
                    logger.debug("Vector deleted", id=id, collection=collection_name)
            except Exception as e:
                logger.debug(
                    "Vector not found in collection (expected)",
                    id=id,
                    collection=collection_name,
                    error=str(e),
                )

        return success

    def delete_vectors_by_ids(self, memory_ids: list[str]) -> list[str]:
        """
        Delete vectors by their IDs across all collections.

        Args:
            memory_ids: List of vector IDs to delete

        Returns:
            List of successfully deleted memory IDs
        """
        if not memory_ids:
            return []

        successfully_deleted = []

        for memory_id in memory_ids:
            success = self.delete_vector(memory_id)
            if success:
                successfully_deleted.append(memory_id)

        logger.info(
            "Batch vector deletion completed",
            requested_count=len(memory_ids),
            deleted_count=len(successfully_deleted),
            deleted_ids=successfully_deleted[:5]
            if len(successfully_deleted) > 5
            else successfully_deleted,
        )

        return successfully_deleted

    def update_vector(
        self, id: str, vector: np.ndarray, metadata: dict[str, Any]
    ) -> bool:
        """
        Update an existing vector and its metadata.

        Args:
            id: Vector ID to update
            vector: New vector data
            metadata: New metadata

        Returns:
            True if updated, False otherwise
        """
        try:
            # Store vector (upsert will update if exists)
            self.store_vector(id, vector, metadata)
            return True
        except Exception as e:
            logger.error("Failed to update vector", id=id, error=str(e))
            return False

    def get_storage_stats(self) -> dict[str, Any]:
        """Get storage statistics for all collections."""
        stats = {}

        for level in [0, 1, 2]:
            collection_name = self.collection_manager.get_collection_name(level)
            try:
                info = self.client.get_collection(collection_name)
                stats[f"level_{level}"] = {
                    "collection_name": collection_name,
                    "vectors_count": info.points_count,  # Use points_count as vectors_count
                    "indexed_vectors_count": info.indexed_vectors_count,
                    "points_count": info.points_count,
                    "segments_count": info.segments_count,
                    "status": info.status,
                }
            except Exception as e:
                logger.error(f"Failed to get stats for level {level}", error=str(e))
                stats[f"level_{level}"] = {"error": str(e)}

        return stats

    def optimize_collections(self) -> bool:
        """Optimize all collections for better performance."""
        try:
            for level in [0, 1, 2]:
                collection_name = self.collection_manager.get_collection_name(level)
                self.client.update_collection(
                    collection_name=collection_name,
                    optimizer_config=models.OptimizersConfigDiff(
                        indexing_threshold=20000, memmap_threshold=20000
                    ),
                )
                logger.debug(
                    "Collection optimized", level=level, collection=collection_name
                )
            return True
        except Exception as e:
            logger.error("Failed to optimize collections", error=str(e))
            return False

    def close(self) -> None:
        """Close connection to Qdrant server."""
        try:
            self.client.close()
            logger.info("Qdrant connection closed")
        except Exception as e:
            logger.error("Error closing Qdrant connection", error=str(e))

    def __enter__(self) -> "HierarchicalMemoryStorage":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()


def create_hierarchical_storage(
    vector_size: int,
    project_id: str,
    host: str | None = None,
    port: int | None = None,
    grpc_port: int | None = None,
    prefer_grpc: bool = True,
) -> HierarchicalMemoryStorage:
    """
    Factory function to create hierarchical memory storage.

    Args:
        vector_size: Dimension of embedding vectors (from configuration)
        project_id: Project identifier for collection namespacing
        host: Qdrant server host (defaults to config)
        port: Qdrant HTTP port (defaults to config)
        grpc_port: Qdrant gRPC port (defaults to config port + 1)
        prefer_grpc: Whether to prefer gRPC connection

    Returns:
        HierarchicalMemoryStorage: Configured storage instance
    """
    return HierarchicalMemoryStorage(
        vector_size=vector_size,
        project_id=project_id,
        host=host,
        port=port,
        grpc_port=grpc_port,
        prefer_grpc=prefer_grpc,
    )
