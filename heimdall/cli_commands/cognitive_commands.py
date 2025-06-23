"""Cognitive memory commands: store, recall, load, git-load, status."""

import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cognitive_memory.main import (
    InitializationError,
    graceful_shutdown,
    initialize_system,
    initialize_with_config,
)
from heimdall.operations import CognitiveOperations

console = Console()


def store_experience(
    text: str = typer.Argument(..., help="Experience text to store"),
    context_json: str | None = typer.Option(
        None, "--context", help="Context as JSON string"
    ),
    config: str | None = typer.Option(None, help="Path to configuration file"),
) -> None:
    """Store an experience in cognitive memory."""
    try:
        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Create operations instance and store experience
        ops = CognitiveOperations(cognitive_system)
        result = ops.store_experience(text, context_json=context_json)

        if result["success"]:
            console.print(
                f"✅ Stored: L{result['hierarchy_level']}, {result['memory_type']}",
                style="bold green",
            )
            console.print(f"📝 Memory ID: {result['memory_id']}")
        else:
            console.print(
                f"❌ Failed to store experience: {result['error']}", style="bold red"
            )
            raise typer.Exit(1)

        # Cleanup
        graceful_shutdown(cognitive_system)

    except InitializationError as e:
        console.print(f"❌ Failed to initialize system: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error storing experience: {e}", style="bold red")
        raise typer.Exit(1) from e


def recall_memories(
    query: str = typer.Argument(..., help="Query to search for in memories"),
    types: list[str] = typer.Option(
        None, "--types", help="Memory types to retrieve (core, peripheral, bridge)"
    ),
    limit: int = typer.Option(10, "--limit", help="Maximum results per type"),
    config: str | None = typer.Option(None, help="Path to configuration file"),
) -> None:
    """Retrieve memories matching a query."""
    try:
        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Create operations instance and retrieve memories
        ops = CognitiveOperations(cognitive_system)
        results = ops.retrieve_memories(query, types, limit)

        if not results["success"]:
            console.print(
                f"❌ Failed to retrieve memories: {results['error']}", style="bold red"
            )
            raise typer.Exit(1)

        # Display results with terminal-specific formatting
        console.print(f"🔍 Query: [bold cyan]{query}[/bold cyan]")
        console.print(f"📊 Total results: {results['total_count']}")

        for memory_type in ["core", "peripheral", "bridge"]:
            memories = results[memory_type]
            if memories:
                console.print(
                    f"\n[bold]{memory_type.upper()}[/bold] ({len(memories)} results)"
                )

                for i, memory in enumerate(memories, 1):
                    # Handle different memory object types
                    if hasattr(memory, "content"):
                        content = memory.content
                        score = getattr(memory, "similarity_score", "N/A")
                    elif isinstance(memory, dict):
                        content = memory.get("content", str(memory))
                        score = memory.get("similarity_score", "N/A")
                    else:
                        content = str(memory)
                        score = "N/A"

                    # Truncate long content for display
                    display_content = (
                        content[:200] + "..." if len(content) > 200 else content
                    )
                    console.print(f"  {i}. [dim]Score: {score}[/dim]")
                    console.print(f"     {display_content}")

        if results["total_count"] == 0:
            console.print(
                "📭 No memories found matching your query", style="bold yellow"
            )

        # Cleanup
        graceful_shutdown(cognitive_system)

    except InitializationError as e:
        console.print(f"❌ Failed to initialize system: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error retrieving memories: {e}", style="bold red")
        raise typer.Exit(1) from e


def load_memories(
    source_path: str = typer.Argument(
        ..., help="Path to the source file or directory to load"
    ),
    loader_type: str = typer.Option(
        "markdown", help="Type of loader to use (markdown, git)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be loaded without loading"
    ),
    recursive: bool = typer.Option(
        False, "--recursive", help="Recursively process directories"
    ),
    config: str | None = typer.Option(None, help="Path to configuration file"),
) -> None:
    """Load memories from external source file or directory."""
    try:
        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Create operations instance and load memories
        ops = CognitiveOperations(cognitive_system)
        result = ops.load_memories(
            source_path=source_path,
            loader_type=loader_type,
            dry_run=dry_run,
            recursive=recursive,
        )

        if not result["success"]:
            console.print(
                f"❌ Failed to load memories: {result['error']}", style="bold red"
            )
            raise typer.Exit(1)

        # Display results with terminal-specific formatting
        if dry_run:
            console.print(
                "🔍 DRY RUN - No memories were actually loaded", style="bold blue"
            )
        else:
            console.print(
                "✅ Memory loading completed successfully", style="bold green"
            )

        # Results table
        results_table = Table(title="Loading Results")
        results_table.add_column("Metric", style="cyan")
        results_table.add_column("Value", style="white")

        results_table.add_row("Memories Loaded", str(result["memories_loaded"]))
        results_table.add_row("Connections Created", str(result["connections_created"]))
        results_table.add_row("Processing Time", f"{result['processing_time']:.2f}s")
        results_table.add_row("Memories Failed", str(result["memories_failed"]))
        results_table.add_row("Connections Failed", str(result["connections_failed"]))

        if result["files_processed"]:
            results_table.add_row(
                "Files Processed", str(len(result["files_processed"]))
            )

        console.print(results_table)

        # Hierarchy distribution
        if result["hierarchy_distribution"]:
            console.print("\n📊 Memory Hierarchy Distribution:")
            for level, count in result["hierarchy_distribution"].items():
                console.print(f"  L{level}: {count} memories")

        # Cleanup
        graceful_shutdown(cognitive_system)

    except InitializationError as e:
        console.print(f"❌ Failed to initialize system: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error loading memories: {e}", style="bold red")
        raise typer.Exit(1) from e


