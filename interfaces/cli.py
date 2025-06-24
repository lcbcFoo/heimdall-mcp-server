#!/usr/bin/env python3
"""
Simple command-line interface for the cognitive memory system.

This module provides a stdio-based CLI that enables users to interact with
the cognitive memory system through basic commands for storing experiences
and retrieving memories.
"""

import argparse
import json
import sys
from typing import Any

from cognitive_memory.core.interfaces import CognitiveSystem
from cognitive_memory.loaders import MarkdownMemoryLoader
from cognitive_memory.main import (
    InitializationError,
    graceful_shutdown,
    initialize_system,
    initialize_with_config,
)
from heimdall.display_utils import format_source_info


class CognitiveCLI:
    """
    Command-line interface for cognitive memory operations.

    Provides basic commands for storing experiences, retrieving memories,
    checking system status, and managing the memory system.
    """

    def __init__(self, cognitive_system: CognitiveSystem):
        """
        Initialize CLI with cognitive system instance.

        Args:
            cognitive_system: The cognitive system interface to use
        """
        self.cognitive_system = cognitive_system
        self.interactive_mode = False

    def store_experience(
        self,
        text: str,
        context: dict[str, Any] | None = None,
        context_json: str | None = None,
    ) -> bool:
        """
        Store a new experience.

        Args:
            text: Experience text to store
            context: Optional context information
            context_json: Optional context as JSON string

        Returns:
            bool: True if stored successfully
        """
        if not text.strip():
            print("Error: Empty text provided")
            return False

        # Parse JSON context if provided
        if context_json and not context:
            try:
                context = json.loads(context_json)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON context - {e}")
                return False

        try:
            memory_id = self.cognitive_system.store_experience(text, context)
            if memory_id:
                print(f"✓ Experience stored with ID: {memory_id}")
                return True
            else:
                print("✗ Failed to store experience")
                return False
        except Exception as e:
            print(f"✗ Error storing experience: {e}")
            return False

    def retrieve_memories(
        self,
        query: str,
        types: list[str] | None = None,
        limit: int = 10,
        display: bool = True,
    ) -> dict[str, list] | None:
        """
        Retrieve memories for a query.

        Args:
            query: Query text
            types: Memory types to retrieve
            limit: Maximum results per type
            display: Whether to print results to console

        Returns:
            dict[str, list] | None: Dictionary with memory types as keys and lists of memories as values,
                                   or None if retrieval failed
        """
        if not query.strip():
            if display:
                print("Error: Empty query provided")
            return None

        if types is None:
            types = ["core", "peripheral", "bridge"]

        try:
            results = self.cognitive_system.retrieve_memories(
                query=query, types=types, max_results=limit
            )

            if display:
                total_results = sum(len(memories) for memories in results.values())
                if total_results == 0:
                    print("No memories found for query")
                    return results  # Return empty results instead of True

                print(f"\n📋 Retrieved {total_results} memories for: '{query}'")

                for memory_type, memories in results.items():
                    if memories:
                        print(f"\n{memory_type.upper()} MEMORIES ({len(memories)}):")
                        for i, memory_item in enumerate(memories, 1):
                            # Handle bridge memories (BridgeMemory objects) vs regular memories (CognitiveMemory)
                            if memory_type == "bridge" and hasattr(
                                memory_item, "memory"
                            ):
                                # Type narrowing for BridgeMemory
                                from cognitive_memory.core.memory import BridgeMemory

                                bridge_mem = memory_item
                                assert isinstance(bridge_mem, BridgeMemory)
                                memory = bridge_mem.memory
                                print(f"  {i}. [bridge] {memory.content[:100]}...")

                                # Format source information for bridge memory
                                source_info = format_source_info(memory)

                                print(
                                    f"     ID: {memory.id}, Level: L{memory.hierarchy_level}, "
                                    f"Novelty: {bridge_mem.novelty_score:.2f}, "
                                    f"Connection: {bridge_mem.connection_potential:.2f}, "
                                    f"Bridge Score: {bridge_mem.bridge_score:.2f}"
                                )
                                if source_info:
                                    print(f"     Source: {source_info}")
                            else:
                                # Regular CognitiveMemory object
                                from cognitive_memory.core.memory import CognitiveMemory

                                assert isinstance(memory_item, CognitiveMemory)
                                memory = memory_item
                                print(
                                    f"  {i}. [{memory.memory_type}] {memory.content[:100]}..."
                                )
                                # Use similarity score from metadata if available, otherwise fallback to memory strength
                                score = memory.metadata.get(
                                    "similarity_score", memory.strength
                                )

                                # Format source information
                                source_info = format_source_info(memory)

                                print(
                                    f"     ID: {memory.id}, Level: L{memory.hierarchy_level}, "
                                    f"Strength: {score:.2f}"
                                )
                                if source_info:
                                    print(f"     Source: {source_info}")

            return results

        except Exception as e:
            if display:
                print(f"✗ Error retrieving memories: {e}")
            return None

    def show_status(self, detailed: bool = False, display: bool = True) -> dict | None:
        """
        Show system status and statistics.

        Args:
            detailed: Whether to include detailed statistics
            display: Whether to print status to console

        Returns:
            dict | None: Status dictionary with system information, or None if retrieval failed
        """
        try:
            stats = self.cognitive_system.get_memory_stats()

            if display:
                print("\n📊 COGNITIVE MEMORY SYSTEM STATUS")
                print("=" * 40)

                # Basic counts
                if "memory_counts" in stats:
                    print("\nMemory Counts:")
                    for key, count in stats["memory_counts"].items():
                        if isinstance(count, int):
                            level_name = (
                                key.replace("level_", "").replace("_", " ").title()
                            )
                            print(f"  {level_name}: {count}")

                # Configuration
                if detailed and "system_config" in stats:
                    print("\nConfiguration:")
                    config = stats["system_config"]
                    print(
                        f"  Activation Threshold: {config.get('activation_threshold', 'N/A')}"
                    )
                    print(
                        f"  Bridge Discovery K: {config.get('bridge_discovery_k', 'N/A')}"
                    )
                    print(f"  Max Activations: {config.get('max_activations', 'N/A')}")

                # Storage statistics
                if detailed and "storage_stats" in stats and stats["storage_stats"]:
                    print("\nStorage Statistics:")
                    storage_stats = stats["storage_stats"]
                    for level_key, level_stats in storage_stats.items():
                        if (
                            isinstance(level_stats, dict)
                            and "vectors_count" in level_stats
                        ):
                            print(
                                f"  {level_key}: {level_stats['vectors_count']} vectors"
                            )

                # Embedding info
                if detailed and "embedding_info" in stats:
                    print("\nEmbedding Model:")
                    info = stats["embedding_info"]
                    print(f"  Model: {info.get('model_name', 'N/A')}")
                    print(f"  Dimensions: {info.get('embedding_dimension', 'N/A')}")

            return stats

        except Exception as e:
            if display:
                print(f"✗ Error retrieving status: {e}")
            return None

    def consolidate_memories(self, dry_run: bool = False) -> bool:
        """
        Trigger memory consolidation.

        Args:
            dry_run: If True, show what would be consolidated without doing it

        Returns:
            bool: True if consolidation completed successfully
        """
        if dry_run:
            print("🔍 Dry run mode: showing consolidation candidates")
            # For now, just run normal consolidation as we don't have dry-run support

        try:
            print("🔄 Starting memory consolidation...")
            results = self.cognitive_system.consolidate_memories()

            print("✓ Consolidation completed:")
            print(f"  Total episodic memories: {results.get('total_episodic', 0)}")
            print(f"  Consolidated to semantic: {results.get('consolidated', 0)}")
            print(f"  Failed: {results.get('failed', 0)}")
            print(f"  Skipped: {results.get('skipped', 0)}")

            return True

        except Exception as e:
            print(f"✗ Error during consolidation: {e}")
            return False

    def load_memories(
        self,
        source_path: str,
        loader_type: str = "markdown",
        dry_run: bool = False,
        recursive: bool = False,
        **kwargs: Any,
    ) -> bool:
        """
        Load memories from external source.

        Args:
            source_path: Path to the source file or directory
            loader_type: Type of loader to use (currently only 'markdown')
            dry_run: If True, validate and show what would be loaded
            recursive: If True and source_path is a directory, recursively find all markdown files
            **kwargs: Additional loader parameters

        Returns:
            bool: True if loading completed successfully
        """
        if loader_type not in ["markdown", "git"]:
            print(f"✗ Unsupported loader type: {loader_type}")
            print("   Currently supported: markdown, git")
            return False

        try:
            # Import config function - we need it for the loader
            from pathlib import Path

            from cognitive_memory.core.config import get_config

            config = get_config()

            # Create the appropriate loader
            loader: Any
            if loader_type == "markdown":
                loader = MarkdownMemoryLoader(config.cognitive)
            elif loader_type == "git":
                from cognitive_memory.loaders import GitHistoryLoader

                loader = GitHistoryLoader(config.cognitive, self.cognitive_system)
            else:
                # This shouldn't happen due to earlier check, but be safe
                print(f"✗ Unsupported loader type: {loader_type}")
                return False

            # Handle directory vs file input
            source_path_obj = Path(source_path)

            if source_path_obj.is_dir() and not (
                loader_type == "git" and (source_path_obj / ".git").exists()
            ):
                # Handle directory processing for non-git loaders
                if not recursive:
                    print(
                        f"✗ {source_path} is a directory. Use --recursive to load all markdown files in the directory."
                    )
                    return False

                # Find all files in directory (following symlinks)
                markdown_files: list[Path] = []
                extensions = loader.get_supported_extensions()

                import os

                for root, _dirs, files in os.walk(source_path_obj, followlinks=True):
                    for file in files:
                        if any(file.endswith(ext) for ext in extensions):
                            markdown_files.append(Path(root) / file)

                if not markdown_files:
                    print(f"✗ No markdown files found in directory: {source_path}")
                    return False

                print(f"📁 Found {len(markdown_files)} markdown files in {source_path}")
                if not dry_run:
                    print("   Files to process:")
                    for f in sorted(markdown_files):
                        rel_path = f.relative_to(source_path_obj)
                        print(f"     - {rel_path}")

                # Process each file
                total_success = True
                total_memories_loaded = 0
                total_connections_created = 0
                total_processing_time = 0.0
                hierarchy_dist_combined = {"L0": 0, "L1": 0, "L2": 0}
                total_memories_failed = 0
                total_connections_failed = 0

                for markdown_file in sorted(markdown_files):
                    file_path_str = str(markdown_file)

                    # Validate individual file
                    if not loader.validate_source(file_path_str):
                        print(
                            f"⚠️ Skipping invalid file: {markdown_file.relative_to(source_path_obj)}"
                        )
                        continue

                    if dry_run:
                        print(
                            f"\n📄 Analyzing: {markdown_file.relative_to(source_path_obj)}"
                        )
                        try:
                            # Load memories without storing them
                            memories = loader.load_from_source(file_path_str, **kwargs)
                            connections = loader.extract_connections(memories)

                            print(f"   Would load {len(memories)} memories")

                            # Count hierarchy distribution
                            for memory in memories:
                                level_key = f"L{memory.hierarchy_level}"
                                if level_key in hierarchy_dist_combined:
                                    hierarchy_dist_combined[level_key] += 1

                            print(f"   Would create {len(connections)} connections")

                        except Exception as e:
                            print(
                                f"   ✗ Error analyzing {markdown_file.relative_to(source_path_obj)}: {e}"
                            )
                            total_success = False
                    else:
                        print(
                            f"\n📄 Loading: {markdown_file.relative_to(source_path_obj)}"
                        )
                        try:
                            # Perform actual loading
                            results = self.cognitive_system.load_memories_from_source(
                                loader, file_path_str, **kwargs
                            )

                            if results["success"]:
                                total_memories_loaded += results["memories_loaded"]
                                total_connections_created += results[
                                    "connections_created"
                                ]
                                total_processing_time += results["processing_time"]
                                total_memories_failed += results["memories_failed"]
                                total_connections_failed += results[
                                    "connections_failed"
                                ]

                                # Aggregate hierarchy distribution
                                if "hierarchy_distribution" in results:
                                    for level, count in results[
                                        "hierarchy_distribution"
                                    ].items():
                                        if level in hierarchy_dist_combined:
                                            hierarchy_dist_combined[level] += count

                                print(
                                    f"   ✓ Loaded {results['memories_loaded']} memories, {results['connections_created']} connections"
                                )
                            else:
                                print(
                                    f"   ✗ Failed to load {markdown_file.relative_to(source_path_obj)}: {results.get('error', 'Unknown error')}"
                                )
                                total_success = False

                        except Exception as e:
                            print(
                                f"   ✗ Error loading {markdown_file.relative_to(source_path_obj)}: {e}"
                            )
                            total_success = False

                # Show summary
                if dry_run:
                    print(
                        f"\n✓ Dry run complete: Would load {sum(hierarchy_dist_combined.values())} total memories"
                    )
                    print("  Combined hierarchy distribution:")
                    for level, count in hierarchy_dist_combined.items():
                        level_name = {
                            "L0": "Concepts",
                            "L1": "Contexts",
                            "L2": "Episodes",
                        }[level]
                        print(f"    {level} ({level_name}): {count} memories")
                else:
                    print(
                        f"\n{'✓' if total_success else '⚠️'} Directory loading {'completed successfully' if total_success else 'completed with errors'}"
                    )
                    print(f"  Total memories loaded: {total_memories_loaded}")
                    print(f"  Total connections created: {total_connections_created}")
                    print(f"  Total processing time: {total_processing_time:.2f}s")

                    if hierarchy_dist_combined:
                        print("  Combined hierarchy distribution:")
                        for level, count in hierarchy_dist_combined.items():
                            level_name = {
                                "L0": "Concepts",
                                "L1": "Contexts",
                                "L2": "Episodes",
                            }[level]
                            print(f"    {level} ({level_name}): {count}")

                    if total_memories_failed > 0:
                        print(f"  ⚠️ Total failed memories: {total_memories_failed}")
                    if total_connections_failed > 0:
                        print(
                            f"  ⚠️ Total failed connections: {total_connections_failed}"
                        )

                return total_success
            else:
                # Single file processing (existing logic)
                # Validate source
                if not loader.validate_source(source_path):
                    print(f"✗ Source validation failed: {source_path}")
                    return False

                if dry_run:
                    print(f"🔍 Dry run mode: analyzing {source_path}")
                    try:
                        # Load memories without storing them
                        memories = loader.load_from_source(source_path, **kwargs)
                        connections = loader.extract_connections(memories)

                        print(f"✓ Would load {len(memories)} memories:")

                        # Show hierarchy distribution
                        hierarchy_dist = {"L0": 0, "L1": 0, "L2": 0}
                        for memory in memories:
                            level_key = f"L{memory.hierarchy_level}"
                            if level_key in hierarchy_dist:
                                hierarchy_dist[level_key] += 1

                        for level, count in hierarchy_dist.items():
                            level_name = {
                                "L0": "Concepts",
                                "L1": "Contexts",
                                "L2": "Episodes",
                            }[level]
                            print(f"  {level} ({level_name}): {count} memories")

                        print(f"✓ Would create {len(connections)} connections")

                        # Show sample memories
                        print("\nSample memories:")
                        for i, memory in enumerate(memories[:5]):
                            title = memory.metadata.get("title", "Untitled")
                            print(
                                f"  {i + 1}. L{memory.hierarchy_level}: {title[:60]}..."
                            )

                        if len(memories) > 5:
                            print(f"  ... and {len(memories) - 5} more")

                        return True

                    except Exception as e:
                        print(f"✗ Error during dry run: {e}")
                        return False
                else:
                    print(f"📁 Loading memories from {source_path}...")

                    # Perform actual loading
                    results = self.cognitive_system.load_memories_from_source(
                        loader, source_path, **kwargs
                    )

                    if results["success"]:
                        print("✓ Memory loading completed successfully")
                        print(f"  Memories loaded: {results['memories_loaded']}")
                        print(
                            f"  Connections created: {results['connections_created']}"
                        )
                        print(f"  Processing time: {results['processing_time']:.2f}s")

                        # Show hierarchy distribution
                        if "hierarchy_distribution" in results:
                            print("  Hierarchy distribution:")
                            for level, count in results[
                                "hierarchy_distribution"
                            ].items():
                                level_name = {
                                    "L0": "Concepts",
                                    "L1": "Contexts",
                                    "L2": "Episodes",
                                }[level]
                                print(f"    {level} ({level_name}): {count}")

                        if results["memories_failed"] > 0:
                            print(
                                f"  ⚠️ Failed to load {results['memories_failed']} memories"
                            )

                        if results["connections_failed"] > 0:
                            print(
                                f"  ⚠️ Failed to create {results['connections_failed']} connections"
                            )

                        return True
                    else:
                        print(
                            f"✗ Memory loading failed: {results.get('error', 'Unknown error')}"
                        )
                        return False

        except Exception as e:
            print(f"✗ Error loading memories: {e}")
            return False

    def clear_memories(self, memory_type: str = "all", confirm: bool = False) -> bool:
        """
        Clear memories (placeholder - not implemented for safety).

        Args:
            memory_type: Type of memories to clear
            confirm: Confirmation flag

        Returns:
            bool: Always False (not implemented)
        """
        print("⚠️  Memory clearing not implemented for safety")
        print("   Use database tools directly if needed")
        return False

    def load_git_patterns(
        self,
        repo_path: str,
        dry_run: bool = False,
        refresh: bool = False,
        **kwargs: Any,
    ) -> bool:
        """
        Load git repository patterns into cognitive memory.

        This method delegates to the existing load_memories() method with git loader type.
        The system automatically handles pattern updates via deterministic IDs and upserts.

        Args:
            repo_path: Path to git repository
            dry_run: If True, show patterns without storing
            refresh: Ignored - system handles updates automatically
            **kwargs: Additional loader parameters (e.g., time_window)

        Returns:
            bool: True if loading completed successfully
        """
        # Delegate to existing load_memories method with git loader type
        return self.load_memories(
            source_path=repo_path, loader_type="git", dry_run=dry_run, **kwargs
        )

    def show_git_status(self, repo_path: str | None = None) -> bool:
        """
        Show git analysis status and pattern statistics.

        This method extends the existing show_status() method with git-specific information.

        Args:
            repo_path: Optional repository path to analyze

        Returns:
            bool: True if status retrieved successfully
        """
        try:
            if repo_path:
                from pathlib import Path

                repo_path_obj = Path(repo_path)
                if not repo_path_obj.exists():
                    print(f"✗ Repository path does not exist: {repo_path}")
                    return False

                if not (repo_path_obj / ".git").exists():
                    print(f"✗ Not a git repository: {repo_path}")
                    return False

                print(f"📊 Git Analysis Status for: {repo_path}")
                print("=" * 50)

                # Use existing search functionality to find git patterns
                return self.search_git_patterns("", limit=0)  # Just show counts
            else:
                # Show overall status using existing method, then add git-specific info
                print("📊 System Status with Git Analysis")
                print("=" * 40)

                success = self.show_status(detailed=False)
                if success:
                    print("\n" + "=" * 40)
                    # Add git pattern summary
                    self.search_git_patterns("", limit=0)  # Just show counts

                return bool(success)

        except Exception as e:
            print(f"✗ Error retrieving git status: {e}")
            return False

    def search_git_patterns(
        self, query: str, pattern_type: str | None = None, limit: int = 10
    ) -> bool:
        """
        Search for specific git patterns.

        This method extends the existing retrieve_memories() method with git pattern filtering.

        Args:
            query: Search query
            pattern_type: Optional pattern type filter (cochange, hotspot, solution)
            limit: Maximum results to show

        Returns:
            bool: True if search completed successfully
        """
        try:
            # Build search query - use git-specific terms
            search_query = f"git pattern {query}" if query.strip() else "git pattern"
            if pattern_type:
                search_query = f"{pattern_type} {search_query}"

            # Use existing retrieve_memories method
            success = self.retrieve_memories(
                query=search_query,
                types=["core", "peripheral"],
                limit=limit * 2,  # Get more to filter for git patterns
            )

            # If this was just a count request (limit=0), show git pattern summary
            if limit == 0 and success:
                print("\n📊 Git Pattern Summary:")
                results = self.cognitive_system.retrieve_memories(
                    query="git pattern", types=["core", "peripheral"], max_results=1000
                )

                total_patterns = sum(len(memories) for memories in results.values())
                print(f"  Total git patterns: {total_patterns}")

                # Count by pattern type (simplified)
                pattern_counts = {"cochange": 0, "hotspot": 0, "solution": 0}
                for _memory_type, memories in results.items():
                    for memory in memories:
                        # Handle both CognitiveMemory and BridgeMemory types
                        from cognitive_memory.core.memory import BridgeMemory

                        if isinstance(memory, BridgeMemory):
                            actual_memory = memory.memory
                        else:
                            actual_memory = memory

                        if actual_memory.id.startswith("git::"):
                            pattern_type_found = actual_memory.metadata.get(
                                "pattern_type", "unknown"
                            )
                            if pattern_type_found in pattern_counts:
                                pattern_counts[pattern_type_found] += 1

                for ptype, count in pattern_counts.items():
                    type_name = {
                        "cochange": "Co-change patterns",
                        "hotspot": "Maintenance hotspots",
                        "solution": "Solution patterns",
                    }[ptype]
                    print(f"  {type_name}: {count}")

            return bool(success)

        except Exception as e:
            print(f"✗ Error searching git patterns: {e}")
            return False

    def interactive_mode_loop(self) -> None:
        """Run interactive mode with command prompt."""
        self.interactive_mode = True
        print("\n🧠 Cognitive Memory Interactive Mode")
        print("Type 'help' for commands, 'quit' to exit")
        print("-" * 40)

        while True:
            try:
                command = input("\ncognitive> ").strip()

                if not command:
                    continue

                if command.lower() in ["quit", "exit", "q"]:
                    print("Goodbye!")
                    break

                elif command.lower() in ["help", "h", "?"]:
                    self._show_interactive_help()

                elif command.startswith("store "):
                    text = command[6:].strip()
                    self.store_experience(text)

                elif command.startswith("retrieve "):
                    query = command[9:].strip()
                    self.retrieve_memories(query)

                elif command.startswith("bridges "):
                    query = command[8:].strip()
                    self.retrieve_memories(query, types=["bridge"])

                elif command.lower() == "status":
                    self.show_status()

                elif command.lower() == "config":
                    self.show_status(detailed=True)

                elif command.lower() == "consolidate":
                    self.consolidate_memories()

                elif command.startswith("load "):
                    source_path = command[5:].strip()
                    if source_path:
                        self.load_memories(source_path)
                    else:
                        print("Usage: load <file_path>")

                else:
                    print(f"Unknown command: {command}")
                    print("Type 'help' for available commands")

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except EOFError:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")

    def _show_interactive_help(self) -> None:
        """Show help for interactive mode commands."""
        print("\nAvailable Commands:")
        print("  store <text>           - Store new experience")
        print("  retrieve <query>       - Retrieve memories (now shows source info)")
        print("  bridges <query>        - Show bridge connections")
        print("  load <file_path>       - Load memories from file")
        print("  status                 - Show system status")
        print("  config                 - Show detailed configuration")
        print("  consolidate            - Trigger memory consolidation")
        print("  help                   - Show this help")
        print("  quit                   - Exit interactive mode")
        print("\nMemory sources are now displayed as:")
        print("  📄 filename.md → Section Title  (Markdown files)")
        print("  🔄 repo-name → file1.py ↔ file2.py  (Git co-change patterns)")
        print("  🔥 repo-name → hotfile.py  (Git maintenance hotspots)")
        print("  💡 repo-name → solution  (Git solution patterns)")


