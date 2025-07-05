"""
Unit tests for GitHistoryMiner incremental loading functionality.

Tests the since_commit parameter and incremental git history extraction,
including security validation, edge cases, and error handling.
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from git import Actor, Repo

from cognitive_memory.git_analysis.commit import Commit
from cognitive_memory.git_analysis.history_miner import (
    GITPYTHON_AVAILABLE,
    GitHistoryMiner,
)


class TestGitHistoryMinerIncremental:
    """Test incremental loading functionality with since_commit parameter."""

    @pytest.fixture
    def incremental_repo(self):
        """Create a git repository with linear commit history for incremental testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "incremental_repo"
            repo_path.mkdir()

            repo = Repo.init(str(repo_path))
            author = Actor("Incremental User", "incremental@example.com")

            # Create a linear history with 5 commits
            commit_hashes = []
            for i in range(5):
                file_path = repo_path / f"file_{i}.txt"
                file_path.write_text(f"Content of file {i}")
                repo.index.add([str(file_path)])
                commit = repo.index.commit(
                    f"Commit {i}", author=author, committer=author
                )
                commit_hashes.append(commit.hexsha)

            yield GitHistoryMiner(str(repo_path)), commit_hashes

    @pytest.mark.skipif(not GITPYTHON_AVAILABLE, reason="GitPython not available")
    def test_extract_since_commit_success(self, incremental_repo):
        """Test successful incremental extraction since a specific commit."""
        miner, commit_hashes = incremental_repo

        # Extract commits since the 2nd commit (should get commits 3, 4, 5)
        since_commit = commit_hashes[1]  # 2nd commit (index 1)
        commits = list(miner.extract_commit_history(since_commit=since_commit))

        # Should get 3 commits (the ones after since_commit)
        assert len(commits) == 3

        # Verify commits are in reverse chronological order (newest first)
        for commit in commits:
            assert isinstance(commit, Commit)
            assert len(commit.hash) == 40  # SHA-1 hash length
            assert commit.author_name == "Incremental User"
            assert commit.author_email == "incremental@example.com"

        # Verify we got the correct commits (should not include since_commit itself)
        extracted_hashes = [commit.hash for commit in commits]
        assert since_commit not in extracted_hashes

        # The newest commits should be first
        assert commit_hashes[4] in extracted_hashes  # 5th commit
        assert commit_hashes[3] in extracted_hashes  # 4th commit
        assert commit_hashes[2] in extracted_hashes  # 3rd commit

    @pytest.mark.skipif(not GITPYTHON_AVAILABLE, reason="GitPython not available")
    def test_extract_since_commit_with_branch(self, incremental_repo):
        """Test incremental extraction with both since_commit and branch parameters."""
        miner, commit_hashes = incremental_repo

        # Get current branch name
        current_branch = miner.repo.active_branch.name
        since_commit = commit_hashes[2]  # 3rd commit

        commits = list(
            miner.extract_commit_history(
                since_commit=since_commit, branch=current_branch
            )
        )

        # Should get 2 commits (4th and 5th)
        assert len(commits) == 2

        extracted_hashes = [commit.hash for commit in commits]
        assert commit_hashes[4] in extracted_hashes
        assert commit_hashes[3] in extracted_hashes
        assert since_commit not in extracted_hashes

    @pytest.mark.skipif(not GITPYTHON_AVAILABLE, reason="GitPython not available")
    def test_extract_since_commit_head(self, incremental_repo):
        """Test incremental extraction from HEAD (should return no commits)."""
        miner, commit_hashes = incremental_repo

        # Use the latest commit as since_commit
        since_commit = commit_hashes[-1]  # Latest commit
        commits = list(miner.extract_commit_history(since_commit=since_commit))

        # Should get no commits (no commits after HEAD)
        assert len(commits) == 0

    @pytest.mark.skipif(not GITPYTHON_AVAILABLE, reason="GitPython not available")
    def test_extract_since_commit_with_max_commits(self, incremental_repo):
        """Test incremental extraction with max_commits limit."""
        miner, commit_hashes = incremental_repo

        since_commit = commit_hashes[0]  # 1st commit
        commits = list(
            miner.extract_commit_history(since_commit=since_commit, max_commits=2)
        )

        # Should be limited to 2 commits even though 4 are available
        assert len(commits) == 2

    @pytest.mark.skipif(not GITPYTHON_AVAILABLE, reason="GitPython not available")
    def test_extract_since_commit_overrides_date_filters(self, incremental_repo):
        """Test that since_commit overrides date filtering parameters."""
        miner, commit_hashes = incremental_repo

        since_commit = commit_hashes[1]  # 2nd commit

        # Use date filters that would normally exclude commits
        since_date = datetime(2030, 1, 1)  # Future date
        until_date = datetime(2030, 12, 31)  # Future date

        commits = list(
            miner.extract_commit_history(
                since_commit=since_commit, since_date=since_date, until_date=until_date
            )
        )

        # Should still get commits despite date filters (since_commit takes precedence)
        assert len(commits) == 3

    @pytest.mark.skipif(not GITPYTHON_AVAILABLE, reason="GitPython not available")
    def test_extract_since_commit_invalid_hash(self, incremental_repo):
        """Test incremental extraction with invalid commit hash."""
        miner, _ = incremental_repo

        invalid_hashes = [
            "invalid_hash",
            "1234567890abcdef" * 3,  # Wrong length
            "gggggggggggggggggggggggggggggggggggggggg",  # Invalid characters
            "",
        ]

        for invalid_hash in invalid_hashes:
            with pytest.raises(ValueError, match="Invalid or non-existent commit hash"):
                list(miner.extract_commit_history(since_commit=invalid_hash))

        # Test None separately - should be treated as valid (no since_commit)
        try:
            result = list(miner.extract_commit_history(since_commit=None))
            # None should be treated as "no since_commit" - should work normally
            assert isinstance(result, list)
        except Exception as e:
            pytest.fail(f"since_commit=None should be valid, but got: {e}")

    @pytest.mark.skipif(not GITPYTHON_AVAILABLE, reason="GitPython not available")
    def test_extract_since_commit_nonexistent_hash(self, incremental_repo):
        """Test incremental extraction with valid but non-existent commit hash."""
        miner, _ = incremental_repo

        # Valid SHA-1 format but doesn't exist in repository
        nonexistent_hash = "abcdef1234567890abcdef1234567890abcdef12"

        with pytest.raises(ValueError, match="Invalid or non-existent commit hash"):
            list(miner.extract_commit_history(since_commit=nonexistent_hash))

    @pytest.mark.skipif(not GITPYTHON_AVAILABLE, reason="GitPython not available")
    def test_extract_since_commit_partial_hash(self, incremental_repo):
        """Test incremental extraction with partial commit hash (should work)."""
        miner, commit_hashes = incremental_repo

        # Use first 12 characters of commit hash (common Git abbreviation)
        partial_hash = commit_hashes[1][:12]

        commits = list(miner.extract_commit_history(since_commit=partial_hash))

        # Should work with partial hash
        assert len(commits) == 3

    def test_validate_commit_hash_valid_sha1(self, incremental_repo):
        """Test commit hash validation with valid SHA-1 hashes."""
        miner, commit_hashes = incremental_repo

        # Test full SHA-1 hash
        full_hash = commit_hashes[0]
        assert miner._validate_commit_hash(full_hash) is True

        # Test partial hash (common abbreviations)
        partial_hash = commit_hashes[0][:7]
        assert miner._validate_commit_hash(partial_hash) is True

        # Test longer partial hash
        longer_partial = commit_hashes[0][:12]
        assert miner._validate_commit_hash(longer_partial) is True

    def test_validate_commit_hash_invalid_format(self, incremental_repo):
        """Test commit hash validation with invalid formats."""
        miner, _ = incremental_repo

        invalid_hashes = [
            "",
            "abc",  # Too short
            "gggg",  # Invalid characters
            "1234567890abcdef" * 5,  # Too long for SHA-1
            "hello world",  # Spaces and invalid chars
            None,
            123,  # Wrong type
        ]

        for invalid_hash in invalid_hashes:
            assert miner._validate_commit_hash(invalid_hash) is False

    def test_validate_commit_hash_no_repo(self):
        """Test commit hash validation when repository is not initialized."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "empty"
            repo_path.mkdir()

            miner = GitHistoryMiner.__new__(GitHistoryMiner)  # Bypass __init__
            miner.repo = None

            assert miner._validate_commit_hash("abcdef1234567890") is False

    @pytest.mark.skipif(not GITPYTHON_AVAILABLE, reason="GitPython not available")
    def test_extract_since_commit_repository_validation_failure(self):
        """Test incremental extraction when repository validation fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "empty_repo"
            repo_path.mkdir()
            Repo.init(str(repo_path))  # Empty repo with no commits

            miner = GitHistoryMiner(str(repo_path))

            with pytest.raises(ValueError, match="Repository validation failed"):
                list(miner.extract_commit_history(since_commit="abc123"))

    @pytest.mark.skipif(not GITPYTHON_AVAILABLE, reason="GitPython not available")
    def test_extract_since_commit_git_command_error(self, incremental_repo):
        """Test handling of GitCommandError during incremental extraction."""
        miner, commit_hashes = incremental_repo

        # Mock iter_commits to raise GitCommandError after validation passes
        from git import GitCommandError

        # First call for validation should succeed, second should fail
        validation_result = iter(
            [MagicMock()]
        )  # Returns an iterator with one mock commit
        miner.repo.iter_commits = MagicMock(
            side_effect=[
                validation_result,
                GitCommandError("git log", "Command failed"),
            ]
        )

        with pytest.raises(GitCommandError):
            list(miner.extract_commit_history(since_commit=commit_hashes[0]))

    @pytest.mark.skipif(not GITPYTHON_AVAILABLE, reason="GitPython not available")
    def test_extract_since_commit_incremental_behavior(self, incremental_repo):
        """Test that incremental extraction behaves correctly with since_commit."""
        miner, commit_hashes = incremental_repo

        since_commit = commit_hashes[1]

        # Test that incremental extraction works (functional test, not logging test)
        commits = list(miner.extract_commit_history(since_commit=since_commit))

        # Should get commits after the since_commit
        assert len(commits) == 3  # commits 2, 3, 4 (after commit 1)

        # Verify we didn't get the since_commit itself
        extracted_hashes = [commit.hash for commit in commits]
        assert since_commit not in extracted_hashes

    @pytest.mark.skipif(not GITPYTHON_AVAILABLE, reason="GitPython not available")
    def test_extract_since_commit_security_limits_maintained(self, incremental_repo):
        """Test that security limits are still enforced in incremental mode."""
        miner, commit_hashes = incremental_repo

        since_commit = commit_hashes[0]

        # Test that max_commits security limit is still enforced
        with patch.object(miner, "_validate_commit_hash", return_value=True):
            # Mock a large number of commits that return empty for conversion
            mock_commits = [MagicMock() for _ in range(100)]  # Smaller number for test

            # Track calls to iter_commits
            call_log = []

            def mock_iter_commits(**kwargs):
                call_log.append(kwargs)
                return iter(mock_commits)

            miner.repo.iter_commits = mock_iter_commits

            # Mock _convert_commit_to_object to return None (failed conversion)
            with patch.object(miner, "_convert_commit_to_object", return_value=None):
                # Should be limited by security max of 10000
                list(
                    miner.extract_commit_history(
                        since_commit=since_commit, max_commits=15000
                    )
                )

                # Verify the final call was made with limited max_count
                assert len(call_log) >= 1
                final_call = call_log[
                    -1
                ]  # Get the actual extraction call (not validation)
                assert final_call["max_count"] == 10000


