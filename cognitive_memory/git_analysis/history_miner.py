"""Secure git history mining with GitPython integration.

This module provides secure git repository analysis using GitPython library
exclusively. All operations are performed without shell command execution,
implementing comprehensive security controls and error handling.

Security Features:
- No shell command execution (GitPython API only)
- Repository path validation before access
- Comprehensive error handling and logging
- Resource cleanup and connection management
- Input validation for all git data
"""

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from git import GitCommandError, InvalidGitRepositoryError, Repo
    from git.objects import Commit as GitCommit

    GITPYTHON_AVAILABLE = True
except ImportError:
    GITPYTHON_AVAILABLE = False
    Repo = type(None)  # type: ignore
    GitCommit = type(None)  # type: ignore
    InvalidGitRepositoryError = Exception  # type: ignore
    GitCommandError = Exception  # type: ignore

from loguru import logger

from .commit import Commit, FileChange
from .security import (
    validate_repository_path,
)


class GitHistoryMiner:
    """Secure git history mining with comprehensive security controls.

    This class provides safe git repository analysis using GitPython
    exclusively, with no shell command execution and comprehensive
    security validation.

    Security Features:
    - Repository path validation before access
    - GitPython API only (no subprocess/shell)
    - Comprehensive error handling
    - Resource cleanup and connection management
    - Input sanitization for all git data
    """

    def __init__(self, repository_path: str):
        """Initialize git history miner with security validation.

        Args:
            repository_path: Path to git repository

        Raises:
            ImportError: If GitPython is not available
            ValueError: If repository path is invalid or insecure
            InvalidGitRepositoryError: If path is not a valid git repository
        """
        if not GITPYTHON_AVAILABLE:
            logger.error("GitPython library not available")
            raise ImportError("GitPython library is required but not installed")

        # Validate repository path for security
        if not validate_repository_path(repository_path):
            logger.error("Repository path validation failed", path=repository_path)
            raise ValueError(f"Invalid or insecure repository path: {repository_path}")

        self.repository_path = Path(repository_path).resolve()
        self.repo: Repo | None = None

        # Initialize repository connection
        try:
            self.repo = Repo(str(self.repository_path))
            logger.info(
                "Git repository initialized successfully",
                path=str(self.repository_path),
            )
        except InvalidGitRepositoryError as e:
            logger.error(
                "Invalid git repository", path=str(self.repository_path), error=str(e)
            )
            # Don't raise - let validate_repository() handle this
            self.repo = None
        except Exception as e:
            logger.error(
                "Failed to initialize git repository",
                path=str(self.repository_path),
                error=str(e),
            )
            # Don't raise - let validate_repository() handle this
            self.repo = None

    def __enter__(self) -> "GitHistoryMiner":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit with cleanup."""
        self.close()

    def close(self) -> None:
        """Clean up resources."""
        if self.repo:
            try:
                self.repo.close()
                logger.debug("Git repository connection closed")
            except Exception as e:
                logger.warning("Error closing git repository", error=str(e))
            finally:
                self.repo = None

    def validate_repository(self) -> bool:
        """Validate repository access and structure.

        Returns:
            True if repository is valid and accessible
        """
        try:
            if not self.repo:
                logger.warning("Repository not initialized")
                return False

            # Check if repository has commits
            try:
                list(self.repo.iter_commits(max_count=1))
            except Exception:
                logger.warning("Repository has no commits or is corrupted")
                return False

            # Check if we can access the HEAD
            try:
                _ = self.repo.head.commit
            except Exception:
                logger.warning("Cannot access repository HEAD")
                return False

            logger.debug("Repository validation successful")
            return True

        except Exception as e:
            logger.error("Repository validation failed", error=str(e))
            return False

    def extract_commit_history(
        self,
        max_commits: int = 1000,
        since_date: datetime | None = None,
        until_date: datetime | None = None,
        branch: str | None = None,
        since_commit: str | None = None,
    ) -> Iterator[Commit]:
        """Extract commit history with security controls.

        Args:
            max_commits: Maximum number of commits to extract (security limit)
            since_date: Extract commits since this date
            until_date: Extract commits until this date
            branch: Branch to extract from (defaults to current branch)
            since_commit: Extract commits since this commit hash (incremental mode)

        Yields:
            Commit: Validated commit objects

        Raises:
            ValueError: If repository is not valid or since_commit is invalid
            GitCommandError: If git operations fail
        """
        if not self.validate_repository():
            raise ValueError("Repository validation failed")

        try:
            # Security: limit max_commits to prevent memory exhaustion
            if max_commits is not None and max_commits > 10000:
                logger.warning(
                    "Max commits limited to 10000 for security", requested=max_commits
                )
                max_commits = 10000

            # Build commit iteration parameters
            kwargs: dict[str, Any] = {"max_count": max_commits}

            # Handle incremental mode with since_commit
            if since_commit is not None:
                # Validate commit hash exists in repository
                if not self._validate_commit_hash(since_commit):
                    raise ValueError(
                        f"Invalid or non-existent commit hash: {since_commit}"
                    )

                # Use git revision range syntax: since_commit..HEAD
                # This excludes the since_commit itself (we already processed it)
                if branch:
                    kwargs["rev"] = f"{since_commit}..{branch}"
                else:
                    kwargs["rev"] = f"{since_commit}..HEAD"

                # Remove date filters when using since_commit (git handles ordering)
                since_date = None
                until_date = None
            elif branch:
                kwargs["rev"] = branch

            if since_date:
                kwargs["since"] = since_date

            if until_date:
                kwargs["until"] = until_date

            logger.info(
                "Starting commit history extraction",
                max_commits=max_commits,
                since_date=since_date,
                until_date=until_date,
                branch=branch,
                since_commit=since_commit,
            )

            commit_count = 0

            # Extract commits using GitPython API
            if self.repo is None:
                raise ValueError("Repository not initialized")
            for commit in self.repo.iter_commits(**kwargs):
                try:
                    commit_obj = self._convert_commit_to_object(commit)
                    if commit_obj:
                        yield commit_obj
                        commit_count += 1

                        # Log progress periodically
                        if commit_count % 100 == 0:
                            logger.debug("Processed commits", count=commit_count)

                except Exception as e:
                    logger.warning(
                        "Failed to process commit",
                        commit_hash=commit.hexsha,
                        error=str(e),
                    )
                    continue

            logger.info(
                "Commit history extraction completed", total_commits=commit_count
            )

        except GitCommandError as e:
            logger.error("Git command failed during history extraction", error=str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error during history extraction", error=str(e))
            raise

    def _convert_commit_to_object(self, commit: GitCommit) -> Commit | None:
        """Convert GitPython commit to Commit object with validation.

        Args:
            commit: GitPython commit object

        Returns:
            Validated Commit object or None if conversion fails
        """
        try:
            # Extract basic commit information
            commit_hash = commit.hexsha
            message = commit.message.strip()
            author_name = commit.author.name
            author_email = commit.author.email
            timestamp = datetime.fromtimestamp(commit.committed_date)

            # Extract parent hashes
            parent_hashes = [parent.hexsha for parent in commit.parents]

            # Extract file changes
            file_changes = []
            try:
                # Get file changes from commit
                if commit.parents:
                    # Use commit.stats for line counts (much more reliable)
                    file_stats = {}
                    try:
                        if hasattr(commit, "stats") and commit.stats.files:
                            file_stats = commit.stats.files
                    except Exception as e:
                        logger.debug(
                            "Failed to get commit stats",
                            commit_hash=commit_hash,
                            error=str(e),
                        )

                    # Get change types from diff
                    diffs = commit.parents[0].diff(commit)
                    for diff in diffs:
                        try:
                            # Determine change type and file path
                            if diff.new_file:
                                change_type = "A"  # Added
                                file_path = diff.b_path
                            elif diff.deleted_file:
                                change_type = "D"  # Deleted
                                file_path = diff.a_path
                            elif diff.renamed_file:
                                change_type = "R"  # Renamed
                                file_path = diff.b_path
                            else:
                                change_type = "M"  # Modified
                                file_path = diff.a_path or diff.b_path

                            if not file_path:
                                continue

                            # Get line changes from stats if available
                            lines_added = 0
                            lines_deleted = 0
                            if file_path in file_stats:
                                lines_added = file_stats[file_path].get("insertions", 0)
                                lines_deleted = file_stats[file_path].get(
                                    "deletions", 0
                                )

                            # Create file change
                            file_change = FileChange(
                                file_path=file_path,
                                change_type=change_type,
                                lines_added=lines_added,
                                lines_deleted=lines_deleted,
                            )
                            file_changes.append(file_change)

                        except Exception as e:
                            logger.debug(
                                "Failed to process diff",
                                commit_hash=commit_hash,
                                error=str(e),
                            )
                            continue
                else:
                    # Initial commit - all files are added
                    for item in commit.tree.traverse():
                        if item.type == "blob":  # type: ignore  # Only files
                            try:
                                file_change = FileChange(
                                    file_path=str(item.path),  # type: ignore
                                    change_type="A",
                                    lines_added=0,
                                    lines_deleted=0,
                                )
                                file_changes.append(file_change)
                            except Exception as e:
                                logger.debug(
                                    "Failed to process initial commit file",
                                    file_path=str(item.path),  # type: ignore
                                    commit_hash=commit_hash,
                                    error=str(e),
                                )
                                continue
            except Exception as e:
                logger.debug(
                    "Failed to extract file changes",
                    commit_hash=commit_hash,
                    error=str(e),
                )
                file_changes = []

            # Create and validate commit object
            message_str = (
                message
                if isinstance(message, str)
                else message.decode("utf-8", errors="ignore")
            )
            author_name_str = author_name or "Unknown"
            author_email_str = author_email or "unknown@example.com"

            return Commit(
                hash=commit_hash,
                message=message_str,
                author_name=author_name_str,
                author_email=author_email_str,
                timestamp=timestamp,
                file_changes=file_changes,
                parent_hashes=parent_hashes,
            )

        except Exception as e:
            logger.warning(
                "Failed to convert commit to object",
                commit_hash=getattr(commit, "hexsha", "unknown"),
                error=str(e),
            )
            return None

    def _validate_commit_hash(self, commit_hash: str) -> bool:
        """Validate that a commit hash exists in the repository.

        Args:
            commit_hash: The commit hash to validate

        Returns:
            True if commit exists and is valid, False otherwise
        """
        try:
            if not self.repo:
                return False

            # Validate hash format (SHA-1: 40 chars, SHA-256: 64 chars, or partial)
            if not isinstance(commit_hash, str) or len(commit_hash.strip()) < 4:
                return False

            commit_hash = commit_hash.strip()
            if not all(c in "0123456789abcdefABCDEF" for c in commit_hash):
                return False

            # Try to resolve the commit
            self.repo.commit(commit_hash)
            return True

        except Exception as e:
            logger.debug(
                "Commit hash validation failed", commit_hash=commit_hash, error=str(e)
            )
            return False

    def get_repository_stats(self) -> dict[str, Any]:
        """Get basic repository statistics with security controls.

        Returns:
            Dictionary containing repository statistics
        """
        # Always return basic structure, even if validation fails
        stats = {
            "repository_path": str(self.repository_path),
            "total_commits": 0,
            "total_branches": 0,
            "total_tags": 0,
            "active_branch": None,
            "last_commit_date": None,
            "first_commit_date": None,
        }

        if not self.validate_repository():
            return stats

        try:
            # Count commits (limited for security)
            try:
                if self.repo is None:
                    raise ValueError("Repository not initialized")
                commits = list(self.repo.iter_commits(max_count=10000))
                stats["total_commits"] = len(commits)

                if commits:
                    stats["last_commit_date"] = datetime.fromtimestamp(
                        commits[0].committed_date
                    )
                    stats["first_commit_date"] = datetime.fromtimestamp(
                        commits[-1].committed_date
                    )
            except Exception as e:
                logger.debug("Failed to count commits", error=str(e))

            # Count branches
            try:
                if self.repo is None:
                    raise ValueError("Repository not initialized")
                stats["total_branches"] = len(list(self.repo.branches))
            except Exception as e:
                logger.debug("Failed to count branches", error=str(e))

            # Count tags
            try:
                if self.repo is None:
                    raise ValueError("Repository not initialized")
                stats["total_tags"] = len(list(self.repo.tags))
            except Exception as e:
                logger.debug("Failed to count tags", error=str(e))

            # Get active branch
            try:
                if self.repo is None:
                    raise ValueError("Repository not initialized")
                stats["active_branch"] = self.repo.active_branch.name
            except Exception as e:
                logger.debug("Failed to get active branch", error=str(e))

            logger.debug("Repository statistics collected", stats=stats)
            return stats

        except Exception as e:
            logger.error("Failed to collect repository statistics", error=str(e))
            return {}


# Utility functions for external use


def create_git_history_miner(repository_path: str) -> GitHistoryMiner:
    """Create a GitHistoryMiner instance with error handling.

    Args:
        repository_path: Path to git repository

    Returns:
        GitHistoryMiner instance

    Raises:
        ImportError: If GitPython is not available
        ValueError: If repository path is invalid
    """
    try:
        return GitHistoryMiner(repository_path)
    except Exception as e:
        logger.error(
            "Failed to create GitHistoryMiner", path=repository_path, error=str(e)
        )
        raise


def validate_git_repository(repository_path: str) -> bool:
    """Validate if path contains a valid git repository.

    Args:
        repository_path: Path to validate

    Returns:
        True if valid git repository, False otherwise
    """
    try:
        with create_git_history_miner(repository_path) as miner:
            return miner.validate_repository()
    except Exception:
        return False
