"""Project memory management commands."""

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


def project_init(
    project_root: str | None = typer.Option(
        None, help="Project root directory (defaults to current directory)"
    ),
    auto_start_qdrant: bool = typer.Option(
        True, help="Automatically start Qdrant if not running"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """Initialize project-specific collections and setup."""
    try:
        from cognitive_memory.core.config import (
            QdrantConfig,
            SystemConfig,
            get_project_id,
        )
        from cognitive_memory.storage.qdrant_storage import create_hierarchical_storage
        from heimdall.cognitive_system.service_manager import QdrantManager

        # Determine project root and generate project ID
        if project_root:
            project_path = Path(project_root).resolve()
        else:
            project_path = Path.cwd()

        project_id = get_project_id(project_path)

        console.print(f"🚀 Initializing project: {project_id}", style="bold blue")
        console.print(f"📁 Project root: {project_path}")

        # Check Qdrant status
        manager = QdrantManager()
        status = manager.get_status()

        if status.status.value != "running":
            if auto_start_qdrant:
                console.print(
                    "🔄 Qdrant not running, starting automatically...",
                    style="bold yellow",
                )

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("Starting Qdrant service...", total=None)

                    success = manager.start(wait_timeout=30)
                    if not success:
                        progress.update(task, description="❌ Failed to start Qdrant")
                        console.print(
                            "❌ Failed to start Qdrant automatically", style="bold red"
                        )
                        raise typer.Exit(1)

                    progress.update(task, description="✅ Qdrant started successfully")
            else:
                console.print(
                    "❌ Qdrant is not running. Please start it with: heimdall qdrant start",
                    style="bold red",
                )
                raise typer.Exit(1)

        # Load system configuration to get embedding dimension
        config = SystemConfig.from_env()

        # Create Qdrant client configuration
        qdrant_config = QdrantConfig.from_env()
        from urllib.parse import urlparse

        parsed_url = urlparse(qdrant_config.url)
        host = parsed_url.hostname or "localhost"
        port = parsed_url.port or 6333

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Initializing project collections...", total=None)

            # Create hierarchical storage to initialize collections
            _ = create_hierarchical_storage(
                vector_size=config.embedding.embedding_dimension,
                project_id=project_id,
                host=host,
                port=port,
                prefer_grpc=qdrant_config.prefer_grpc,
            )

            progress.update(task, description="✅ Project collections initialized")

        # Check and download spaCy model if needed
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Checking spaCy model...", total=None)

            try:
                import spacy

                # Try to load the model
                spacy.load("en_core_web_md")
                progress.update(task, description="✅ spaCy model already available")
            except OSError:
                # Model not found, download it
                progress.update(
                    task, description="📥 Downloading spaCy model (en_core_web_md)..."
                )

                import subprocess
                import sys

                result = subprocess.run(
                    [sys.executable, "-m", "spacy", "download", "en_core_web_md"],
                    capture_output=True,
                    text=True,
                )

                if result.returncode == 0:
                    progress.update(
                        task, description="✅ spaCy model downloaded successfully"
                    )
                else:
                    progress.update(
                        task, description="❌ Failed to download spaCy model"
                    )
                    console.print(
                        f"❌ Failed to download spaCy model. Error: {result.stderr}",
                        style="bold red",
                    )
                    console.print(
                        "Please run manually: python -m spacy download en_core_web_md",
                        style="bold yellow",
                    )

        # Create project configuration file
        heimdall_dir = project_path / ".heimdall"
        heimdall_dir.mkdir(exist_ok=True)

        config_file = heimdall_dir / "config.yaml"
        if not config_file.exists():
            import yaml

            project_config = {
                "project_id": project_id,
                "qdrant_url": qdrant_config.url,
                "monitoring": {
                    "target_path": "./docs",
                    "interval_seconds": 5.0,
                    "ignore_patterns": [
                        ".git",
                        "node_modules",
                        "__pycache__",
                        ".pytest_cache",
                    ],
                },
                "database": {"path": "./.heimdall/cognitive_memory.db"},
            }

            config_file.write_text(yaml.dump(project_config, default_flow_style=False))
            console.print(f"📝 Created configuration: {config_file}")

        if json_output:
            output_data = {
                "project_id": project_id,
                "project_root": str(project_path),
                "qdrant_url": qdrant_config.url,
                "config_file": str(config_file),
                "status": "initialized",
            }
            console.print(json.dumps(output_data, indent=2))
        else:
            console.print("✅ Project initialization complete!", style="bold green")

            # Show project info table
            info_table = Table(title="Project Information")
            info_table.add_column("Property", style="cyan")
            info_table.add_column("Value", style="white")
            info_table.add_row("Project ID", project_id)
            info_table.add_row("Project Root", str(project_path))
            info_table.add_row("Qdrant URL", qdrant_config.url)
            info_table.add_row("Config File", str(config_file))
            info_table.add_row(
                "Collections",
                f"{project_id}_concepts, {project_id}_contexts, {project_id}_episodes",
            )
            console.print(info_table)

    except Exception as e:
        console.print(f"❌ Error initializing project: {e}", style="bold red")
        raise typer.Exit(1) from e


def project_list(
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
    show_collections: bool = typer.Option(
        False, "--collections", help="Show collection details"
    ),
) -> None:
    """List all projects in shared Qdrant instance."""
    try:
        from qdrant_client import QdrantClient

        from cognitive_memory.core.config import QdrantConfig
        from heimdall.cognitive_system.service_manager import QdrantManager

        # Check Qdrant status
        manager = QdrantManager()
        status = manager.get_status()

        if status.status.value != "running":
            console.print(
                "❌ Qdrant is not running. Please start it with: heimdall qdrant start",
                style="bold red",
            )
            raise typer.Exit(1)

        # Create Qdrant client
        qdrant_config = QdrantConfig.from_env()
        from urllib.parse import urlparse

        parsed_url = urlparse(qdrant_config.url)
        host = parsed_url.hostname or "localhost"
        port = parsed_url.port or 6333

        client = QdrantClient(
            host=host, port=port, prefer_grpc=qdrant_config.prefer_grpc
        )

        # Get all collections and extract project IDs
        try:
            all_collections = client.get_collections().collections
            projects: dict[str, list[dict[str, Any]]] = {}

            for collection in all_collections:
                # Extract project ID from collection name (format: {project_id}_{level})
                if "_" in collection.name:
                    parts = collection.name.rsplit("_", 1)
                    if len(parts) == 2 and parts[1] in [
                        "concepts",
                        "contexts",
                        "episodes",
                    ]:
                        project_id = parts[0]
                        if project_id not in projects:
                            projects[project_id] = []

                        # Get detailed collection info for stats
                        try:
                            collection_info = client.get_collection(collection.name)
                            points_count = collection_info.points_count
                            indexed_vectors_count = (
                                collection_info.indexed_vectors_count
                            )
                        except Exception:
                            points_count = 0
                            indexed_vectors_count = 0

                        projects[project_id].append(
                            {
                                "name": collection.name,
                                "level": parts[1],
                                "vectors_count": points_count,  # Use points_count as vectors_count
                                "points_count": points_count,
                                "indexed_vectors_count": indexed_vectors_count,
                            }
                        )

            if json_output:
                result = {
                    "total_projects": len(projects),
                    "projects": projects,
                    "qdrant_url": qdrant_config.url,
                }
                console.print(json.dumps(result, indent=2))
            else:
                if not projects:
                    console.print(
                        "📭 No projects found in shared Qdrant instance",
                        style="bold yellow",
                    )
                else:
                    console.print(
                        f"📊 Found {len(projects)} project(s) in shared Qdrant:",
                        style="bold blue",
                    )

                    projects_table = Table(title="Projects in Shared Qdrant")
                    projects_table.add_column("Project ID", style="cyan")
                    projects_table.add_column("Collections", style="green")
                    if show_collections:
                        projects_table.add_column("Total Vectors", style="white")
                        projects_table.add_column("Total Points", style="white")

                    for project_id, collections in projects.items():
                        collection_names = ", ".join([c["name"] for c in collections])
                        if show_collections:
                            total_vectors = sum(c["vectors_count"] for c in collections)
                            total_points = sum(c["points_count"] for c in collections)
                            projects_table.add_row(
                                project_id,
                                collection_names,
                                str(total_vectors),
                                str(total_points),
                            )
                        else:
                            projects_table.add_row(project_id, collection_names)

                    console.print(projects_table)

        except Exception as e:
            console.print(
                f"❌ Error querying Qdrant collections: {e}", style="bold red"
            )
            raise typer.Exit(1) from e

    except Exception as e:
        console.print(f"❌ Error listing projects: {e}", style="bold red")
        raise typer.Exit(1) from e


def project_clean(
    project_id: str = typer.Argument(
        ..., help="Project ID to clean (use 'list' command to see available projects)"
    ),
    confirm: bool = typer.Option(False, "--yes", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be deleted without actually deleting"
    ),
) -> None:
    """Remove project collections from shared Qdrant instance."""
    try:
        from qdrant_client import QdrantClient

        from cognitive_memory.core.config import QdrantConfig
        from heimdall.cognitive_system.service_manager import QdrantManager

        # Check Qdrant status
        manager = QdrantManager()
        status = manager.get_status()

        if status.status.value != "running":
            console.print(
                "❌ Qdrant is not running. Please start it with: heimdall qdrant start",
                style="bold red",
            )
            raise typer.Exit(1)

        # Create Qdrant client
        qdrant_config = QdrantConfig.from_env()
        from urllib.parse import urlparse

        parsed_url = urlparse(qdrant_config.url)
        host = parsed_url.hostname or "localhost"
        port = parsed_url.port or 6333

        client = QdrantClient(
            host=host, port=port, prefer_grpc=qdrant_config.prefer_grpc
        )

        # Find collections for this project
        try:
            all_collections = client.get_collections().collections
            project_collections = [
                c
                for c in all_collections
                if c.name.startswith(f"{project_id}_")
                and c.name.endswith(("_concepts", "_contexts", "_episodes"))
            ]

            if not project_collections:
                console.print(
                    f"⚠️ No collections found for project: {project_id}",
                    style="bold yellow",
                )
                console.print("Use 'heimdall project list' to see available projects")
                raise typer.Exit(1)

            collection_names = [c.name for c in project_collections]

            # Get detailed collection info to calculate total vectors
            total_vectors = 0
            for collection in project_collections:
                try:
                    collection_info = client.get_collection(collection.name)
                    total_vectors += collection_info.points_count
                except Exception:
                    pass  # Skip collections that can't be queried

            if dry_run:
                console.print(
                    f"🔍 DRY RUN: Would delete {len(collection_names)} collection(s) for project '{project_id}':",
                    style="bold blue",
                )
                for name in collection_names:
                    console.print(f"  - {name}")
                console.print(f"Total vectors that would be deleted: {total_vectors}")
                return

            # Show what will be deleted
            console.print(
                f"🗑️ Will delete {len(collection_names)} collection(s) for project '{project_id}':",
                style="bold yellow",
            )
            for name in collection_names:
                console.print(f"  - {name}")
            console.print(f"Total vectors to delete: {total_vectors}")

            # Confirmation
            if not confirm:
                confirm_delete = typer.confirm(
                    "⚠️ This action cannot be undone. Continue?"
                )
                if not confirm_delete:
                    console.print("❌ Operation cancelled", style="bold yellow")
                    raise typer.Exit(0)

            # Delete collections
            deleted_collections = []
            failed_collections = []

            for collection in project_collections:
                try:
                    client.delete_collection(collection.name)
                    deleted_collections.append(collection.name)
                    console.print(f"✅ Deleted: {collection.name}")
                except Exception as e:
                    failed_collections.append(
                        {"name": collection.name, "error": str(e)}
                    )
                    console.print(f"❌ Failed to delete {collection.name}: {e}")

            if json_output:
                result = {
                    "project_id": project_id,
                    "deleted_collections": deleted_collections,
                    "failed_collections": failed_collections,
                    "total_deleted": len(deleted_collections),
                    "total_failed": len(failed_collections),
                }
                console.print(json.dumps(result, indent=2))
            else:
                if deleted_collections:
                    console.print(
                        f"✅ Successfully deleted {len(deleted_collections)} collection(s)",
                        style="bold green",
                    )
                if failed_collections:
                    console.print(
                        f"❌ Failed to delete {len(failed_collections)} collection(s)",
                        style="bold red",
                    )
                    for failed in failed_collections:
                        console.print(f"  - {failed['name']}: {failed['error']}")

                if failed_collections:
                    raise typer.Exit(1)

        except Exception as e:
            console.print(
                f"❌ Error cleaning project collections: {e}", style="bold red"
            )
            raise typer.Exit(1) from e

    except Exception as e:
        console.print(f"❌ Error cleaning project: {e}", style="bold red")
        raise typer.Exit(1) from e
