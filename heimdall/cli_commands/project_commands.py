"""Project memory management commands."""

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


def _is_git_repository(project_path: Path) -> bool:
    """Check if the project path is within a git repository."""
    return (project_path / ".git").exists()


def _ensure_heimdall_in_gitignore(project_path: Path) -> None:
    """
    Ensure .heimdall/ is added to .gitignore if the project is a git repository.

    Args:
        project_path: Path to the project directory
    """
    # Only create/modify .gitignore if this is a git repository
    if not _is_git_repository(project_path):
        return

    gitignore_path = project_path / ".gitignore"
    heimdall_entry = ".heimdall/"

    try:
        if gitignore_path.exists():
            # Read existing .gitignore
            content = gitignore_path.read_text()
            # Check if .heimdall/ is already in .gitignore
            # Account for variations like .heimdall, .heimdall/, /.heimdall/
            patterns = [".heimdall", ".heimdall/", "/.heimdall", "/.heimdall/"]
            if not any(pattern in content for pattern in patterns):
                # Append to existing .gitignore
                with gitignore_path.open("a") as f:
                    if not content.endswith("\n") and content:
                        f.write("\n")
                    f.write(f"{heimdall_entry}\n")
                console.print(
                    f"📝 Added {heimdall_entry} to existing .gitignore",
                    style="bold green",
                )
            else:
                console.print(f"✅ {heimdall_entry} already in .gitignore", style="dim")
        else:
            # Create new .gitignore
            gitignore_path.write_text(f"{heimdall_entry}\n")
            console.print(
                f"📝 Created .gitignore with {heimdall_entry}", style="bold green"
            )
    except Exception as e:
        console.print(f"⚠️ Could not update .gitignore: {e}", style="bold yellow")
        console.print(
            f"   Please add {heimdall_entry} to .gitignore manually", style="dim"
        )


