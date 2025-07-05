#!/usr/bin/env python3
"""
Heimdall MCP Server - Git Hook Installer (Python Implementation)

Safely installs post-commit hook with preservation of existing hooks.
Replaces the bash implementation with cross-platform Python code.

This installer provides the same functionality as the bash version:
- Safe installation with existing hook preservation
- Hook chaining and backup/restore functionality
- Cross-platform compatibility using pathlib
- Comprehensive status checking and validation
"""

import sys
from pathlib import Path
from typing import Literal

try:
    import typer
    from rich.console import Console

    _has_rich = True
except ImportError:
    # Fallback to basic print if rich/typer not available
    print("Warning: typer/rich not available, using basic interface")
    typer = None  # type: ignore
    Console = None  # type: ignore
    _has_rich = False

# Initialize console if available
console = Console() if _has_rich else None


def log_info(message: str) -> None:
    """Log info message with proper formatting."""
    if console:
        console.print(f"[blue][INFO][/blue] {message}")
    else:
        print(f"[INFO] {message}")


def log_success(message: str) -> None:
    """Log success message with proper formatting."""
    if console:
        console.print(f"[green][SUCCESS][/green] {message}")
    else:
        print(f"[SUCCESS] {message}")


def log_warning(message: str) -> None:
    """Log warning message with proper formatting."""
    if console:
        console.print(f"[yellow][WARNING][/yellow] {message}")
    else:
        print(f"[WARNING] {message}")


def log_error(message: str) -> None:
    """Log error message with proper formatting."""
    if console:
        console.print(f"[red][ERROR][/red] {message}")
    else:
        print(f"[ERROR] {message}")


def show_usage() -> None:
    """Show usage information."""
    usage_text = """
Usage: git_hook_installer.py [OPTIONS] [REPOSITORY_PATH]

Install Heimdall post-commit hook for automatic incremental git loading.

OPTIONS:
    --install       Install the post-commit hook (default)
    --uninstall     Remove the Heimdall post-commit hook
    --status        Show current hook status
    --force         Force installation even if hooks exist
    --dry-run       Show what would be done without making changes
    --help, -h      Show this help message

REPOSITORY_PATH:
    Path to git repository (default: current directory)

EXAMPLES:
    git_hook_installer.py                          # Install hook in current repository
    git_hook_installer.py /path/to/repo            # Install hook in specific repository
    git_hook_installer.py --uninstall              # Remove hook from current repository
    git_hook_installer.py --status                 # Check hook status
    git_hook_installer.py --dry-run --force        # Preview forced installation
    """
    print(usage_text)


def validate_git_repo(repo_path: Path) -> bool:
    """
    Validate git repository.

    Args:
        repo_path: Path to validate

    Returns:
        True if valid git repository
    """
    if not (repo_path / ".git").exists():
        log_error(f"Not a git repository: {repo_path}")
        log_error(
            "Please run this script from within a git repository or specify a valid path."
        )
        return False
    return True


def validate_hook_script() -> tuple[bool, Path]:
    """
    Check if hook script exists and is executable.

    Returns:
        Tuple of (is_valid, script_path)
    """
    script_dir = Path(__file__).parent
    hook_script = script_dir / "post_commit_hook.py"

    if not hook_script.exists():
        log_error(f"Hook script not found: {hook_script}")
        log_error("Please ensure Heimdall MCP Server is properly installed.")
        return False, hook_script

    if not hook_script.is_file():
        log_error(f"Hook script is not a file: {hook_script}")
        return False, hook_script

    # Check if script is executable (on Unix-like systems)
    try:
        import stat

        mode = hook_script.stat().st_mode
        if not (mode & stat.S_IXUSR):
            log_warning(f"Hook script is not executable: {hook_script}")
            log_info("Run: chmod +x {hook_script}")
    except Exception:
        pass  # Skip executable check on Windows

    return True, hook_script


