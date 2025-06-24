"""File monitoring service management commands."""

import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from heimdall.cognitive_system.monitoring_service import (
    MonitoringService,
    MonitoringServiceError,
)

console = Console()


def monitor_start(
    daemon: bool = typer.Option(False, help="Run in daemon mode"),
    project_root: str | None = typer.Option(None, help="Project root directory"),
) -> None:
    """Start file monitoring service."""
    console.print("🔍 Starting file monitoring service...", style="bold blue")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Starting monitoring service...", total=None)

        try:
            service = MonitoringService(project_root=project_root)
            success = service.start(daemon_mode=daemon)

            if success:
                progress.update(task, description="✅ Monitoring service started")
                console.print(
                    "✅ File monitoring service started successfully",
                    style="bold green",
                )

                if daemon:
                    console.print(
                        "🔄 Running in daemon mode - monitoring files in background",
                        style="dim",
                    )
                else:
                    console.print(
                        "👀 Monitoring files - press Ctrl+C to stop", style="dim"
                    )

                # Show status info
                status = service.get_status()
                info_table = Table(title="Service Information")
                info_table.add_column("Property", style="cyan")
                info_table.add_column("Value", style="white")
                info_table.add_row("Status", "✅ Running")
                info_table.add_row("PID", str(status["pid"]))
                info_table.add_row("Files Monitored", str(status["files_monitored"]))
                console.print(info_table)

            else:
                progress.update(task, description="❌ Failed to start monitoring")
                console.print(
                    "❌ Failed to start file monitoring service", style="bold red"
                )
                raise typer.Exit(1)

        except MonitoringServiceError as e:
            progress.update(task, description=f"❌ Service error: {str(e)}")
            console.print(f"❌ Service error: {e}", style="bold red")
            raise typer.Exit(1) from e
        except Exception as e:
            progress.update(task, description=f"❌ Error: {str(e)}")
            console.print(
                f"❌ Error starting monitoring service: {e}", style="bold red"
            )
            raise typer.Exit(1) from e


def monitor_stop(
    project_root: str | None = typer.Option(None, help="Project root directory"),
) -> None:
    """Stop file monitoring service."""
    console.print("🛑 Stopping file monitoring service...", style="bold yellow")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Stopping monitoring service...", total=None)

        try:
            service = MonitoringService(project_root=project_root)
            success = service.stop()

            if success:
                progress.update(task, description="✅ Monitoring service stopped")
                console.print(
                    "✅ File monitoring service stopped successfully",
                    style="bold green",
                )
            else:
                progress.update(task, description="⚠️ Service was not running")
                console.print(
                    "⚠️ File monitoring service was not running", style="bold yellow"
                )

        except MonitoringServiceError as e:
            progress.update(task, description=f"❌ Service error: {str(e)}")
            console.print(f"❌ Service error: {e}", style="bold red")
            raise typer.Exit(1) from e
        except Exception as e:
            progress.update(task, description=f"❌ Error: {str(e)}")
            console.print(
                f"❌ Error stopping monitoring service: {e}", style="bold red"
            )
            raise typer.Exit(1) from e


def monitor_restart(
    project_root: str | None = typer.Option(None, help="Project root directory"),
) -> None:
    """Restart file monitoring service."""
    console.print("🔄 Restarting file monitoring service...", style="bold blue")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Restarting monitoring service...", total=None)

        try:
            service = MonitoringService(project_root=project_root)
            success = service.restart()

            if success:
                progress.update(task, description="✅ Monitoring service restarted")
                console.print(
                    "✅ File monitoring service restarted successfully",
                    style="bold green",
                )

                # Show status info
                status = service.get_status()
                info_table = Table(title="Service Information")
                info_table.add_column("Property", style="cyan")
                info_table.add_column("Value", style="white")
                info_table.add_row("Status", "✅ Running")
                info_table.add_row("PID", str(status["pid"]))
                info_table.add_row("Restart Count", str(status["restart_count"]))
                info_table.add_row("Files Monitored", str(status["files_monitored"]))
                console.print(info_table)

            else:
                progress.update(task, description="❌ Failed to restart monitoring")
                console.print(
                    "❌ Failed to restart file monitoring service", style="bold red"
                )
                raise typer.Exit(1)

        except MonitoringServiceError as e:
            progress.update(task, description=f"❌ Service error: {str(e)}")
            console.print(f"❌ Service error: {e}", style="bold red")
            raise typer.Exit(1) from e
        except Exception as e:
            progress.update(task, description=f"❌ Error: {str(e)}")
            console.print(
                f"❌ Error restarting monitoring service: {e}", style="bold red"
            )
            raise typer.Exit(1) from e