def project_init(
    project_root: str | None = typer.Option(
        None, help="Project root directory (defaults to current directory)"
    ),
    auto_start_qdrant: bool = typer.Option(
        True, help="Automatically start Qdrant if not running"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
    # Interactive control flags
    non_interactive: bool = typer.Option(
        False, "--non-interactive", help="Skip all prompts, use defaults"
    ),
    # Monitoring control
    auto_monitor: bool = typer.Option(
        False, "--auto-monitor", help="Force enable automatic file monitoring"
    ),
    no_monitor: bool = typer.Option(
        False, "--no-monitor", help="Force disable automatic file monitoring"
    ),
    # Git history control
    load_git_history: bool = typer.Option(
        False, "--load-git-history", help="Force enable git history loading"
    ),
    skip_git_history: bool = typer.Option(
        False, "--skip-git-history", help="Force disable git history loading"
    ),
    # Git hooks control
    setup_git_hooks: bool = typer.Option(
        False, "--setup-git-hooks", help="Force enable git hooks installation"
    ),
    skip_git_hooks: bool = typer.Option(
        False, "--skip-git-hooks", help="Force disable git hooks installation"
    ),
    # MCP integration control
    setup_mcp: bool = typer.Option(
        False, "--setup-mcp", help="Force enable MCP integration setup"
    ),
    skip_mcp: bool = typer.Option(
        False, "--skip-mcp", help="Force disable MCP integration setup"
    ),
) -> None:
    """Initialize project-specific collections and setup."""
    try:
        # Validate flag combinations early
        if auto_monitor and no_monitor:
            console.print(
                "❌ Cannot specify both --auto-monitor and --no-monitor",
                style="bold red",
            )
            raise typer.Exit(1)

        if load_git_history and skip_git_history:
            console.print(
                "❌ Cannot specify both --load-git-history and --skip-git-history",
                style="bold red",
            )
            raise typer.Exit(1)

        if setup_git_hooks and skip_git_hooks:
            console.print(
                "❌ Cannot specify both --setup-git-hooks and --skip-git-hooks",
                style="bold red",
            )
            raise typer.Exit(1)

        if setup_mcp and skip_mcp:
            console.print(
                "❌ Cannot specify both --setup-mcp and --skip-mcp",
                style="bold red",
            )
            raise typer.Exit(1)

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

        # Initialize shared environment and download models if needed
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Initialize shared data directories first
            task = progress.add_task(
                "Setting up shared data directories...", total=None
            )

            try:
                from heimdall.cognitive_system.data_dirs import (
                    initialize_shared_environment,
                )

                initialize_shared_environment()
                progress.update(task, description="✅ Shared data directories ready")
            except Exception as e:
                progress.update(task, description="❌ Failed to setup data directories")
                console.print(
                    f"❌ Failed to setup data directories. Error: {e}",
                    style="bold red",
                )

            # Download SentenceBERT ONNX models
            task = progress.add_task("Checking SentenceBERT models...", total=None)

            try:
                from heimdall.cognitive_system.data_dirs import ensure_models_available

                ensure_models_available()
                progress.update(task, description="✅ SentenceBERT models ready")
            except Exception as e:
                progress.update(
                    task, description="❌ Failed to download SentenceBERT models"
                )
                console.print(
                    f"❌ Failed to download SentenceBERT models. Error: {e}",
                    style="bold red",
                )

            # Check and download spaCy model
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

            # Check and download NLTK data
            task = progress.add_task("Checking NLTK data...", total=None)
            _ensure_nltk_data_available(progress, task)

        # Create project configuration file and directories
        heimdall_dir = project_path / ".heimdall"
        heimdall_dir.mkdir(exist_ok=True)

        # Add .heimdall to .gitignore (only if this is a git repository)
        _ensure_heimdall_in_gitignore(project_path)

        # Create docs directory for monitoring
        docs_dir = heimdall_dir / "docs"
        docs_dir.mkdir(exist_ok=True)

        config_file = heimdall_dir / "config.yaml"
        if not config_file.exists():
            import yaml

            # Use template-based generation
            template_path = (
                Path(__file__).parent.parent.parent
                / "templates"
                / "config.yaml.template"
            )
            if template_path.exists():
                template = template_path.read_text()
                yaml_content = template.replace("${project_id}", project_id)
                yaml_content = yaml_content.replace("${qdrant_url}", qdrant_config.url)
                config_file.write_text(yaml_content)
            else:
                # Fallback to direct YAML generation
                project_config = {
                    "project_id": project_id,
                    "qdrant_url": qdrant_config.url,
                    "logging": {
                        "level": "warn",
                    },
                    "monitoring": {
                        "enabled": True,
                        "target_path": "./.heimdall/docs",
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
                config_file.write_text(
                    yaml.dump(project_config, default_flow_style=False)
                )

            console.print(f"📝 Created configuration: {config_file}")
            console.print(f"📁 Created monitoring directory: {docs_dir}")

            # Create a README in the docs directory
            readme_content = """# Heimdall Documentation Directory

This directory is monitored by Heimdall's file monitoring service for automatic memory updates.

## Usage

- Place documentation files directly in this directory
- Or create symlinks to your actual documentation:
  ```bash
  ln -s ../docs ./.heimdall/docs/project-docs
  ln -s ../README.md ./.heimdall/docs/README.md
  ```

## Supported Formats

- Markdown (.md, .markdown, .mdown, .mkd)
- Text files (.txt)
- More formats coming soon

## Monitoring

Files in this directory are automatically:
- Parsed and stored as cognitive memories
- Updated when modified
- Indexed for semantic search
- Connected to related concepts
"""
            readme_file = docs_dir / "README.md"
            if not readme_file.exists():
                readme_file.write_text(readme_content)

        # Determine user choices for optional features
        user_wants_monitoring = _determine_monitoring_choice(
            auto_monitor, no_monitor, non_interactive
        )
        user_wants_git_history = _determine_git_history_choice(
            load_git_history, skip_git_history, non_interactive, project_path
        )
        user_wants_git_hooks = _determine_git_hooks_choice(
            setup_git_hooks, skip_git_hooks, non_interactive, project_path
        )
        user_wants_mcp = _determine_mcp_setup_choice(
            setup_mcp, skip_mcp, non_interactive
        )

        if json_output:
            # Execute user-selected features for JSON mode too
            git_history_loaded = False
            git_hooks_installed = False
            mcp_configured_platforms = []

            if user_wants_git_history:
                git_history_loaded = _execute_git_history_loading(project_path)

            if user_wants_git_hooks:
                git_hooks_installed = _execute_git_hooks_installation(project_path)

            if user_wants_monitoring:
                _execute_monitoring_service_startup(project_path)

            if user_wants_mcp:
                mcp_configured_platforms = _execute_mcp_setup()

            output_data = {
                "project_id": project_id,
                "project_root": str(project_path),
                "qdrant_url": qdrant_config.url,
                "config_file": str(config_file),
                "status": "initialized",
                "monitoring_enabled": user_wants_monitoring,
                "git_history_loaded": git_history_loaded,
                "git_hooks_installed": git_hooks_installed,
                "mcp_configured_platforms": mcp_configured_platforms,
            }
            console.print(json.dumps(output_data, indent=2))
        else:
            # Execute user-selected features
            git_history_loaded = False
            git_hooks_installed = False
            mcp_configured_platforms = []

            # Load git history if requested
            if user_wants_git_history:
                git_history_loaded = _execute_git_history_loading(project_path)

            # Install git hooks if requested
            if user_wants_git_hooks:
                git_hooks_installed = _execute_git_hooks_installation(project_path)

            # Start monitoring service if requested
            if user_wants_monitoring:
                _execute_monitoring_service_startup(project_path)

            # Setup MCP integration if requested
            if user_wants_mcp:
                mcp_configured_platforms = _execute_mcp_setup()

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

            # Add MCP platforms if any were configured
            if mcp_configured_platforms:
                info_table.add_row("MCP Platforms", ", ".join(mcp_configured_platforms))

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
    confirm: bool = typer.Option(False, "--yes", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be deleted without actually deleting"
    ),
    project_root: str | None = typer.Option(
        None, help="Project root directory (defaults to current directory)"
    ),
) -> None:
    """Remove project collections and setup from current directory."""
    try:
        from qdrant_client import QdrantClient

        from cognitive_memory.core.config import QdrantConfig, get_project_id
        from heimdall.cognitive_system.service_manager import QdrantManager

        # Determine project root and generate project ID
        if project_root:
            project_path = Path(project_root).resolve()
        else:
            project_path = Path.cwd()

        project_id = get_project_id(project_path)

        console.print(f"🗑️ Cleaning project: {project_id}")
        console.print(f"📁 Project root: {project_path}")

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
                    total_vectors += collection_info.points_count or 0
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

            # Check for .heimdall directory and git hooks after successful collection deletion
            heimdall_dir_removed = False
            heimdall_dir_error = None
            git_hooks_removed = False
            git_hooks_error = None

            heimdall_dir = project_path / ".heimdall"

            if (
                deleted_collections
            ):  # Only clean up if we successfully deleted some collections
                # Remove git hooks if they exist
                if (project_path / ".git").exists():
                    try:
                        from heimdall.cli_commands.git_hook_commands import (
                            uninstall_hook,
                        )

                        if not confirm:  # If --yes wasn't used, ask for confirmation
                            console.print(f"\n🪝 Found git repository: {project_path}")
                            remove_hooks = typer.confirm(
                                "Do you want to remove Heimdall git hooks as well?"
                            )
                        else:
                            # If --yes was used, also remove git hooks
                            remove_hooks = True

                        if remove_hooks:
                            git_hooks_removed = uninstall_hook(
                                project_path, dry_run=False
                            )
                            if git_hooks_removed:
                                console.print("✅ Removed Heimdall git hooks")
                    except Exception as e:
                        git_hooks_error = str(e)
                        console.print(
                            f"❌ Failed to remove git hooks: {e}",
                            style="bold red",
                        )

                # Remove .heimdall directory
                if heimdall_dir.exists() and heimdall_dir.is_dir():
                    if not confirm:  # If --yes wasn't used, ask for confirmation
                        console.print(f"\n📁 Found .heimdall directory: {heimdall_dir}")
                        remove_heimdall = typer.confirm(
                            "Do you want to remove the .heimdall directory as well?"
                        )
                    else:
                        # If --yes was used, also remove .heimdall directory
                        remove_heimdall = True

                    if remove_heimdall:
                        try:
                            import shutil

                            shutil.rmtree(heimdall_dir)
                            heimdall_dir_removed = True
                            console.print(
                                f"✅ Removed .heimdall directory: {heimdall_dir}"
                            )
                        except Exception as e:
                            heimdall_dir_error = str(e)
                            console.print(
                                f"❌ Failed to remove .heimdall directory: {e}",
                                style="bold red",
                            )

            if json_output:
                result = {
                    "project_id": project_id,
                    "deleted_collections": deleted_collections,
                    "failed_collections": failed_collections,
                    "total_deleted": len(deleted_collections),
                    "total_failed": len(failed_collections),
                    "heimdall_dir_removed": heimdall_dir_removed,
                    "heimdall_dir_error": heimdall_dir_error,
                    "git_hooks_removed": git_hooks_removed,
                    "git_hooks_error": git_hooks_error,
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


def _determine_monitoring_choice(
    auto_monitor: bool, no_monitor: bool, non_interactive: bool
) -> bool:
    """
    Determine user's choice for monitoring service.

    Args:
        auto_monitor: Force enable monitoring
        no_monitor: Force disable monitoring
        non_interactive: Skip prompts, use defaults

    Returns:
        True if user wants monitoring enabled
    """
    # Use explicit flags if provided
    if auto_monitor:
        return True
    if no_monitor:
        return False

    # Use defaults for non-interactive mode
    if non_interactive:
        return True  # Default: enable monitoring

    # Interactive prompt
    console.print("", end="")  # Empty line for spacing
    return bool(
        typer.confirm(
            "🔍 Start automatic file monitoring for documentation changes?",
            default=True,
        )
    )


def _determine_git_history_choice(
    load_git_history: bool,
    skip_git_history: bool,
    non_interactive: bool,
    project_path: Path,
) -> bool:
    """
    Determine user's choice for git history loading.

    Args:
        load_git_history: Force enable git history loading
        skip_git_history: Force disable git history loading
        non_interactive: Skip prompts, use defaults
        project_path: Project path to check for git repository

    Returns:
        True if user wants git history loaded
    """
    # Check if this is a git repository
    if not (project_path / ".git").exists():
        if load_git_history:
            console.print(
                "⚠️ --load-git-history specified but this is not a git repository",
                style="bold yellow",
            )
        return False  # Not a git repo, can't load history

    # Use explicit flags if provided
    if load_git_history:
        return True
    if skip_git_history:
        return False

    # Use defaults for non-interactive mode
    if non_interactive:
        return False  # Default: skip git history (can be slow)

    # Interactive prompt
    return bool(
        typer.confirm(
            "📚 Parse existing git history into memory? (This may take time for large repositories)",
            default=False,
        )
    )


def _determine_git_hooks_choice(
    setup_git_hooks: bool,
    skip_git_hooks: bool,
    non_interactive: bool,
    project_path: Path,
) -> bool:
    """
    Determine user's choice for git hooks installation.

    Args:
        setup_git_hooks: Force enable git hooks setup
        skip_git_hooks: Force disable git hooks setup
        non_interactive: Skip prompts, use defaults
        project_path: Project path to check for git repository

    Returns:
        True if user wants git hooks installed
    """
    # Check if this is a git repository
    if not (project_path / ".git").exists():
        if setup_git_hooks:
            console.print(
                "⚠️ --setup-git-hooks specified but this is not a git repository",
                style="bold yellow",
            )
        return False  # Not a git repo, can't install hooks

    # Use explicit flags if provided
    if setup_git_hooks:
        return True
    if skip_git_hooks:
        return False

    # Use defaults for non-interactive mode
    if non_interactive:
        return False  # Default: skip git hooks (user can set up manually)

    # Interactive prompt
    return bool(
        typer.confirm(
            "🪝 Setup git hooks for automatic commit processing?", default=False
        )
    )


def _execute_git_history_loading(project_path: Path) -> bool:
    """
    Execute git history loading using the operations layer.

    Args:
        project_path: Path to the project directory

    Returns:
        True if git history loading succeeded
    """
    try:
        console.print("📚 Loading git history into memory...", style="bold blue")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Processing git commits...", total=None)

            # Import and use the operations layer
            from cognitive_memory.main import initialize_system
            from heimdall.operations import CognitiveOperations

            # Initialize cognitive system and operations
            cognitive_system = initialize_system()
            operations = CognitiveOperations(cognitive_system)

            # Load git patterns (full history)
            result = operations.load_git_patterns(
                repo_path=str(project_path),
                dry_run=False,
                max_commits=None,  # Load full history
            )

            success = result.get("success", False)
            memories_loaded = result.get("memories_loaded", 0)

            if success:
                memory_word = "memory" if memories_loaded == 1 else "memories"
                progress.update(
                    task,
                    description=f"✅ Loaded {memories_loaded} {memory_word} from git history",
                )
                console.print(
                    f"✅ Git history loaded: {memories_loaded} {memory_word}",
                    style="bold green",
                )
                return True
            else:
                progress.update(task, description="❌ Failed to load git history")
                console.print("❌ Failed to load git history", style="bold red")
                return False

    except Exception as e:
        console.print(f"❌ Error loading git history: {e}", style="bold red")
        return False


def _execute_git_hooks_installation(project_path: Path) -> bool:
    """
    Execute git hooks installation using the existing git hook commands.

    Args:
        project_path: Path to the project directory

    Returns:
        True if git hooks installation succeeded
    """
    try:
        console.print("🪝 Installing git hooks...", style="bold blue")

        # Import git hook installation function
        from heimdall.cli_commands.git_hook_commands import install_hook

        # Install hooks with force=False (preserve existing hooks via chaining)
        success = install_hook(project_path, force=False, dry_run=False)

        if success:
            console.print("✅ Git hooks installed successfully", style="bold green")
            console.print(
                "   Commits will now be automatically processed for memory storage",
                style="dim",
            )
        else:
            console.print("❌ Failed to install git hooks", style="bold red")

        return success

    except Exception as e:
        console.print(f"❌ Error installing git hooks: {e}", style="bold red")
        return False


def _execute_monitoring_service_startup(project_path: Path) -> None:
    """
    Execute monitoring service startup (same logic as before).

    Args:
        project_path: Path to the project directory
    """
    try:
        from cognitive_memory.core.config import CognitiveConfig

        # Check if monitoring is enabled in core config
        cognitive_config = CognitiveConfig.from_env()

        if cognitive_config.monitoring_enabled:
            console.print("🔍 Starting monitoring service...", style="bold blue")
            import subprocess
            import sys

            # Start monitoring in a separate process
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "heimdall.cli",
                        "monitor",
                        "start",
                        "--project-root",
                        str(project_path),
                    ],
                    cwd=str(project_path),
                    timeout=5,
                    capture_output=True,
                    text=True,
                )

                if result.returncode == 0:
                    console.print(
                        "✅ Monitoring service started in daemon mode",
                        style="bold green",
                    )
                else:
                    # Clean stderr output from color codes and format nicely
                    import re

                    clean_stderr = re.sub(r"\x1b\[[0-9;]*m", "", result.stderr.strip())
                    console.print(
                        f"⚠️ Failed to start monitoring service: {clean_stderr}",
                        style="bold yellow",
                    )
            except subprocess.TimeoutExpired:
                # This shouldn't happen with proper daemon detachment, but handle gracefully
                console.print(
                    "✅ Monitoring service started in daemon mode",
                    style="bold green",
                )
            except Exception as e:
                # Clean exception message from color codes if present
                import re

                clean_error_msg = re.sub(r"\x1b\[[0-9;]*m", "", str(e).strip())
                console.print(
                    f"⚠️ Failed to start monitoring service: {clean_error_msg}",
                    style="bold yellow",
                )
        else:
            console.print("ℹ️ Monitoring is disabled in config", style="dim")

    except Exception as e:
        console.print(f"⚠️ Failed to start monitoring: {e}", style="bold yellow")


def _determine_mcp_setup_choice(
    setup_mcp: bool, skip_mcp: bool, non_interactive: bool
) -> bool:
    """
    Determine user's choice for MCP integration setup.

    Args:
        setup_mcp: Force enable MCP setup
        skip_mcp: Force disable MCP setup
        non_interactive: Skip prompts, use defaults

    Returns:
        True if user wants MCP integration setup
    """
    # Use explicit flags if provided
    if setup_mcp:
        return True
    if skip_mcp:
        return False

    # Use defaults for non-interactive mode
    if non_interactive:
        return True  # Default: enable MCP setup (non-intrusive)

    # Check if any platforms are detected
    from heimdall.cli_commands.mcp_commands import get_mcp_platform_info

    platform_info = get_mcp_platform_info()

    if not platform_info:
        # No platforms detected, show guide and don't prompt
        from heimdall.cli_commands.mcp_commands import show_mcp_setup_guide

        show_mcp_setup_guide()
        return False

    # Show detected platforms
    console.print("", end="")  # Empty line for spacing
    console.print("🔗 Detected IDE platforms for MCP integration:", style="bold blue")

    for _platform_id, info in platform_info.items():
        config = info["config"]
        status = info["status"]
        console.print(f"   • {config.name}: {status}")

    # Interactive prompt
    return bool(
        typer.confirm(
            "Configure MCP integration for detected IDE platforms?",
            default=True,
        )
    )


def _execute_mcp_setup() -> list[str]:
    """
    Execute MCP setup for detected platforms.

    Returns:
        List of successfully configured platform names
    """
    configured_platforms: list[str] = []

    try:
        from heimdall.cli_commands.mcp_commands import (
            PLATFORMS,
            get_mcp_platform_info,
            install_mcp_interactive,
        )

        platform_info = get_mcp_platform_info()

        if not platform_info:
            console.print(
                "⚠️ No IDE platforms detected for MCP setup", style="bold yellow"
            )
            return configured_platforms

        console.print("🔗 Setting up MCP integration...", style="bold blue")

        # Filter platforms that need setup
        platforms_needing_setup = [
            (platform_id, info)
            for platform_id, info in platform_info.items()
            if info["needs_setup"]
        ]

        if not platforms_needing_setup:
            console.print(
                "✅ All detected platforms already configured", style="bold green"
            )
            # Still return all detected platforms as they're configured
            configured_platforms = [
                PLATFORMS[platform_id].name for platform_id in platform_info.keys()
            ]
            return configured_platforms

        # Setup each platform that needs it
        for platform_id, info in platforms_needing_setup:
            config = info["config"]
            console.print(f"   🔧 Configuring {config.name}...")

            try:
                success = install_mcp_interactive(platform_id, force=False)
                if success:
                    console.print(f"   ✅ {config.name} configured successfully")
                    configured_platforms.append(config.name)
                else:
                    console.print(f"   ⚠️ Failed to configure {config.name}")
            except Exception as e:
                console.print(f"   ❌ Error configuring {config.name}: {e}")

        # Add already configured platforms to the list
        for _platform_id, info in platform_info.items():
            if not info["needs_setup"]:
                configured_platforms.append(info["config"].name)

        if configured_platforms:
            console.print(
                f"✅ MCP integration completed for {len(configured_platforms)} platform(s)",
                style="bold green",
            )
            console.print(
                "   💡 Restart your IDE to load the new MCP server", style="dim"
            )

        return configured_platforms

    except Exception as e:
        console.print(f"❌ Error setting up MCP integration: {e}", style="bold red")
        return configured_platforms


def _ensure_nltk_data_available(progress: Any, task: Any) -> None:
    """
    Ensure required NLTK data is available for emotional dimension extraction.

    Downloads punkt_tab tokenizer and other required NLTK resources needed by
    TextBlob and NRCLex for emotional analysis in cognitive dimension extraction.

    Args:
        progress: Rich progress context for status updates
        task: Progress task for status updates
    """
    try:
        import subprocess
        import sys

        import nltk

        # Check if punkt_tab is available (this is what's failing in tests)
        try:
            from nltk.tokenize import sent_tokenize

            # Test if punkt_tab works
            sent_tokenize("Test sentence.")
            progress.update(task, description="✅ NLTK data already available")
            return
        except LookupError:
            # punkt_tab not found, need to download
            pass

        progress.update(
            task, description="📥 Downloading NLTK data (punkt_tab, punkt)..."
        )

        # Required NLTK data for TextBlob and NRCLex
        required_datasets = [
            "punkt_tab",  # New punkt tokenizer (required by latest NLTK)
            "punkt",  # Legacy punkt tokenizer (fallback)
        ]

        # Download required datasets
        for dataset in required_datasets:
            try:
                nltk.download(dataset, quiet=True)
            except Exception as e:
                # Log but continue - some datasets might not be available
                console.print(f"⚠️ Could not download {dataset}: {e}", style="dim")

        # Verify that tokenization now works
        try:
            from nltk.tokenize import sent_tokenize

            sent_tokenize("Test sentence.")
            progress.update(task, description="✅ NLTK data downloaded successfully")
        except LookupError:
            # If direct NLTK download failed, try alternative approach
            progress.update(
                task, description="📥 Using alternative NLTK download method..."
            )

            # Try using subprocess to download via python -m nltk.downloader
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import nltk; nltk.download('punkt_tab', quiet=True); nltk.download('punkt', quiet=True)",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                progress.update(
                    task, description="✅ NLTK data downloaded successfully"
                )
            else:
                progress.update(task, description="❌ Failed to download NLTK data")
                console.print(
                    f"❌ Failed to download NLTK data. Error: {result.stderr}",
                    style="bold red",
                )
                console.print(
                    "Please run manually: python -c \"import nltk; nltk.download('punkt_tab'); nltk.download('punkt')\"",
                    style="bold yellow",
                )

    except ImportError:
        progress.update(task, description="⚠️ NLTK not installed, skipping")
        console.print(
            "⚠️ NLTK not installed, emotional analysis may not work properly",
            style="bold yellow",
        )
    except Exception as e:
        progress.update(task, description="❌ Failed to setup NLTK data")
        console.print(f"❌ Error setting up NLTK data: {e}", style="bold red")
        console.print(
            "Please run manually: python -c \"import nltk; nltk.download('punkt_tab'); nltk.download('punkt')\"",
            style="bold yellow",
        )