def get_hook_status(
    repo_path: Path,
) -> Literal[
    "NO_HOOK", "HEIMDALL_INSTALLED", "HEIMDALL_NOT_EXECUTABLE", "OTHER_HOOK_EXISTS"
]:
    """
    Get current hook status.

    Args:
        repo_path: Repository path

    Returns:
        Hook status string
    """
    hook_file = repo_path / ".git" / "hooks" / "post-commit"

    if not hook_file.exists():
        return "NO_HOOK"

    try:
        content = hook_file.read_text(encoding="utf-8")
        if "Heimdall MCP Server" in content:
            import stat

            mode = hook_file.stat().st_mode
            if mode & stat.S_IXUSR:
                return "HEIMDALL_INSTALLED"
            else:
                return "HEIMDALL_NOT_EXECUTABLE"
        else:
            return "OTHER_HOOK_EXISTS"
    except Exception:
        return "OTHER_HOOK_EXISTS"


def show_status(repo_path: Path) -> None:
    """
    Show current hook status.

    Args:
        repo_path: Repository path
    """
    hook_file = repo_path / ".git" / "hooks" / "post-commit"
    status = get_hook_status(repo_path)

    log_info(f"Repository: {repo_path}")
    log_info(f"Hook file: {hook_file}")

    if status == "NO_HOOK":
        log_info("Status: No post-commit hook installed")
    elif status == "HEIMDALL_INSTALLED":
        log_success("Status: Heimdall post-commit hook is installed and active")
    elif status == "HEIMDALL_NOT_EXECUTABLE":
        log_warning("Status: Heimdall hook installed but not executable")
    elif status == "OTHER_HOOK_EXISTS":
        log_warning("Status: Different post-commit hook exists")
        if hook_file.exists():
            log_info("Existing hook preview:")
            try:
                content = hook_file.read_text(encoding="utf-8")
                lines = content.split("\n")
                for _i, line in enumerate(lines[:10]):
                    print(f"  {line}")
                if len(lines) > 10:
                    log_info(f"  ... (truncated, {len(lines)} total lines)")
            except Exception:
                log_warning("Could not read existing hook file")