def monitor_status(
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
    project_root: str | None = typer.Option(None, help="Project root directory"),
) -> None:
    """Show file monitoring service status."""
    try:
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
        status_table.add_row(
            "Uptime",
            f"{status['uptime_seconds']:.1f}s" if status["uptime_seconds"] else "N/A",
        )
        status_table.add_row("Files Monitored", str(status["files_monitored"]))
        status_table.add_row("Sync Operations", str(status["sync_operations"]))
        status_table.add_row("Error Count", str(status["error_count"]))
        status_table.add_row("Restart Count", str(status["restart_count"]))

        if status["memory_usage_mb"]:
            status_table.add_row("Memory Usage", f"{status['memory_usage_mb']:.1f} MB")

        if status["cpu_percent"]:
            status_table.add_row("CPU Usage", f"{status['cpu_percent']:.1f}%")

        if status["last_sync_time"]:
            import datetime

            sync_time = datetime.datetime.fromtimestamp(status["last_sync_time"])
            status_table.add_row("Last Sync", sync_time.strftime("%Y-%m-%d %H:%M:%S"))

        if status["last_error"]:
            status_table.add_row("Last Error", status["last_error"])

        console.print(status_table)

    except MonitoringServiceError as e:
        console.print(f"❌ Service error: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error getting monitoring status: {e}", style="bold red")
        raise typer.Exit(1) from e


def monitor_health(
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
    project_root: str | None = typer.Option(None, help="Project root directory"),
) -> None:
    """Perform file monitoring service health check."""
    try:
        service = MonitoringService(project_root=project_root)
        health = service.health_check()

        if json_output:
            console.print(json.dumps(health, indent=2))
            return

        # Rich formatted output
        if health["status"] == "healthy":
            console.print("🟢 File monitoring service is healthy", style="bold green")
        elif health["status"] == "warning":
            console.print(
                "🟡 File monitoring service has warnings", style="bold yellow"
            )
        else:
            console.print("🔴 File monitoring service is unhealthy", style="bold red")

        # Health checks table
        checks_table = Table(title="Health Checks")
        checks_table.add_column("Check", style="cyan")
        checks_table.add_column("Status", style="white")
        checks_table.add_column("Message", style="white")

        for check in health["checks"]:
            if check["status"] == "pass":
                status_display = "✅ PASS"
            elif check["status"] == "warn":
                status_display = "⚠️ WARN"
            else:
                status_display = "❌ FAIL"

            checks_table.add_row(check["name"], status_display, check["message"])

        console.print(checks_table)

        # Overall status panel
        if health["status"] == "healthy":
            status_color = "green"
            status_icon = "✅"
        elif health["status"] == "warning":
            status_color = "yellow"
            status_icon = "⚠️"
        else:
            status_color = "red"
            status_icon = "❌"

        status_panel = Panel(
            f"{status_icon} Overall Status: [bold {status_color}]{health['status'].upper()}[/bold {status_color}]",
            title="Health Summary",
            border_style=status_color,
        )
        console.print(status_panel)

        # Exit with appropriate code
        if health["status"] == "healthy":
            return
        elif health["status"] == "warning":
            raise typer.Exit(1)
        else:
            raise typer.Exit(2)

    except MonitoringServiceError as e:
        console.print(f"❌ Service error: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error performing health check: {e}", style="bold red")
        raise typer.Exit(1) from e
