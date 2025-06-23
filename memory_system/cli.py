#!/usr/bin/env python3
"""
Unified CLI for the cognitive memory system with embedded service management.

This module provides a comprehensive command-line interface that handles:
- Qdrant vector database management
- Interface server management (HTTP, MCP)
- Interactive cognitive memory shell
- Health checking and system verification
"""

import json
import os
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from cognitive_memory.main import (
    InitializationError,
    graceful_shutdown,
    initialize_system,
    initialize_with_config,
)

from .health_checker import HealthChecker, HealthCheckResults, HealthResult
from .interactive_shell import InteractiveShell
from .service_manager import QdrantManager, ServiceStatus

# Initialize rich console for enhanced output
console = Console()

# Main CLI app
app = typer.Typer(
    name="memory_system",
    help="🧠 Cognitive Memory System - Unified CLI",
    add_completion=False,
)

# Service management commands
qdrant_app = typer.Typer(help="Qdrant vector database management")
app.add_typer(qdrant_app, name="qdrant")

# Server interface commands
serve_app = typer.Typer(help="Start interface servers")
app.add_typer(serve_app, name="serve")

# Monitoring service commands
monitor_app = typer.Typer(help="File monitoring service management")
app.add_typer(monitor_app, name="monitor")


@qdrant_app.command("start")  # type: ignore[misc]
def qdrant_start(
    port: int = typer.Option(6333, help="Port for Qdrant service"),
    data_dir: str | None = typer.Option(None, help="Data directory path"),
    detach: bool = typer.Option(True, help="Run in background"),
    force_local: bool = typer.Option(
        False, help="Force local binary instead of Docker"
    ),
    wait_timeout: int = typer.Option(30, help="Seconds to wait for startup"),
) -> None:
    """Start Qdrant vector database service."""
    console.print("🚀 Starting Qdrant vector database...", style="bold blue")

    manager = QdrantManager()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Starting Qdrant service...", total=None)

        try:
            success = manager.start(
                port=port,
                data_dir=data_dir,
                detach=detach,
                force_local=force_local,
                wait_timeout=wait_timeout,
            )

            if success:
                progress.update(task, description="✅ Qdrant started successfully")
                console.print(
                    f"🎉 Qdrant is running on port {port}", style="bold green"
                )

                # Show connection info
                info_table = Table(title="Connection Information")
                info_table.add_column("Property", style="cyan")
                info_table.add_column("Value", style="white")
                info_table.add_row("URL", f"http://localhost:{port}")
                info_table.add_row("Status", "✅ Running")
                info_table.add_row(
                    "Mode", "Docker" if not force_local else "Local Binary"
                )
                console.print(info_table)
                return  # Explicitly exit on success

            else:
                progress.update(task, description="❌ Failed to start Qdrant")
                console.print("❌ Failed to start Qdrant service", style="bold red")
                raise typer.Exit(1) from None

        except Exception as e:
            progress.update(task, description=f"❌ Error: {str(e)}")
            console.print(f"❌ Error starting Qdrant: {e}", style="bold red")
            raise typer.Exit(1) from e


@qdrant_app.command("stop")  # type: ignore[misc]
def qdrant_stop() -> None:
    """Stop Qdrant vector database service."""
    console.print("🛑 Stopping Qdrant vector database...", style="bold yellow")

    manager = QdrantManager()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Stopping Qdrant service...", total=None)

        try:
            success = manager.stop()

            if success:
                progress.update(task, description="✅ Qdrant stopped successfully")
                console.print("✅ Qdrant service stopped", style="bold green")
            else:
                progress.update(task, description="⚠️ Qdrant was not running")
                console.print("⚠️ Qdrant service was not running", style="bold yellow")

        except Exception as e:
            progress.update(task, description=f"❌ Error: {str(e)}")
            console.print(f"❌ Error stopping Qdrant: {e}", style="bold red")
            raise typer.Exit(1) from e


