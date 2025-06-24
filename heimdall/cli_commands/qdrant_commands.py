"""Qdrant vector database management commands."""

import json

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from heimdall.cognitive_system.service_manager import QdrantManager, ServiceStatus

console = Console()


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
