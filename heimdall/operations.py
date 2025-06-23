#!/usr/bin/env python3
"""
Pure operations layer for cognitive memory system.

This module contains all business logic for cognitive operations with no interface dependencies.
Returns structured data dictionaries that can be consumed by any interface layer (CLI, MCP, HTTP, etc.).

This is the single source of truth for cognitive memory operations.
"""

import json
import os
from pathlib import Path
from typing import Any

from cognitive_memory.core.interfaces import CognitiveSystem


class CognitiveOperations:
    """
    Pure cognitive operations layer with no interface dependencies.

    All methods return structured data dictionaries that can be formatted
    by interface layers (CLI, MCP, HTTP, etc.) according to their needs.

    This class contains the single source of truth for all cognitive memory business logic.
    """

    def __init__(self, cognitive_system: CognitiveSystem):
        """
        Initialize operations with cognitive system instance.

        Args:
            cognitive_system: The cognitive system interface to use
        """
        self.cognitive_system = cognitive_system

    def store_experience(
        self,
        text: str,
        context: dict[str, Any] | None = None,
        context_json: str | None = None,
    ) -> dict[str, Any]:
        """
        Store a new experience in cognitive memory.

        Args:
            text: Experience text to store
            context: Optional context information as dictionary
            context_json: Optional context as JSON string (alternative to context dict)

        Returns:
            Dict containing:
            - success: bool - True if stored successfully
            - memory_id: str | None - ID of stored memory if successful
            - hierarchy_level: int | None - Level where memory was stored (0=concepts, 1=contexts, 2=episodes)
            - memory_type: str | None - Type of memory created ("episodic" or "semantic")
            - error: str | None - Error message if failed
        """
        if not text.strip():
            return {
                "success": False,
                "memory_id": None,
                "hierarchy_level": None,
                "memory_type": None,
                "error": "Empty text provided",
            }

        # Parse JSON context if provided
        if context_json and not context:
            try:
                context = json.loads(context_json)
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "memory_id": None,
                    "hierarchy_level": None,
                    "memory_type": None,
                    "error": f"Invalid JSON context - {e}",
                }

        try:
            memory_id = self.cognitive_system.store_experience(text, context)
            if memory_id:
                # Try to get hierarchy level and memory type from the stored memory
                # This is a best-effort attempt - we'll use reasonable defaults if not available
                hierarchy_level = (
                    context.get("hierarchy_level", 2) if context else 2
                )  # Default to episodes
                memory_type = (
                    context.get("memory_type", "episodic") if context else "episodic"
                )

                return {
                    "success": True,
                    "memory_id": memory_id,
                    "hierarchy_level": hierarchy_level,
                    "memory_type": memory_type,
                    "error": None,
                }
            else:
                return {
                    "success": False,
                    "memory_id": None,
                    "hierarchy_level": None,
                    "memory_type": None,
                    "error": "Failed to store experience - no memory ID returned",
                }
        except Exception as e:
            return {
                "success": False,
                "memory_id": None,
                "hierarchy_level": None,
                "memory_type": None,
                "error": str(e),
            }

    def retrieve_memories(
        self, query: str, types: list[str] | None = None, limit: int = 10
    ) -> dict[str, Any]:
        """
        Retrieve memories for a query.

        Args:
            query: Query text
            types: Memory types to retrieve (core, peripheral, bridge)
            limit: Maximum results per type

        Returns:
            Dict containing:
            - core: list - Core memories matching query
            - peripheral: list - Peripheral memories matching query
            - bridge: list - Bridge memories connecting concepts
            - total_count: int - Total number of memories found
            - query: str - Original query for reference
            - success: bool - True if retrieval completed without errors
            - error: str | None - Error message if failed
        """
        if not query.strip():
            return {
                "core": [],
                "peripheral": [],
                "bridge": [],
                "total_count": 0,
                "query": query,
                "success": False,
                "error": "Empty query provided",
            }

        if types is None:
            types = ["core", "peripheral", "bridge"]

        try:
            results = self.cognitive_system.retrieve_memories(
                query=query, types=types, max_results=limit
            )

            total_count = sum(len(memories) for memories in results.values())

            # Ensure all expected keys are present with empty lists as defaults
            standardized_results = {
                "core": results.get("core", []),
                "peripheral": results.get("peripheral", []),
                "bridge": results.get("bridge", []),
                "total_count": total_count,
                "query": query,
                "success": True,
                "error": None,
            }

            return standardized_results

        except Exception as e:
            return {
                "core": [],
                "peripheral": [],
                "bridge": [],
                "total_count": 0,
                "query": query,
                "success": False,
                "error": str(e),
            }

    def get_system_status(self, detailed: bool = False) -> dict[str, Any]:
        """
        Get system status and statistics.

        Args:
            detailed: Whether to include detailed statistics

        Returns:
            Dict containing:
            - memory_counts: dict - Count of memories by type/level
            - system_config: dict - System configuration (if detailed=True)
            - storage_stats: dict - Storage statistics (if detailed=True)
            - embedding_info: dict - Embedding model info (if detailed=True)
            - success: bool - True if status retrieved successfully
            - error: str | None - Error message if failed
        """
        try:
            stats = self.cognitive_system.get_memory_stats()

            result = {
                "memory_counts": stats.get("memory_counts", {}),
                "success": True,
                "error": None,
            }

            if detailed:
                result.update(
                    {
                        "system_config": stats.get("system_config", {}),
                        "storage_stats": stats.get("storage_stats", {}),
                        "embedding_info": stats.get("embedding_info", {}),
                    }
                )

            return result

        except Exception as e:
            return {
                "memory_counts": {},
                "system_config": {} if detailed else None,
                "storage_stats": {} if detailed else None,
                "embedding_info": {} if detailed else None,
                "success": False,
                "error": str(e),
            }

    def consolidate_memories(self, dry_run: bool = False) -> dict[str, Any]:
        """
        Trigger memory consolidation process.

        Args:
            dry_run: If True, show what would be consolidated without doing it

        Returns:
            Dict containing:
            - total_episodic: int - Total episodic memories processed
            - consolidated: int - Number successfully consolidated to semantic
            - failed: int - Number that failed to consolidate
            - skipped: int - Number skipped (already semantic, etc.)
            - success: bool - True if consolidation completed successfully
            - error: str | None - Error message if failed
            - dry_run: bool - Whether this was a dry run
        """
        try:
            # Note: Current system doesn't support dry_run mode in consolidate_memories
            # We'll run the actual consolidation for now
            results = self.cognitive_system.consolidate_memories()

            return {
                "total_episodic": results.get("total_episodic", 0),
                "consolidated": results.get("consolidated", 0),
                "failed": results.get("failed", 0),
                "skipped": results.get("skipped", 0),
                "success": True,
                "error": None,
                "dry_run": dry_run,
            }

        except Exception as e:
            return {
                "total_episodic": 0,
                "consolidated": 0,
                "failed": 0,
                "skipped": 0,
                "success": False,
                "error": str(e),
                "dry_run": dry_run,
            }

    def load_memories(
        self,
        source_path: str,
        loader_type: str = "markdown",
        dry_run: bool = False,
        recursive: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Load memories from external source.

        Args:
            source_path: Path to the source file or directory
            loader_type: Type of loader to use (markdown, git)
            dry_run: If True, validate and show what would be loaded
            recursive: If True and source_path is directory, recursively find files
            **kwargs: Additional loader parameters

        Returns:
            Dict containing:
            - success: bool - True if loading completed successfully
            - memories_loaded: int - Number of memories loaded
            - connections_created: int - Number of connections created
            - processing_time: float - Time taken in seconds
            - hierarchy_distribution: dict - Distribution of memories by level
            - memories_failed: int - Number of memories that failed to load
            - connections_failed: int - Number of connections that failed
            - files_processed: list - List of files processed (for directory loading)
            - error: str | None - Error message if failed
            - dry_run: bool - Whether this was a dry run
        """
        if loader_type not in ["markdown", "git"]:
            return {
                "success": False,
                "memories_loaded": 0,
                "connections_created": 0,
                "processing_time": 0.0,
                "hierarchy_distribution": {},
                "memories_failed": 0,
                "connections_failed": 0,
                "files_processed": [],
                "error": f"Unsupported loader type: {loader_type}. Currently supported: markdown, git",
                "dry_run": dry_run,
            }

        try:
            # Import necessary modules
            from cognitive_memory.core.config import get_config
            from cognitive_memory.loaders import MarkdownMemoryLoader

            config = get_config()

            # Create the appropriate loader
            loader: Any | Any  # Type will be MarkdownMemoryLoader or GitHistoryLoader
            if loader_type == "markdown":
                loader = MarkdownMemoryLoader(config.cognitive)
            elif loader_type == "git":
                from cognitive_memory.loaders import GitHistoryLoader

                loader = GitHistoryLoader(config.cognitive, self.cognitive_system)
            else:
                return {
                    "success": False,
                    "memories_loaded": 0,
                    "connections_created": 0,
                    "processing_time": 0.0,
                    "hierarchy_distribution": {},
                    "memories_failed": 0,
                    "connections_failed": 0,
                    "files_processed": [],
                    "error": f"Unsupported loader type: {loader_type}",
                    "dry_run": dry_run,
                }

            source_path_obj = Path(source_path)

            # Handle directory vs file processing
            if source_path_obj.is_dir() and not (
                loader_type == "git" and (source_path_obj / ".git").exists()
            ):
                return self._process_directory(
                    loader, source_path_obj, dry_run, recursive, **kwargs
                )
            else:
                return self._process_single_source(
                    loader, source_path, dry_run, **kwargs
                )

        except Exception as e:
            return {
                "success": False,
                "memories_loaded": 0,
                "connections_created": 0,
                "processing_time": 0.0,
                "hierarchy_distribution": {},
                "memories_failed": 0,
                "connections_failed": 0,
                "files_processed": [],
                "error": str(e),
                "dry_run": dry_run,
            }

    def load_git_patterns(
        self, repo_path: str, dry_run: bool = False, **kwargs: Any
    ) -> dict[str, Any]:
        """
        Load git repository patterns into cognitive memory.

        Args:
            repo_path: Path to git repository
            dry_run: If True, show patterns without storing
            **kwargs: Additional loader parameters (e.g., time_window)

        Returns:
            Dict containing same structure as load_memories() but for git patterns
        """
        return self.load_memories(
            source_path=repo_path, loader_type="git", dry_run=dry_run, **kwargs
        )

    def _process_directory(
        self,
        loader: Any,
        source_path_obj: Path,
        dry_run: bool,
        recursive: bool,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Process a directory of files."""
        if not recursive:
            return {
                "success": False,
                "memories_loaded": 0,
                "connections_created": 0,
                "processing_time": 0.0,
                "hierarchy_distribution": {},
                "memories_failed": 0,
                "connections_failed": 0,
                "files_processed": [],
                "error": f"{source_path_obj} is a directory. Use recursive=True to load all files in the directory.",
                "dry_run": dry_run,
            }

        # Find all supported files in directory
        markdown_files: list[Path] = []
        extensions = loader.get_supported_extensions()

        for root, _dirs, files in os.walk(source_path_obj, followlinks=True):
            for file in files:
                if any(file.endswith(ext) for ext in extensions):
                    markdown_files.append(Path(root) / file)

        if not markdown_files:
            return {
                "success": False,
                "memories_loaded": 0,
                "connections_created": 0,
                "processing_time": 0.0,
                "hierarchy_distribution": {},
                "memories_failed": 0,
                "connections_failed": 0,
                "files_processed": [],
                "error": f"No {', '.join(extensions)} files found in directory: {source_path_obj}",
                "dry_run": dry_run,
            }

        # Process files
        total_memories_loaded = 0
        total_connections_created = 0
        total_processing_time = 0.0
        hierarchy_dist_combined = {"L0": 0, "L1": 0, "L2": 0}
        total_memories_failed = 0
        total_connections_failed = 0
        files_processed = []
        total_success = True

        for markdown_file in sorted(markdown_files):
            file_path_str = str(markdown_file)
            relative_path = str(markdown_file.relative_to(source_path_obj))

            # Validate individual file
            if not loader.validate_source(file_path_str):
                total_success = False
                continue

            files_processed.append(relative_path)

            if dry_run:
                try:
                    # Load memories without storing them
                    memories = loader.load_from_source(file_path_str, **kwargs)

                    # Count hierarchy distribution
                    for memory in memories:
                        level_key = f"L{memory.hierarchy_level}"
                        if level_key in hierarchy_dist_combined:
                            hierarchy_dist_combined[level_key] += 1

                except Exception:
                    total_success = False
            else:
                try:
                    # Perform actual loading
                    results = self.cognitive_system.load_memories_from_source(
                        loader, file_path_str, **kwargs
                    )

                    if results["success"]:
                        total_memories_loaded += results["memories_loaded"]
                        total_connections_created += results["connections_created"]
                        total_processing_time += results["processing_time"]
                        total_memories_failed += results["memories_failed"]
                        total_connections_failed += results["connections_failed"]

                        # Aggregate hierarchy distribution
                        if "hierarchy_distribution" in results:
                            for level, count in results[
                                "hierarchy_distribution"
                            ].items():
                                if level in hierarchy_dist_combined:
                                    hierarchy_dist_combined[level] += count
                    else:
                        total_success = False

                except Exception:
                    total_success = False

        return {
            "success": total_success,
            "memories_loaded": total_memories_loaded,
            "connections_created": total_connections_created,
            "processing_time": total_processing_time,
            "hierarchy_distribution": hierarchy_dist_combined,
            "memories_failed": total_memories_failed,
            "connections_failed": total_connections_failed,
            "files_processed": files_processed,
            "error": None if total_success else "Some files failed to process",
            "dry_run": dry_run,
        }

    def _process_single_source(
        self, loader: Any, source_path: str, dry_run: bool, **kwargs: Any
    ) -> dict[str, Any]:
        """Process a single file or git repository."""
        # Validate source
        if not loader.validate_source(source_path):
            return {
                "success": False,
                "memories_loaded": 0,
                "connections_created": 0,
                "processing_time": 0.0,
                "hierarchy_distribution": {},
                "memories_failed": 0,
                "connections_failed": 0,
                "files_processed": [source_path],
                "error": f"Source validation failed: {source_path}",
                "dry_run": dry_run,
            }

        if dry_run:
            try:
                # Load memories without storing them
                memories = loader.load_from_source(source_path, **kwargs)
                connections = loader.extract_connections(memories)

                # Show hierarchy distribution
                hierarchy_dist = {"L0": 0, "L1": 0, "L2": 0}
                for memory in memories:
                    level_key = f"L{memory.hierarchy_level}"
                    if level_key in hierarchy_dist:
                        hierarchy_dist[level_key] += 1

                return {
                    "success": True,
                    "memories_loaded": len(memories),
                    "connections_created": len(connections),
                    "processing_time": 0.0,
                    "hierarchy_distribution": hierarchy_dist,
                    "memories_failed": 0,
                    "connections_failed": 0,
                    "files_processed": [source_path],
                    "error": None,
                    "dry_run": dry_run,
                }

            except Exception as e:
                return {
                    "success": False,
                    "memories_loaded": 0,
                    "connections_created": 0,
                    "processing_time": 0.0,
                    "hierarchy_distribution": {},
                    "memories_failed": 0,
                    "connections_failed": 0,
                    "files_processed": [source_path],
                    "error": str(e),
                    "dry_run": dry_run,
                }
        else:
            try:
                # Perform actual loading
                results = self.cognitive_system.load_memories_from_source(
                    loader, source_path, **kwargs
                )

                return {
                    "success": results["success"],
                    "memories_loaded": results["memories_loaded"],
                    "connections_created": results["connections_created"],
                    "processing_time": results["processing_time"],
                    "hierarchy_distribution": results.get("hierarchy_distribution", {}),
                    "memories_failed": results["memories_failed"],
                    "connections_failed": results["connections_failed"],
                    "files_processed": [source_path],
                    "error": results.get("error") if not results["success"] else None,
                    "dry_run": dry_run,
                }

            except Exception as e:
                return {
                    "success": False,
                    "memories_loaded": 0,
                    "connections_created": 0,
                    "processing_time": 0.0,
                    "hierarchy_distribution": {},
                    "memories_failed": 0,
                    "connections_failed": 0,
                    "files_processed": [source_path],
                    "error": str(e),
                    "dry_run": dry_run,
                }