@qdrant_app.command("status")  # type: ignore[misc]
def qdrant_status(
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """Show Qdrant service status."""
    manager = QdrantManager()
    status = manager.get_status()

    if json_output:
        status_data = {
            "status": status.status.value,
            "port": status.port,
            "pid": status.pid,
            "container_id": status.container_id,
            "uptime_seconds": status.uptime_seconds,
            "health_status": status.health_status,
            "error": status.error,
        }
        console.print(json.dumps(status_data, indent=2))
        return

    # Rich formatted output
    if status.status == ServiceStatus.RUNNING:
        console.print("🟢 Qdrant is running", style="bold green")
    elif status.status == ServiceStatus.STOPPED:
        console.print("🔴 Qdrant is stopped", style="bold red")
    else:
        console.print("🟡 Qdrant status unknown", style="bold yellow")

    # Status table
    status_table = Table(title="Qdrant Service Status")
    status_table.add_column("Property", style="cyan")
    status_table.add_column("Value", style="white")

    status_table.add_row("Status", status.status.value)
    status_table.add_row("Port", str(status.port) if status.port else "N/A")
    status_table.add_row("PID", str(status.pid) if status.pid else "N/A")
    status_table.add_row("Container ID", status.container_id or "N/A")
    status_table.add_row(
        "Uptime", f"{status.uptime_seconds}s" if status.uptime_seconds else "N/A"
    )
    status_table.add_row("Health", status.health_status or "Unknown")

    if status.error:
        status_table.add_row("Error", status.error)

    console.print(status_table)


@qdrant_app.command("logs")  # type: ignore[misc]
def qdrant_logs(
    lines: int = typer.Option(50, help="Number of log lines to show"),
    follow: bool = typer.Option(False, "-f", help="Follow log output"),
) -> None:
    """Show Qdrant service logs."""
    manager = QdrantManager()

    try:
        logs = manager.get_logs(lines=lines, follow=follow)

        if follow:
            console.print(
                "📄 Following Qdrant logs (Ctrl+C to stop)...", style="bold blue"
            )
            console.print("-" * 60)

            try:
                for log_line in logs:
                    console.print(log_line.rstrip())
            except KeyboardInterrupt:
                console.print("\n⏹️ Stopped following logs", style="bold yellow")

        else:
            console.print(f"📄 Last {lines} lines from Qdrant logs:", style="bold blue")
            console.print("-" * 60)

            for log_line in logs:
                console.print(log_line.rstrip())

    except Exception as e:
        console.print(f"❌ Error retrieving logs: {e}", style="bold red")
        raise typer.Exit(1) from e


@serve_app.command("mcp")  # type: ignore[misc]
def serve_mcp(
    config: str | None = typer.Option(None, help="Path to configuration file"),
) -> None:
    """Start MCP protocol server in stdin/stdout mode."""
    console.print("🔗 Starting MCP server (stdin/stdout mode)...", style="bold blue")

    try:
        # Import here to avoid circular dependencies
        from interfaces.mcp_server import run_server

        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Start MCP server
        run_server(cognitive_system=cognitive_system)

    except ImportError as e:
        console.print("❌ MCP interface not implemented yet", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error starting MCP server: {e}", style="bold red")
        raise typer.Exit(1) from e


@app.command("shell")  # type: ignore[misc]
def interactive_shell(
    config: str | None = typer.Option(None, help="Path to configuration file"),
    prompt: str | None = typer.Option(None, help="Custom prompt string"),
) -> None:
    """Start interactive cognitive memory shell."""
    console.print(
        "🧠 Starting interactive cognitive memory shell...", style="bold blue"
    )

    try:
        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Start interactive shell
        shell = InteractiveShell(cognitive_system, custom_prompt=prompt)
        shell.run()

        # Cleanup
        graceful_shutdown(cognitive_system)

    except InitializationError as e:
        console.print(f"❌ Failed to initialize system: {e}", style="bold red")
        raise typer.Exit(1) from e
    except KeyboardInterrupt:
        console.print("\n👋 Goodbye!", style="bold yellow")
    except Exception as e:
        console.print(f"❌ Error in shell: {e}", style="bold red")
        raise typer.Exit(1) from e


# Git loading commands
load_git_app = typer.Typer(help="Git history loading commands")
app.add_typer(load_git_app, name="load-git")


@load_git_app.command("incremental")  # type: ignore[misc]
def load_git_incremental(
    source_path: str = typer.Argument(".", help="Path to git repository"),
    max_commits: int = typer.Option(1000, help="Maximum commits to process"),
    force_full_load: bool = typer.Option(
        False, "--force-full", help="Force full history load ignoring incremental state"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be loaded without actually loading"
    ),
    config: str | None = typer.Option(None, help="Path to configuration file"),
) -> None:
    """Load git commits incrementally (only new commits since last run)."""
    console.print("📚 Loading git commits incrementally...", style="bold blue")

    try:
        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Create CLI interface and delegate to it
        from interfaces.cli import CognitiveCLI

        cli = CognitiveCLI(cognitive_system)

        # Load git history with incremental mode
        success = cli.load_memories(
            source_path=source_path,
            loader_type="git",
            dry_run=dry_run,
            max_commits=max_commits,
            force_full_load=force_full_load,
        )

        if not success:
            raise typer.Exit(1)

        console.print("✅ Git incremental loading completed", style="bold green")

    except InitializationError as e:
        console.print(f"❌ Failed to initialize system: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error: {e}", style="bold red")
        raise typer.Exit(1) from e
    finally:
        # Graceful shutdown
        try:
            graceful_shutdown(cognitive_system)
        except Exception:
            pass  # Ignore shutdown errors


@app.command("load")  # type: ignore[misc]
def load_memories(
    source_path: str = typer.Argument(..., help="Path to the source file to load"),
    loader_type: str = typer.Option("markdown", help="Type of loader to use"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be loaded without actually loading"
    ),
    config: str | None = typer.Option(None, help="Path to configuration file"),
) -> None:
    """Load memories from external source file."""
    try:
        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Create CLI interface and delegate to it
        from interfaces.cli import CognitiveCLI

        cli = CognitiveCLI(cognitive_system)

        # Delegate to the CognitiveCLI class which handles all the logic
        success = cli.load_memories(
            source_path=source_path, loader_type=loader_type, dry_run=dry_run
        )

        if not success:
            raise typer.Exit(1)

    except InitializationError as e:
        console.print(f"❌ Failed to initialize system: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error: {e}", style="bold red")
        raise typer.Exit(1) from e
    finally:
        # Graceful shutdown
        try:
            graceful_shutdown(cognitive_system)
        except Exception:
            pass  # Ignore shutdown errors


@app.command("doctor")  # type: ignore[misc]
def health_check(
    json_output: bool = typer.Option(
        False, "--json", help="Output results in JSON format"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Show detailed diagnostic information"
    ),
    fix: bool = typer.Option(False, "--fix", help="Attempt to fix detected issues"),
    config: str | None = typer.Option(None, help="Path to configuration file"),
) -> None:
    """Run comprehensive health checks and system verification."""
    console.print(
        "🩺 Running cognitive memory system health checks...", style="bold blue"
    )

    checker = HealthChecker(config_path=config)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running health checks...", total=None)

        try:
            results = checker.run_all_checks(verbose=verbose, fix_issues=fix)

            progress.update(task, description="✅ Health checks completed")

            if json_output:
                # JSON output for CI/CD integration
                json_results = {
                    "overall_status": results.overall_status.value,
                    "checks": [
                        {
                            "name": check.name,
                            "status": check.status.value,
                            "message": check.message,
                            "details": check.details,
                            "fix_attempted": check.fix_attempted,
                            "fix_successful": check.fix_successful,
                        }
                        for check in results.checks
                    ],
                    "recommendations": results.recommendations,
                    "timestamp": results.timestamp.isoformat(),
                }
                console.print(json.dumps(json_results, indent=2))

            else:
                # Rich formatted output
                _display_health_results(results, verbose)

            # Exit with appropriate code
            if results.overall_status == HealthResult.HEALTHY:
                console.print("✅ System is healthy!", style="bold green")
            elif results.overall_status == HealthResult.WARNING:
                console.print("⚠️ System has warnings", style="bold yellow")
                raise typer.Exit(1)
            else:
                console.print("❌ System has critical issues", style="bold red")
                raise typer.Exit(2)

        except Exception as e:
            progress.update(task, description=f"❌ Error: {str(e)}")
            console.print(f"❌ Error running health checks: {e}", style="bold red")
            raise typer.Exit(1) from e


def _display_health_results(results: HealthCheckResults, verbose: bool) -> None:
    """Display health check results in rich format."""
    # Overall status panel
    if results.overall_status == HealthResult.HEALTHY:
        status_color = "green"
        status_icon = "✅"
    elif results.overall_status == HealthResult.WARNING:
        status_color = "yellow"
        status_icon = "⚠️"
    else:
        status_color = "red"
        status_icon = "❌"

    status_panel = Panel(
        f"{status_icon} Overall Status: [bold {status_color}]{results.overall_status.value.upper()}[/bold {status_color}]",
        title="Health Check Summary",
        border_style=status_color,
    )
    console.print(status_panel)

    # Individual checks table
    checks_table = Table(title="Individual Health Checks")
    checks_table.add_column("Check", style="cyan")
    checks_table.add_column("Status", style="white")
    checks_table.add_column("Message", style="white")

    if verbose:
        checks_table.add_column("Details", style="dim")

    for check in results.checks:
        if check.status == HealthResult.HEALTHY:
            status_display = "✅ PASS"
        elif check.status == HealthResult.WARNING:
            status_display = "⚠️ WARN"
        else:
            status_display = "❌ FAIL"

        row_data = [check.name, status_display, check.message]
        if verbose and check.details:
            row_data.append(str(check.details))
        elif verbose:
            row_data.append("N/A")

        checks_table.add_row(*row_data)

    console.print(checks_table)

    # Recommendations
    if results.recommendations:
        console.print("\n📋 Recommendations:", style="bold blue")
        for i, recommendation in enumerate(results.recommendations, 1):
            console.print(f"  {i}. {recommendation}")


@monitor_app.command("start")  # type: ignore[misc]
def monitor_start(
    target_path: str | None = typer.Argument(None, help="Directory to monitor"),
    daemon: bool = typer.Option(False, "--daemon", help="Run in daemon mode"),
    interval: float = typer.Option(5.0, help="Polling interval in seconds"),
    project_root: str | None = typer.Option(None, help="Project root directory"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """Start file monitoring service."""
    try:
        from .monitoring_service import MonitoringService, MonitoringServiceError

        # Set target path if provided (for backward compatibility with env var)
        if target_path:
            os.environ["MONITORING_TARGET_PATH"] = str(Path(target_path).resolve())

        # Set interval if provided (for backward compatibility with env var)
        if interval != 5.0:
            os.environ["MONITORING_INTERVAL_SECONDS"] = str(interval)

        console.print("🔍 Starting file monitoring service...", style="bold blue")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Starting monitoring service...", total=None)

            service = MonitoringService(project_root=project_root)
            success = service.start(daemon_mode=daemon)

            if success:
                progress.update(task, description="✅ Monitoring service started")

                if json_output:
                    status = service.get_status()
                    console.print(json.dumps(status, indent=2))
                else:
                    console.print(
                        "✅ File monitoring service started successfully",
                        style="bold green",
                    )

                    target = os.getenv("MONITORING_TARGET_PATH", "unknown")
                    console.print(f"📁 Monitoring: {target}")
                    console.print(f"⏱️ Interval: {interval}s")

                    if daemon:
                        console.print("🔧 Running in daemon mode")
                    else:
                        console.print("Press Ctrl+C to stop monitoring")
            else:
                progress.update(task, description="❌ Failed to start monitoring")
                console.print("❌ Failed to start monitoring service", style="bold red")
                raise typer.Exit(1)

    except MonitoringServiceError as e:
        console.print(f"❌ Monitoring service error: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error starting monitoring: {e}", style="bold red")
        raise typer.Exit(1) from e


@monitor_app.command("stop")  # type: ignore[misc]
def monitor_stop(
    project_root: str | None = typer.Option(None, help="Project root directory"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """Stop file monitoring service."""
    try:
        from .monitoring_service import MonitoringService, MonitoringServiceError

        console.print("🛑 Stopping file monitoring service...", style="bold yellow")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Stopping monitoring service...", total=None)

            service = MonitoringService(project_root=project_root)
            success = service.stop()

            if success:
                progress.update(task, description="✅ Monitoring service stopped")

                if json_output:
                    status = service.get_status()
                    console.print(json.dumps(status, indent=2))
                else:
                    console.print(
                        "✅ File monitoring service stopped", style="bold green"
                    )
            else:
                progress.update(task, description="⚠️ Service was not running")
                console.print(
                    "⚠️ Monitoring service was not running", style="bold yellow"
                )

    except MonitoringServiceError as e:
        console.print(f"❌ Monitoring service error: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error stopping monitoring: {e}", style="bold red")
        raise typer.Exit(1) from e


@monitor_app.command("restart")  # type: ignore[misc]
def monitor_restart(
    project_root: str | None = typer.Option(None, help="Project root directory"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """Restart file monitoring service."""
    try:
        from .monitoring_service import MonitoringService, MonitoringServiceError

        console.print("🔄 Restarting file monitoring service...", style="bold blue")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Restarting monitoring service...", total=None)

            service = MonitoringService(project_root=project_root)
            success = service.restart()

            if success:
                progress.update(task, description="✅ Monitoring service restarted")

                if json_output:
                    status = service.get_status()
                    console.print(json.dumps(status, indent=2))
                else:
                    console.print(
                        "✅ File monitoring service restarted successfully",
                        style="bold green",
                    )
            else:
                progress.update(task, description="❌ Failed to restart monitoring")
                console.print(
                    "❌ Failed to restart monitoring service", style="bold red"
                )
                raise typer.Exit(1)

    except MonitoringServiceError as e:
        console.print(f"❌ Monitoring service error: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error restarting monitoring: {e}", style="bold red")
        raise typer.Exit(1) from e


@monitor_app.command("status")  # type: ignore[misc]
def monitor_status(
    project_root: str | None = typer.Option(None, help="Project root directory"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
    detailed: bool = typer.Option(
        False, "--detailed", help="Show detailed status information"
    ),
) -> None:
    """Show file monitoring service status."""
    try:
        from .monitoring_service import MonitoringService, MonitoringServiceError

        service = MonitoringService(project_root=project_root)
        status = service.get_status()

        if json_output:
            console.print(json.dumps(status, indent=2))
            return

        # Rich formatted output
        if status["is_running"]:
            console.print("🟢 File monitoring service is running", style="bold green")
        else:
            console.print("🔴 File monitoring service is stopped", style="bold red")

        # Status table
        status_table = Table(title="Monitoring Service Status")
        status_table.add_column("Property", style="cyan")
        status_table.add_column("Value", style="white")

        status_table.add_row("Status", "Running" if status["is_running"] else "Stopped")
        status_table.add_row("PID", str(status["pid"]) if status["pid"] else "N/A")

        if status["uptime_seconds"]:
            uptime = status["uptime_seconds"]
            if uptime > 3600:
                uptime_str = f"{uptime / 3600:.1f} hours"
            elif uptime > 60:
                uptime_str = f"{uptime / 60:.1f} minutes"
            else:
                uptime_str = f"{uptime:.1f} seconds"
            status_table.add_row("Uptime", uptime_str)

        status_table.add_row("Files Monitored", str(status["files_monitored"]))
        status_table.add_row("Sync Operations", str(status["sync_operations"]))
        status_table.add_row("Error Count", str(status["error_count"]))

        if detailed:
            if status["memory_usage_mb"]:
                status_table.add_row(
                    "Memory Usage", f"{status['memory_usage_mb']:.1f} MB"
                )
            if status["cpu_percent"]:
                status_table.add_row("CPU Usage", f"{status['cpu_percent']:.1f}%")
            if status["restart_count"]:
                status_table.add_row("Restart Count", str(status["restart_count"]))
            if status["last_error"]:
                status_table.add_row("Last Error", status["last_error"])

        console.print(status_table)

        # Target path information from centralized config
        try:
            from pathlib import Path

            from cognitive_memory.core.config import get_monitoring_config

            config = get_monitoring_config(Path(project_root) if project_root else None)
            target_path = config["target_path"]
            console.print(f"\n📁 Target Path: {target_path}")
        except Exception:
            # Fallback to environment variable for backward compatibility
            target_path = os.getenv("MONITORING_TARGET_PATH")
            if target_path:
                console.print(f"\n📁 Target Path: {target_path}")

    except MonitoringServiceError as e:
        console.print(f"❌ Monitoring service error: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error getting status: {e}", style="bold red")
        raise typer.Exit(1) from e


@monitor_app.command("health")  # type: ignore[misc]
def monitor_health(
    project_root: str | None = typer.Option(None, help="Project root directory"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """Perform monitoring service health check."""
    try:
        from .monitoring_service import MonitoringService, MonitoringServiceError

        service = MonitoringService(project_root=project_root)
        health = service.health_check()

        if json_output:
            console.print(json.dumps(health, indent=2))
            return

        # Rich formatted output
        if health["status"] == "healthy":
            console.print("🟢 Monitoring service is healthy", style="bold green")
        elif health["status"] == "warning":
            console.print("🟡 Monitoring service has warnings", style="bold yellow")
        else:
            console.print("🔴 Monitoring service is unhealthy", style="bold red")

        # Health checks table
        health_table = Table(title="Health Check Results")
        health_table.add_column("Check", style="cyan")
        health_table.add_column("Status", style="white")
        health_table.add_column("Message", style="white")

        for check in health["checks"]:
            if check["status"] == "pass":
                status_display = "✅ PASS"
            elif check["status"] == "warn":
                status_display = "⚠️ WARN"
            else:
                status_display = "❌ FAIL"

            health_table.add_row(
                check["name"].replace("_", " ").title(),
                status_display,
                check["message"],
            )

        console.print(health_table)

        # Exit with appropriate code
        if health["status"] == "healthy":
            return
        elif health["status"] == "warning":
            raise typer.Exit(1)
        else:
            raise typer.Exit(2)

    except MonitoringServiceError as e:
        console.print(f"❌ Monitoring service error: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error checking health: {e}", style="bold red")
        raise typer.Exit(1) from e


def main() -> int:
    """Main entry point for the unified CLI."""
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