def load_git_patterns(
    repo_path: str = typer.Argument(".", help="Path to git repository"),
    max_commits: int = typer.Option(1000, help="Maximum commits to process"),
    force_full_load: bool = typer.Option(
        False, "--force-full", help="Force full history load"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be loaded without loading"
    ),
    config: str | None = typer.Option(None, help="Path to configuration file"),
) -> None:
    """Load git commit patterns into cognitive memory."""
    try:
        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Create operations instance and load git patterns
        ops = CognitiveOperations(cognitive_system)
        result = ops.load_git_patterns(
            repo_path=repo_path,
            max_commits=max_commits,
            force_full_load=force_full_load,
            dry_run=dry_run,
        )

        if not result["success"]:
            console.print(
                f"❌ Failed to load git patterns: {result['error']}", style="bold red"
            )
            raise typer.Exit(1)

        # Display results with terminal-specific formatting
        if dry_run:
            console.print(
                "🔍 DRY RUN - No patterns were actually loaded", style="bold blue"
            )
        else:
            console.print(
                "✅ Git pattern loading completed successfully", style="bold green"
            )

        # Results table
        results_table = Table(title="Git Loading Results")
        results_table.add_column("Metric", style="cyan")
        results_table.add_column("Value", style="white")

        results_table.add_row("Patterns Loaded", str(result["patterns_loaded"]))
        results_table.add_row("Commits Processed", str(result["commits_processed"]))
        results_table.add_row("Processing Time", f"{result['processing_time']:.2f}s")

        if "patterns_failed" in result:
            results_table.add_row("Patterns Failed", str(result["patterns_failed"]))

        console.print(results_table)

        # Cleanup
        graceful_shutdown(cognitive_system)

    except InitializationError as e:
        console.print(f"❌ Failed to initialize system: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error loading git patterns: {e}", style="bold red")
        raise typer.Exit(1) from e


def system_status(
    detailed: bool = typer.Option(
        False, "--detailed", help="Show detailed system statistics"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
    config: str | None = typer.Option(None, help="Path to configuration file"),
) -> None:
    """Show cognitive memory system status and statistics."""
    try:
        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Create operations instance and get status
        ops = CognitiveOperations(cognitive_system)
        result = ops.get_system_status(detailed=detailed)

        if not result["success"]:
            console.print(
                f"❌ Failed to get system status: {result['error']}", style="bold red"
            )
            raise typer.Exit(1)

        if json_output:
            console.print(json.dumps(result, indent=2))
        else:
            # Terminal-specific formatting
            console.print("🧠 Cognitive Memory System Status", style="bold blue")

            # Memory counts table
            if result["memory_counts"]:
                memory_table = Table(title="Memory Statistics")
                memory_table.add_column("Type/Level", style="cyan")
                memory_table.add_column("Count", style="white")

                for key, count in result["memory_counts"].items():
                    memory_table.add_row(key.replace("_", " ").title(), str(count))

                console.print(memory_table)

            # Detailed information
            if detailed:
                if result.get("system_config"):
                    config_panel = Panel(
                        json.dumps(result["system_config"], indent=2),
                        title="System Configuration",
                        border_style="blue",
                    )
                    console.print(config_panel)

                if result.get("storage_stats"):
                    storage_panel = Panel(
                        json.dumps(result["storage_stats"], indent=2),
                        title="Storage Statistics",
                        border_style="green",
                    )
                    console.print(storage_panel)

                if result.get("embedding_info"):
                    embedding_panel = Panel(
                        json.dumps(result["embedding_info"], indent=2),
                        title="Embedding Information",
                        border_style="yellow",
                    )
                    console.print(embedding_panel)

        # Cleanup
        graceful_shutdown(cognitive_system)

    except InitializationError as e:
        console.print(f"❌ Failed to initialize system: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error getting system status: {e}", style="bold red")
        raise typer.Exit(1) from e