def create_chained_hook(repo_path: Path, hook_script: Path) -> None:
    """
    Create chained hook that preserves existing functionality.

    Args:
        repo_path: Repository path
        hook_script: Path to Heimdall hook script
    """
    hook_file = repo_path / ".git" / "hooks" / "post-commit"
    backup_file = hook_file.with_suffix(".heimdall-backup")
    temp_file = hook_file.with_suffix(".tmp")

    # Create backup of existing hook
    hook_file.rename(backup_file)
    log_info(f"Backed up existing hook to: {backup_file}")

    # Create new chained hook
    chained_content = f'''#!/bin/bash
# Chained post-commit hook with Heimdall MCP Server integration
# Original hook preserved and executed first

set -e

# Execute original hook first
if [[ -f "{backup_file}" ]] && [[ -x "{backup_file}" ]]; then
    echo "Executing original post-commit hook..."
    "{backup_file}" "$@"
    original_exit_code=$?

    if [[ $original_exit_code -ne 0 ]]; then
        echo "Warning: Original hook exited with code $original_exit_code"
        # Continue with Heimdall hook even if original fails
    fi
fi

# Execute Heimdall hook
if [[ -f "{hook_script}" ]] && [[ -x "{hook_script}" ]]; then
    echo "Executing Heimdall incremental git loading..."
    "{hook_script}" "$@"
else
    echo "Warning: Heimdall hook script not found or not executable: {hook_script}"
fi

exit 0
'''

    # Write and make executable
    temp_file.write_text(chained_content, encoding="utf-8")
    import stat

    temp_file.chmod(
        temp_file.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    temp_file.rename(hook_file)

    log_success("Created chained hook preserving original functionality")


def install_hook(
    repo_path: Path, hook_script: Path, force: bool = False, dry_run: bool = False
) -> bool:
    """
    Install hook with various strategies based on current state.

    Args:
        repo_path: Repository path
        hook_script: Path to Heimdall hook script
        force: Force installation even if hooks exist
        dry_run: Show what would be done without making changes

    Returns:
        True if installation succeeded
    """
    hook_file = repo_path / ".git" / "hooks" / "post-commit"
    hooks_dir = repo_path / ".git" / "hooks"
    status = get_hook_status(repo_path)

    # Create hooks directory if it doesn't exist
    if not hooks_dir.exists():
        if dry_run:
            log_info(f"[DRY RUN] Would create hooks directory: {hooks_dir}")
        else:
            hooks_dir.mkdir(parents=True, exist_ok=True)
            log_info(f"Created hooks directory: {hooks_dir}")

    if status == "NO_HOOK":
        if dry_run:
            log_info("[DRY RUN] Would create new Heimdall post-commit hook")
            log_info(f"[DRY RUN] Target: {hook_file}")
        else:
            # Create symlink to our hook script
            if hook_file.exists():
                hook_file.unlink()
            hook_file.symlink_to(hook_script.resolve())
            log_success("Installed Heimdall post-commit hook")
        return True

    elif status == "HEIMDALL_INSTALLED":
        if force:
            if dry_run:
                log_info("[DRY RUN] Would reinstall Heimdall hook (forced)")
            else:
                if hook_file.exists():
                    hook_file.unlink()
                hook_file.symlink_to(hook_script.resolve())
                log_success("Reinstalled Heimdall post-commit hook (forced)")
            return True
        else:
            log_warning("Heimdall hook already installed. Use --force to reinstall.")
            return True

    elif status == "HEIMDALL_NOT_EXECUTABLE":
        if dry_run:
            log_info("[DRY RUN] Would fix hook permissions")
        else:
            import stat

            current_mode = hook_file.stat().st_mode
            hook_file.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            log_success("Fixed Heimdall hook permissions")
        return True

    elif status == "OTHER_HOOK_EXISTS":
        if force:
            if dry_run:
                log_info("[DRY RUN] Would create chained hook preserving existing hook")
                log_info("[DRY RUN] Existing hook would be backed up and chained")
            else:
                create_chained_hook(repo_path, hook_script)
            return True
        else:
            log_warning("Another post-commit hook already exists.")
            log_warning(
                "Use --force to create a chained hook that preserves existing functionality."
            )
            log_warning("Or manually integrate Heimdall hook with your existing hook.")
            return False


def uninstall_hook(repo_path: Path, dry_run: bool = False) -> bool:
    """
    Uninstall hook with proper backup restoration.

    Args:
        repo_path: Repository path
        dry_run: Show what would be done without making changes

    Returns:
        True if uninstallation succeeded
    """
    hook_file = repo_path / ".git" / "hooks" / "post-commit"
    backup_file = hook_file.with_suffix(".heimdall-backup")
    status = get_hook_status(repo_path)

    if status == "NO_HOOK":
        log_info("No post-commit hook to uninstall")
        return True

    elif status in ["HEIMDALL_INSTALLED", "HEIMDALL_NOT_EXECUTABLE"]:
        # Check if this is a chained hook with backup
        if backup_file.exists():
            if dry_run:
                log_info("[DRY RUN] Would restore original hook from backup")
                log_info(f"[DRY RUN] Backup: {backup_file}")
            else:
                hook_file.unlink()
                backup_file.rename(hook_file)
                log_success("Restored original post-commit hook from backup")
        else:
            if dry_run:
                log_info("[DRY RUN] Would remove Heimdall post-commit hook")
            else:
                hook_file.unlink()
                log_success("Removed Heimdall post-commit hook")
        return True

    elif status == "OTHER_HOOK_EXISTS":
        # Check if it's a chained hook with backup
        if backup_file.exists():
            if dry_run:
                log_info("[DRY RUN] Would restore original hook from backup")
                log_info(f"[DRY RUN] Backup: {backup_file}")
            else:
                hook_file.unlink()
                backup_file.rename(hook_file)
                log_success("Restored original post-commit hook from backup")
            return True
        else:
            log_warning("Found non-Heimdall post-commit hook")
            log_warning(
                "Manual removal required to avoid breaking existing functionality"
            )
            log_info(f"Hook file: {hook_file}")
            return False

    return False


def main() -> None:
    """Main entry point for the hook installer."""
    # Simple argument parsing if typer not available
    if not _has_rich:
        args = sys.argv[1:]

        # Default values
        action = "install"
        repo_path = Path.cwd()
        force = False
        dry_run = False

        # Parse simple arguments
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "--install":
                action = "install"
            elif arg == "--uninstall":
                action = "uninstall"
            elif arg == "--status":
                action = "status"
            elif arg == "--force":
                force = True
            elif arg == "--dry-run":
                dry_run = True
            elif arg in ["--help", "-h"]:
                show_usage()
                sys.exit(0)
            elif not arg.startswith("--"):
                repo_path = Path(arg).resolve()
            i += 1

        # Execute logic
        execute_action_cli(action, repo_path, force, dry_run)
    else:
        # Use typer for rich CLI experience
        app = typer.Typer(help="Heimdall Git Hook Installer")

        def install_cmd(
            repo_path: str = typer.Argument(".", help="Repository path"),
            force: bool = typer.Option(False, "--force", help="Force installation"),
            dry_run: bool = typer.Option(
                False, "--dry-run", help="Show what would be done"
            ),
        ) -> None:
            """Install Heimdall post-commit hook."""
            execute_action_cli("install", Path(repo_path).resolve(), force, dry_run)

        app.command("install")(install_cmd)

        def uninstall_cmd(
            repo_path: str = typer.Argument(".", help="Repository path"),
            dry_run: bool = typer.Option(
                False, "--dry-run", help="Show what would be done"
            ),
        ) -> None:
            """Uninstall Heimdall post-commit hook."""
            execute_action_cli("uninstall", Path(repo_path).resolve(), False, dry_run)

        app.command("uninstall")(uninstall_cmd)

        def status_cmd(
            repo_path: str = typer.Argument(".", help="Repository path"),
        ) -> None:
            """Show hook installation status."""
            execute_action_cli("status", Path(repo_path).resolve(), False, False)

        app.command("status")(status_cmd)

        app()


def execute_action(action: str, repo_path: Path, force: bool, dry_run: bool) -> bool:
    """
    Execute the specified action.

    Args:
        action: Action to perform (install/uninstall/status)
        repo_path: Repository path
        force: Force flag
        dry_run: Dry run flag

    Returns:
        True if successful, False otherwise
    """
    # Validate inputs
    if not validate_git_repo(repo_path):
        return False

    hook_valid, hook_script = validate_hook_script()
    if not hook_valid:
        return False

    # Execute action
    try:
        if action == "install":
            success = install_hook(repo_path, hook_script, force, dry_run)
            if success and not dry_run:
                log_success("Hook installation completed successfully")
                log_info(
                    "The hook will automatically process new commits for memory storage"
                )
                log_info("Hook logs are written to: .heimdall/monitor.log")
            return success

        elif action == "uninstall":
            return uninstall_hook(repo_path, dry_run)

        elif action == "status":
            show_status(repo_path)
            return True

        else:
            log_error(f"Unknown action: {action}")
            return False

    except Exception as e:
        log_error(f"Unexpected error: {e}")
        return False


def execute_action_cli(
    action: str, repo_path: Path, force: bool, dry_run: bool
) -> None:
    """
    Execute action with CLI behavior (exits on completion).

    Args:
        action: Action to perform (install/uninstall/status)
        repo_path: Repository path
        force: Force flag
        dry_run: Dry run flag
    """
    success = execute_action(action, repo_path, force, dry_run)
    if action == "status":
        sys.exit(0)  # Status always succeeds
    else:
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