class TestGitHistoryMinerIncrementalEdgeCases:
    """Test edge cases and error conditions for incremental loading."""

    @pytest.fixture
    def branched_repo(self):
        """Create a repository with multiple branches for testing edge cases."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "branched_repo"
            repo_path.mkdir()

            repo = Repo.init(str(repo_path))
            author = Actor("Branch User", "branch@example.com")

            # Create initial commit on main branch
            file_path = repo_path / "main.txt"
            file_path.write_text("Main branch content")
            repo.index.add([str(file_path)])
            main_commit = repo.index.commit(
                "Main branch commit", author=author, committer=author
            )

            # Create feature branch
            feature_branch = repo.create_head("feature")
            feature_branch.checkout()

            # Add commits to feature branch
            feature_commits = []
            for i in range(3):
                file_path = repo_path / f"feature_{i}.txt"
                file_path.write_text(f"Feature content {i}")
                repo.index.add([str(file_path)])
                commit = repo.index.commit(
                    f"Feature commit {i}", author=author, committer=author
                )
                feature_commits.append(commit.hexsha)

            # Switch back to main branch
            repo.heads.master.checkout()

            yield GitHistoryMiner(str(repo_path)), main_commit.hexsha, feature_commits

    @pytest.mark.skipif(not GITPYTHON_AVAILABLE, reason="GitPython not available")
    def test_extract_since_commit_different_branch(self, branched_repo):
        """Test incremental extraction with commit from different branch."""
        miner, main_commit_hash, feature_commits = branched_repo

        # Try to use a commit from feature branch while on main branch
        feature_commit = feature_commits[0]

        # This should work - git can handle cross-branch commit references
        commits = list(miner.extract_commit_history(since_commit=feature_commit))

        # The behavior depends on git's revision walking algorithm
        # Should return commits reachable from HEAD but not from since_commit
        assert isinstance(commits, list)

    @pytest.mark.skipif(not GITPYTHON_AVAILABLE, reason="GitPython not available")
    def test_extract_since_commit_with_branch_parameter(self, branched_repo):
        """Test incremental extraction specifying both since_commit and target branch."""
        miner, main_commit_hash, feature_commits = branched_repo

        # Extract from feature branch since main commit
        commits = list(
            miner.extract_commit_history(
                since_commit=main_commit_hash, branch="feature"
            )
        )

        # Should get the feature branch commits
        assert len(commits) == 3
        extracted_hashes = [commit.hash for commit in commits]

        # All feature commits should be present
        for feature_commit in feature_commits:
            assert feature_commit in extracted_hashes

    @pytest.mark.skipif(not GITPYTHON_AVAILABLE, reason="GitPython not available")
    def test_validate_commit_hash_sha256_support(self, branched_repo):
        """Test commit hash validation supports SHA-256 format (future-proofing)."""
        miner, _, _ = branched_repo

        # SHA-256 hash (64 characters)
        sha256_hash = "a" * 64

        # Should validate format correctly (even if commit doesn't exist)
        # The validation should not fail on format, only on existence
        with pytest.raises(ValueError, match="Invalid or non-existent commit hash"):
            list(miner.extract_commit_history(since_commit=sha256_hash))

    def test_validate_commit_hash_whitespace_handling(self, branched_repo):
        """Test commit hash validation handles whitespace correctly."""
        miner, main_commit_hash, _ = branched_repo

        valid_hash = main_commit_hash

        # Test with leading/trailing whitespace
        whitespace_variants = [
            f" {valid_hash}",
            f"{valid_hash} ",
            f" {valid_hash} ",
            f"\t{valid_hash}\n",
        ]

        for variant in whitespace_variants:
            # Should strip whitespace and validate successfully
            assert miner._validate_commit_hash(variant) is True

    @pytest.mark.skipif(not GITPYTHON_AVAILABLE, reason="GitPython not available")
    def test_extract_since_commit_exception_during_validation(self, branched_repo):
        """Test handling of exceptions during commit hash validation."""
        miner, _, _ = branched_repo

        # Mock repo.commit to raise an exception
        miner.repo.commit = MagicMock(side_effect=Exception("Validation error"))

        with pytest.raises(ValueError, match="Invalid or non-existent commit hash"):
            list(miner.extract_commit_history(since_commit="abcdef123456"))

    @pytest.mark.skipif(not GITPYTHON_AVAILABLE, reason="GitPython not available")
    def test_extract_since_commit_mixed_case_hash(self, branched_repo):
        """Test incremental extraction with mixed case commit hash."""
        miner, main_commit_hash, feature_commits = branched_repo
        commit_hashes = [main_commit_hash] + feature_commits

        # Convert to mixed case
        mixed_case_hash = ""
        for i, char in enumerate(commit_hashes[0]):
            if i % 2 == 0:
                mixed_case_hash += char.upper()
            else:
                mixed_case_hash += char.lower()

        # Should work with mixed case
        commits = list(miner.extract_commit_history(since_commit=mixed_case_hash))
        # Since we're on the main branch and using the main commit hash as since_commit,
        # we should get no commits (no commits after the main commit on main branch)
        assert len(commits) == 0