def create_cli_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI commands."""
    parser = argparse.ArgumentParser(
        prog="cognitive-cli",
        description="Cognitive Memory System CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cognitive-cli store "Had trouble debugging the authentication flow"
  cognitive-cli retrieve "authentication issues"
  cognitive-cli status --detailed
  cognitive-cli interactive
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Store command
    store_parser = subparsers.add_parser("store", help="Store a new experience")
    store_parser.add_argument("text", help="Experience text to store")
    store_parser.add_argument("--context", help="Context as JSON string")
    store_parser.add_argument(
        "--level",
        type=int,
        choices=[0, 1, 2],
        help="Hierarchy level (0=concepts, 1=contexts, 2=episodes)",
    )

    # Retrieve command
    retrieve_parser = subparsers.add_parser("retrieve", help="Retrieve memories")
    retrieve_parser.add_argument("query", help="Query text")
    retrieve_parser.add_argument(
        "--types",
        nargs="+",
        choices=["core", "peripheral", "bridge"],
        help="Memory types to retrieve",
    )
    retrieve_parser.add_argument(
        "--limit", type=int, default=10, help="Maximum results per type"
    )

    # Status command
    status_parser = subparsers.add_parser("status", help="Show system status")
    status_parser.add_argument(
        "--detailed", action="store_true", help="Show detailed statistics"
    )

    # Consolidate command
    consolidate_parser = subparsers.add_parser(
        "consolidate", help="Consolidate memories"
    )
    consolidate_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be consolidated"
    )

    # Load command
    load_parser = subparsers.add_parser(
        "load", help="Load memories from external source"
    )
    load_parser.add_argument("source_path", help="Path to source file")
    load_parser.add_argument(
        "--loader-type",
        choices=["markdown", "git"],
        default="markdown",
        help="Type of loader to use",
    )
    load_parser.add_argument(
        "--dry-run", action="store_true", help="Analyze source without loading memories"
    )
    load_parser.add_argument(
        "--chunk-size", type=int, help="Override maximum tokens per chunk"
    )
    load_parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively find all markdown files in directory",
    )

    # Clear command (placeholder)
    clear_parser = subparsers.add_parser("clear", help="Clear memories")
    clear_parser.add_argument(
        "--type",
        choices=["episodic", "semantic", "all"],
        default="all",
        help="Type of memories to clear",
    )
    clear_parser.add_argument("--confirm", action="store_true", help="Confirm deletion")

    # Git commands
    git_parser = subparsers.add_parser("git-load", help="Load git repository patterns")
    git_parser.add_argument("repo_path", help="Path to git repository")
    git_parser.add_argument(
        "--time-window", default="3m", help="Analysis time window (e.g., 3m, 6m, 1y)"
    )
    git_parser.add_argument(
        "--dry-run", action="store_true", help="Show patterns without storing"
    )
    git_parser.add_argument(
        "--refresh", action="store_true", help="Update existing patterns"
    )

    git_status_parser = subparsers.add_parser(
        "git-status", help="Show git analysis status"
    )
    git_status_parser.add_argument(
        "repo_path", nargs="?", help="Repository path (optional)"
    )

    git_patterns_parser = subparsers.add_parser(
        "git-patterns", help="Search git patterns"
    )
    git_patterns_parser.add_argument("query", help="Search query for patterns")
    git_patterns_parser.add_argument(
        "--type", choices=["cochange", "hotspot", "solution"], help="Pattern type"
    )
    git_patterns_parser.add_argument(
        "--limit", type=int, default=10, help="Maximum results to show"
    )

    # Interactive command
    interactive_parser = subparsers.add_parser(
        "interactive", help="Enter interactive mode"
    )
    interactive_parser.add_argument("--prompt", help="Custom prompt string")

    return parser


def main() -> int:
    """Main CLI entry point."""
    parser = create_cli_parser()

    # Add global options
    parser.add_argument("--config", help="Path to configuration file (.env format)")
    parser.add_argument(
        "--profile",
        choices=["default", "development", "production", "test"],
        default="default",
        help="System initialization profile",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Initialize cognitive system using factory
    try:
        print("🧠 Initializing cognitive memory system...")

        if args.config:
            cognitive_system = initialize_with_config(args.config)
        else:
            cognitive_system = initialize_system(args.profile)

        print("✓ System initialized successfully")

        # Create CLI instance
        cli = CognitiveCLI(cognitive_system)

        # Dispatch commands
        exit_code = 0

        try:
            if args.command == "store":
                success = cli.store_experience(
                    text=args.text, context_json=getattr(args, "context", None)
                )
                if hasattr(args, "level") and args.level is not None:
                    # Add hierarchy level to context
                    context = {"hierarchy_level": args.level}
                    success = cli.store_experience(args.text, context)
                exit_code = 0 if success else 1

            elif args.command == "retrieve":
                result = cli.retrieve_memories(
                    query=args.query,
                    types=getattr(args, "types", None),
                    limit=getattr(args, "limit", 10),
                )
                success = bool(result)
                exit_code = 0 if success else 1

            elif args.command == "status":
                result = cli.show_status(detailed=getattr(args, "detailed", False))
                success = bool(result)
                exit_code = 0 if success else 1

            elif args.command == "consolidate":
                success = cli.consolidate_memories(
                    dry_run=getattr(args, "dry_run", False)
                )
                exit_code = 0 if success else 1

            elif args.command == "load":
                kwargs = {}
                if hasattr(args, "chunk_size") and args.chunk_size:
                    kwargs["max_tokens_per_chunk"] = args.chunk_size

                success = cli.load_memories(
                    source_path=args.source_path,
                    loader_type=getattr(args, "loader_type", "markdown"),
                    dry_run=getattr(args, "dry_run", False),
                    recursive=getattr(args, "recursive", False),
                    **kwargs,
                )
                exit_code = 0 if success else 1

            elif args.command == "clear":
                success = cli.clear_memories(
                    memory_type=getattr(args, "type", "all"),
                    confirm=getattr(args, "confirm", False),
                )
                exit_code = 0 if success else 1

            elif args.command == "git-load":
                kwargs = {}
                if hasattr(args, "time_window") and args.time_window:
                    kwargs["time_window"] = args.time_window

                success = cli.load_git_patterns(
                    repo_path=args.repo_path,
                    dry_run=getattr(args, "dry_run", False),
                    refresh=getattr(args, "refresh", False),
                    **kwargs,
                )
                exit_code = 0 if success else 1

            elif args.command == "git-status":
                success = cli.show_git_status(
                    repo_path=getattr(args, "repo_path", None)
                )
                exit_code = 0 if success else 1

            elif args.command == "git-patterns":
                success = cli.search_git_patterns(
                    query=args.query,
                    pattern_type=getattr(args, "type", None),
                    limit=getattr(args, "limit", 10),
                )
                exit_code = 0 if success else 1

            elif args.command == "interactive":
                cli.interactive_mode_loop()
                exit_code = 0

            else:
                print(f"Unknown command: {args.command}")
                exit_code = 1

        finally:
            # Perform graceful shutdown
            print("🔄 Shutting down system...")
            if graceful_shutdown(cognitive_system):
                print("✓ System shutdown completed")
            else:
                print("⚠️ System shutdown completed with warnings")

        return exit_code

    except InitializationError as e:
        print(f"✗ Failed to initialize cognitive memory system: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        return 130
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
