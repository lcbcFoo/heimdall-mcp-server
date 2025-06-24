#!/usr/bin/env python3
"""
Release automation script for heimdall-mcp package.

This script automates the release process:
1. Validates package configuration
2. Builds distribution packages
3. Optionally uploads to PyPI
"""

import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()


def run_command(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    console.print(f"[cyan]Running:[/cyan] {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if check and result.returncode != 0:
        console.print(f"[red]Command failed:[/red] {cmd}")
        console.print(f"[red]Error:[/red] {result.stderr}")
        sys.exit(1)

    return result


def validate_package() -> bool:
    """Validate package configuration and dependencies."""
    console.print("[yellow]Validating package configuration...[/yellow]")

    # Check pyproject.toml exists
    if not Path("pyproject.toml").exists():
        console.print("[red]Error: pyproject.toml not found[/red]")
        return False

    # Validate package with build tools
    try:
        run_command("python -m build --help > /dev/null")
    except SystemExit:
        console.print(
            "[red]Error: build module not installed. Run: pip install build[/red]"
        )
        return False

    # Check if package can be imported
    try:
        run_command(
            "python -c 'import cognitive_memory; import interfaces; import heimdall'"
        )
    except SystemExit:
        console.print("[red]Error: Package modules cannot be imported[/red]")
        return False

    console.print("[green]Package validation passed![/green]")
    return True


def clean_build_artifacts() -> None:
    """Clean previous build artifacts."""
    console.print("[yellow]Cleaning build artifacts...[/yellow]")

    artifacts = ["build/", "dist/", "*.egg-info/"]
    for artifact in artifacts:
        run_command(f"rm -rf {artifact}", check=False)


def build_package() -> bool:
    """Build source and wheel distributions."""
    console.print("[yellow]Building package distributions...[/yellow]")

    try:
        run_command("python -m build")
        console.print("[green]Package built successfully![/green]")
        return True
    except SystemExit:
        console.print("[red]Build failed[/red]")
        return False


def check_distribution() -> bool:
    """Check the built distribution with twine."""
    console.print("[yellow]Checking distribution...[/yellow]")

    try:
        run_command("python -m twine check dist/*")
        console.print("[green]Distribution check passed![/green]")
        return True
    except SystemExit:
        console.print("[red]Distribution check failed[/red]")
        return False


def upload_to_pypi(test: bool = False) -> bool:
    """Upload package to PyPI or TestPyPI."""
    repository = "testpypi" if test else "pypi"
    console.print(f"[yellow]Uploading to {repository.upper()}...[/yellow]")

    try:
        if test:
            run_command("python -m twine upload --repository testpypi dist/*")
        else:
            run_command("python -m twine upload dist/*")

        console.print(f"[green]Successfully uploaded to {repository.upper()}![/green]")
        return True
    except SystemExit:
        console.print(f"[red]Upload to {repository.upper()} failed[/red]")
        return False


def main(
    clean: bool = typer.Option(True, help="Clean build artifacts before building"),
    validate: bool = typer.Option(True, help="Validate package before building"),
    build: bool = typer.Option(True, help="Build package distributions"),
    check: bool = typer.Option(True, help="Check built distributions"),
    upload: bool = typer.Option(False, help="Upload to PyPI"),
    test_upload: bool = typer.Option(False, help="Upload to TestPyPI"),
) -> None:
    """
    Release automation for heimdall-mcp package.

    This script handles the complete release process from validation to upload.
    """
    console.print(
        Panel.fit(
            "[bold blue]Heimdall MCP Release Automation[/bold blue]",
            border_style="blue",
        )
    )

    # Change to project root
    project_root = Path(__file__).parent.parent
    console.print(f"[cyan]Working directory:[/cyan] {project_root}")

    try:
        # Validation
        if validate and not validate_package():
            sys.exit(1)

        # Clean artifacts
        if clean:
            clean_build_artifacts()

        # Build package
        if build and not build_package():
            sys.exit(1)

        # Check distribution
        if check and not check_distribution():
            sys.exit(1)

        # Upload options
        if test_upload:
            if not upload_to_pypi(test=True):
                sys.exit(1)
        elif upload:
            if not upload_to_pypi(test=False):
                sys.exit(1)

        console.print(
            Panel.fit(
                "[bold green]Release process completed successfully![/bold green]",
                border_style="green",
            )
        )

        if not (upload or test_upload):
            console.print("\n[yellow]Next steps:[/yellow]")
            console.print(
                "• To upload to TestPyPI: python scripts/release.py --test-upload"
            )
            console.print("• To upload to PyPI: python scripts/release.py --upload")

    except KeyboardInterrupt:
        console.print("\n[red]Release process interrupted by user[/red]")
        sys.exit(1)


if __name__ == "__main__":
    typer.run(main)
