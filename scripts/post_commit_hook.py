#!/usr/bin/env python3
"""
Heimdall MCP Server - Post-Commit Hook (Python Implementation)

Automatically processes the latest commit for memory storage using the
shared Qdrant architecture and centralized configuration system.

This hook replaces the bash implementation with cross-platform Python code
that directly integrates with the cognitive memory system without Docker
container dependencies.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Graceful imports with fallbacks
try:
    import git
except ImportError:
    print("Heimdall: WARNING: GitPython not available, cannot process git hooks")
    sys.exit(0)

try:
    from cognitive_memory.core.config import get_project_paths
    from cognitive_memory.main import initialize_system
    from interfaces.cli import CognitiveCLI
except ImportError as e:
    print(f"Heimdall: WARNING: Cannot import cognitive memory system: {e}")
    sys.exit(0)


def log_message(paths: Any, message: str, is_error: bool = False) -> None:
    """
    Log message to both console and file with colors.

    Args:
        paths: ProjectPaths object with log file location
        message: Message to log
        is_error: Whether this is an error message
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"

    # ANSI color codes
    BLUE = "\033[34m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    # Print to console with colors (visible in git output)
    if is_error:
        prefix_colored = f"{RED}ERROR{RESET}"
        message_colored = f"{RED}{message}{RESET}"
    elif "memory loaded" in message or "memories loaded" in message:
        prefix_colored = f"{GREEN}SUCCESS{RESET}"
        message_colored = f"{GREEN}{message}{RESET}"
    elif "completed" in message:
        prefix_colored = f"{BLUE}INFO{RESET}"
        message_colored = f"{BLUE}{message}{RESET}"
    else:
        prefix_colored = f"{YELLOW}INFO{RESET}"
        message_colored = message

    print(f"{BOLD}Heimdall{RESET} [{prefix_colored}]: {message_colored}")

    # Log to file without colors
    try:
        with open(paths.log_file, "a", encoding="utf-8") as f:
            f.write(f"{log_entry}\n")
    except Exception:
        pass  # Don't break hook if logging fails


def main() -> None:
    """
    Main post-commit hook execution.

    This function handles the complete post-commit processing workflow:
    1. Validate git repository and get latest commit info
    2. Initialize cognitive memory system
    3. Load the latest commit into memory via direct function call
    4. Log results appropriately

    Always exits with code 0 to prevent breaking git operations.
    """
    paths = None

    try:
        # Find git repository root using GitPython
        try:
            repo = git.Repo(search_parent_directories=True)
            repo_root = Path(repo.working_dir)
        except git.exc.InvalidGitRepositoryError:
            print("Heimdall: ERROR: Not in a git repository")
            sys.exit(0)
        except Exception as e:
            print(f"Heimdall: ERROR: Failed to access git repository: {e}")
            sys.exit(0)

        # Get project paths for logging
        paths = get_project_paths(repo_root)

        # Get latest commit info
        try:
            latest_commit = repo.head.commit
            commit_hash = latest_commit.hexsha
            commit_short = commit_hash[:8]
        except Exception as e:
            log_message(paths, f"Failed to get latest commit info: {e}", is_error=True)
            sys.exit(0)

        # Initialize cognitive memory system and execute git loading (suppress verbose output)
        try:
            import contextlib
            import io
            import os

            # Suppress all logging during the operation
            original_log_level = os.environ.get("LOG_LEVEL", "INFO")
            os.environ["LOG_LEVEL"] = "ERROR"

            # Also disable loguru directly
            try:
                from loguru import logger

                logger.disable("")  # Disable all loguru logging
            except ImportError:
                pass

            # Capture stdout to count memories loaded
            captured_output = io.StringIO()

            with contextlib.redirect_stdout(captured_output):
                cognitive_system = initialize_system()
                cli = CognitiveCLI(cognitive_system)

                # Use load_git_patterns which handles incremental loading automatically
                # with max_commits=1 to process only the latest commit
                success = cli.load_git_patterns(
                    repo_path=str(repo_root),
                    dry_run=False,
                    max_commits=1,  # Only process the latest commit
                )

            # Restore original log level and re-enable loguru
            os.environ["LOG_LEVEL"] = original_log_level
            try:
                from loguru import logger

                logger.enable("")  # Re-enable loguru logging
            except ImportError:
                pass

            # Parse the output to extract memory count
            output = captured_output.getvalue()
            memories_loaded = 0
            if "Memories loaded:" in output:
                for line in output.split("\n"):
                    if "Memories loaded:" in line:
                        try:
                            memories_loaded = int(
                                line.split("Memories loaded:")[1].strip()
                            )
                        except (IndexError, ValueError):
                            pass

            if success:
                if memories_loaded > 0:
                    memory_word = "memory" if memories_loaded == 1 else "memories"
                    log_message(
                        paths,
                        f"Processed commit {commit_short}: {memories_loaded} {memory_word} loaded",
                    )
                else:
                    log_message(
                        paths,
                        f"Processed commit {commit_short}: no new memories (incremental)",
                    )
            else:
                log_message(
                    paths,
                    f"WARNING: Failed to process commit {commit_short}",
                    is_error=True,
                )

        except Exception as e:
            log_message(
                paths,
                f"ERROR: Failed to process commit {commit_short}: {str(e)}",
                is_error=True,
            )

        log_message(paths, "Post-commit hook completed")

    except Exception as e:
        error_msg = f"Unexpected error in post-commit hook: {str(e)}"
        if paths:
            log_message(paths, error_msg, is_error=True)
        else:
            print(f"Heimdall: ERROR: {error_msg}")

    # Always exit 0 to never break git operations
    sys.exit(0)


if __name__ == "__main__":
    main()
