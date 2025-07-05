#!/usr/bin/env python3
"""
Unified CLI for the Heimdall cognitive memory system.

This module provides a clean command-line interface that consolidates:
- Cognitive memory operations (store, recall, load, git-load, status)
- Service management (qdrant, monitor, project)
- Interactive shell and health checking

Uses the operations layer for cognitive commands and imports service management
components for infrastructure operations.
"""

import sys

import typer
from loguru import logger
from rich.console import Console

# Import command functions from separate modules
from heimdall.cli_commands.cognitive_commands import (
    delete_memories_by_tags_cmd,
    delete_memory_cmd,
    load_git_patterns,
    load_memories,
    recall_memories,
    remove_file_cmd,
    store_experience,
    system_status,
)
from heimdall.cli_commands.git_hook_commands import (
    git_hook_install,
    git_hook_status,
    git_hook_uninstall,
)
from heimdall.cli_commands.health_commands import health_check, interactive_shell
from heimdall.cli_commands.mcp_commands import (
    generate_mcp,
    install_mcp,
    list_mcp,
    remove_mcp,
    status_mcp,
)
from heimdall.cli_commands.monitor_commands import (
    monitor_health,
    monitor_restart,
    monitor_start,
    monitor_status,
    monitor_stop,
)
from heimdall.cli_commands.project_commands import (
    project_clean,
    project_init,
    project_list,
)
from heimdall.cli_commands.qdrant_commands import (
    qdrant_logs,
    qdrant_start,
    qdrant_status,
    qdrant_stop,
)

# Set default Loguru log level to WARNING to prevent early DEBUG messages
# This will be reconfigured by early logging setup based on project config
logger.remove()
logger.add(
    sys.stderr,
    level="WARNING",
    format="{time} | {level} | {name}:{function}:{line} - {message}",
)

# Initialize rich console for enhanced output
console = Console()

# Global flag to track logging configuration
_logging_configured = False

# Main CLI app
app = typer.Typer(
    name="heimdall",
    help="🧠 Heimdall Cognitive Memory System - Unified CLI",
    add_completion=False,
)

# Service management command groups
qdrant_app = typer.Typer(help="Qdrant vector database management")
app.add_typer(qdrant_app, name="qdrant")

monitor_app = typer.Typer(help="File monitoring service management")
app.add_typer(monitor_app, name="monitor")

project_app = typer.Typer(help="Project memory management")
app.add_typer(project_app, name="project")

git_hook_app = typer.Typer(help="Git hook management for automatic memory processing")
app.add_typer(git_hook_app, name="git-hook")

mcp_app = typer.Typer(help="🔗 MCP integration management")
app.add_typer(mcp_app, name="mcp")

serve_app = typer.Typer(help="Start interface servers")
app.add_typer(serve_app, name="serve")

# Legacy git loading commands for compatibility
load_git_app = typer.Typer(help="Git history loading commands")
app.add_typer(load_git_app, name="load-git")

# Register cognitive memory commands
app.command("store")(store_experience)
app.command("recall")(recall_memories)
app.command("load")(load_memories)
app.command("git-load")(load_git_patterns)
app.command("status")(system_status)
app.command("remove-file")(remove_file_cmd)
app.command("delete-memory")(delete_memory_cmd)
app.command("delete-memories-by-tags")(delete_memories_by_tags_cmd)

# Register health and shell commands
app.command("doctor")(health_check)
app.command("shell")(interactive_shell)

# Register Qdrant commands
qdrant_app.command("start")(qdrant_start)
qdrant_app.command("stop")(qdrant_stop)
qdrant_app.command("status")(qdrant_status)
qdrant_app.command("logs")(qdrant_logs)

# Register monitor commands
monitor_app.command("start")(monitor_start)
monitor_app.command("stop")(monitor_stop)
monitor_app.command("restart")(monitor_restart)
monitor_app.command("status")(monitor_status)
monitor_app.command("health")(monitor_health)

# Register project commands
project_app.command("init")(project_init)
project_app.command("list")(project_list)
project_app.command("clean")(project_clean)

# Register git hook commands
git_hook_app.command("install")(git_hook_install)
git_hook_app.command("uninstall")(git_hook_uninstall)
git_hook_app.command("status")(git_hook_status)

# Register MCP commands
mcp_app.command("install")(install_mcp)
mcp_app.command("list")(list_mcp)
mcp_app.command("remove")(remove_mcp)
mcp_app.command("status")(status_mcp)
mcp_app.command("generate")(generate_mcp)


def _setup_early_logging() -> None:
    """
    Set up early logging based on project configuration before any CLI operations.

    This detects project config and applies logging level early to reduce verbosity
    of initialization messages across all commands.
    """
    try:
        # Detect project config and apply environment overrides
        import os
        import sys

        from cognitive_memory.core.config import LoggingConfig, detect_project_config
        from cognitive_memory.core.logging_setup import setup_logging

        # Global flag to track logging configuration
        global _logging_configured

        # For project init commands, default to WARN level to reduce noise
        is_project_init = len(sys.argv) >= 3 and sys.argv[1:3] == ["project", "init"]

        # Set default logging level to WARN if not already configured
        # Note: detect_project_config looks for LOG_LEVEL, not HEIMDALL_LOG_LEVEL
        if "LOG_LEVEL" not in os.environ and "HEIMDALL_LOG_LEVEL" not in os.environ:
            if is_project_init:
                # During project init, ensure WARNING level to reduce initialization noise
                os.environ["LOG_LEVEL"] = "WARNING"
            else:
                # Try to detect project config first
                project_config = detect_project_config()
                if project_config:
                    # Apply project config to environment variables
                    for key, value in project_config.items():
                        if key not in os.environ:  # Only set if not already defined
                            os.environ[key] = value
                else:
                    # No project config found, default to WARNING for all commands
                    os.environ["LOG_LEVEL"] = "WARNING"

        # Create logging config using the environment (including project overrides)
        logging_config = LoggingConfig.from_env()

        # Set up logging immediately
        setup_logging(logging_config)

        # Mark logging as configured to prevent duplicate setup
        _logging_configured = True

    except Exception:
        # If early setup fails, continue with default logging
        # Individual commands will set up logging again later
        pass


def main() -> int:
    """Main entry point for the unified Heimdall CLI."""
    try:
        # Set up early logging from project config before any operations
        _setup_early_logging()

        app()
        return 0
    except typer.Exit as e:
        return int(e.exit_code) if e.exit_code is not None else 1
    except KeyboardInterrupt:
        console.print("\n⚠️ Interrupted by user", style="bold yellow")
        return 130
    except Exception as e:
        console.print(f"❌ Unexpected error: {e}", style="bold red")
        return 1


if __name__ == "__main__":
    sys.exit(main())
