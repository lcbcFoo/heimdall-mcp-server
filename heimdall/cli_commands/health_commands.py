"""Health check and interactive shell commands."""

import json

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
from heimdall.cognitive_system.health_checker import (
    HealthChecker,
    HealthCheckResults,
    HealthResult,
)
from heimdall.interactive_shell import InteractiveShell

console = Console()


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


def interactive_shell(
    config: str | None = typer.Option(None, help="Path to configuration file"),
    prompt: str | None = typer.Option(None, help="Custom prompt string"),
) -> None:
    """Start interactive cognitive memory shell."""
    # Show project context
    try:
        from cognitive_memory.core.config import get_project_id

        project_id = get_project_id()
        console.print(
            f"🧠 Starting interactive cognitive memory shell for project: {project_id}",
            style="bold blue",
        )
    except Exception:
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
