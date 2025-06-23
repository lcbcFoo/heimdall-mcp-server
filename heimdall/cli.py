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
from rich.console import Console

# Import command functions from separate modules
from heimdall.cli_commands.cognitive_commands import (
    load_git_patterns,
    load_memories,
    recall_memories,
    store_experience,
    system_status,
)
from heimdall.cli_commands.health_commands import health_check, interactive_shell
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

# Initialize rich console for enhanced output
console = Console()

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


def main() -> int:
    """Main entry point for the unified Heimdall CLI."""
    try:
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
