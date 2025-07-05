#!/usr/bin/env python3
"""
End-to-end CLI integration tests for git hook commands.

This test validates the complete CLI integration of git hook commands
through the actual heimdall CLI interface, testing the full user workflow.
"""

import stat
import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.mark.slow
class TestGitHookCLIIntegration:
    """Test suite for git hook CLI integration."""

    @pytest.fixture
    def temp_git_repo(self):
        """Create a temporary git repository for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "test_repo"
            repo_path.mkdir()

            # Initialize git repository
            subprocess.run(["git", "init"], cwd=repo_path, check=True)
            subprocess.run(
                ["git", "config", "user.name", "Test User"], cwd=repo_path, check=True
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo_path,
                check=True,
            )

            # Create initial commit
            test_file = repo_path / "README.md"
            test_file.write_text("# Test Repository\n")
            subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True
            )

            yield repo_path

    @pytest.fixture
    def temp_git_repo_with_hook(self, temp_git_repo):
        """Create a temporary git repository with an existing hook."""
        hooks_dir = temp_git_repo / ".git" / "hooks"
        hooks_dir.mkdir(exist_ok=True)

        existing_hook = hooks_dir / "post-commit"
        existing_hook.write_text("#!/bin/bash\necho 'Existing hook executed'\n")
        existing_hook.chmod(existing_hook.stat().st_mode | stat.S_IXUSR)

        yield temp_git_repo

    def run_heimdall_command(self, args, cwd=None, check=True):
        """Run heimdall CLI command and return result."""
        cmd = ["python", "-m", "heimdall.cli"] + args
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=check
        )
        return result

    def test_git_hook_install_cli_fresh_repo(self, temp_git_repo):
        """Test git hook install command via CLI in fresh repository."""
        result = self.run_heimdall_command(["git-hook", "install", str(temp_git_repo)])

        assert result.returncode == 0
        assert (
            "Hook installation completed successfully" in result.stdout or result.stderr
        )

        # Verify hook was installed
        hook_file = temp_git_repo / ".git" / "hooks" / "post-commit"
        hook_script = temp_git_repo / ".git" / "hooks" / "heimdall_post_commit_hook.py"

        assert hook_file.exists()
        assert hook_script.exists()
        assert hook_script.stat().st_mode & stat.S_IXUSR

    def test_git_hook_install_cli_current_directory(self, temp_git_repo):
        """Test git hook install command via CLI using current directory."""
        result = self.run_heimdall_command(["git-hook", "install"], cwd=temp_git_repo)

        assert result.returncode == 0

        # Verify hook was installed
        hook_file = temp_git_repo / ".git" / "hooks" / "post-commit"
        assert hook_file.exists()

    def test_git_hook_install_cli_dry_run(self, temp_git_repo):
        """Test git hook install dry run via CLI."""
        result = self.run_heimdall_command(
            ["git-hook", "install", "--dry-run", str(temp_git_repo)]
        )

        assert result.returncode == 0
        assert "[DRY RUN]" in result.stdout or result.stderr

        # Verify no files were actually created
        hook_file = temp_git_repo / ".git" / "hooks" / "post-commit"
        assert not hook_file.exists()

    def test_git_hook_install_cli_force(self, temp_git_repo_with_hook):
        """Test git hook install with force flag via CLI."""
        result = self.run_heimdall_command(
            ["git-hook", "install", "--force", str(temp_git_repo_with_hook)]
        )

        assert result.returncode == 0

        # Verify chained hook was created
        hook_file = temp_git_repo_with_hook / ".git" / "hooks" / "post-commit"
        backup_file = hook_file.with_suffix(".heimdall-backup")

        assert hook_file.exists()
        assert backup_file.exists()

        content = hook_file.read_text()
        assert "Chained post-commit hook" in content

    def test_git_hook_install_cli_existing_hook_no_force(self, temp_git_repo_with_hook):
        """Test git hook install with existing hook without force flag."""
        result = self.run_heimdall_command(
            ["git-hook", "install", str(temp_git_repo_with_hook)], check=False
        )

        # Should fail with exit code 1
        assert result.returncode == 1
        assert (
            "Another post-commit hook already exists" in result.stdout or result.stderr
        )

    def test_git_hook_uninstall_cli_basic(self, temp_git_repo):
        """Test git hook uninstall command via CLI."""
        # Install hook first
        self.run_heimdall_command(["git-hook", "install", str(temp_git_repo)])

        # Verify it's installed
        hook_file = temp_git_repo / ".git" / "hooks" / "post-commit"
        assert hook_file.exists()

        # Uninstall
        result = self.run_heimdall_command(
            ["git-hook", "uninstall", str(temp_git_repo)]
        )

        assert result.returncode == 0
        assert not hook_file.exists()

    def test_git_hook_uninstall_cli_dry_run(self, temp_git_repo):
        """Test git hook uninstall dry run via CLI."""
        # Install hook first
        self.run_heimdall_command(["git-hook", "install", str(temp_git_repo)])

        hook_file = temp_git_repo / ".git" / "hooks" / "post-commit"
        assert hook_file.exists()

        # Dry run uninstall
        result = self.run_heimdall_command(
            ["git-hook", "uninstall", "--dry-run", str(temp_git_repo)]
        )

        assert result.returncode == 0
        assert "[DRY RUN]" in result.stdout or result.stderr

        # File should still exist
        assert hook_file.exists()

    def test_git_hook_uninstall_cli_with_backup_restore(self, temp_git_repo_with_hook):
        """Test git hook uninstall with backup restoration via CLI."""
        original_content = (
            temp_git_repo_with_hook / ".git" / "hooks" / "post-commit"
        ).read_text()

        # Install chained hook
        self.run_heimdall_command(
            ["git-hook", "install", "--force", str(temp_git_repo_with_hook)]
        )

        # Uninstall
        result = self.run_heimdall_command(
            ["git-hook", "uninstall", str(temp_git_repo_with_hook)]
        )

        assert result.returncode == 0

        # Check original hook was restored
        hook_file = temp_git_repo_with_hook / ".git" / "hooks" / "post-commit"
        assert hook_file.exists()
        assert hook_file.read_text() == original_content

    def test_git_hook_status_cli_no_hook(self, temp_git_repo):
        """Test git hook status command via CLI when no hook exists."""
        result = self.run_heimdall_command(["git-hook", "status", str(temp_git_repo)])

        assert result.returncode == 0
        assert "No post-commit hook installed" in result.stdout or result.stderr

    def test_git_hook_status_cli_heimdall_installed(self, temp_git_repo):
        """Test git hook status command via CLI when Heimdall hook is installed."""
        # Install hook first
        self.run_heimdall_command(["git-hook", "install", str(temp_git_repo)])

        result = self.run_heimdall_command(["git-hook", "status", str(temp_git_repo)])

        assert result.returncode == 0
        assert (
            "Heimdall post-commit hook is installed and active" in result.stdout
            or result.stderr
        )

    def test_git_hook_status_cli_other_hook_exists(self, temp_git_repo_with_hook):
        """Test git hook status command via CLI when other hook exists."""
        result = self.run_heimdall_command(
            ["git-hook", "status", str(temp_git_repo_with_hook)]
        )

        assert result.returncode == 0
        assert "Different post-commit hook exists" in result.stdout or result.stderr

    def test_git_hook_commands_invalid_repo(self):
        """Test git hook commands with invalid repository paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_path = Path(temp_dir) / "not_a_repo"
            invalid_path.mkdir()

            # All commands should fail with exit code 1
            commands = [
                ["git-hook", "install", str(invalid_path)],
                ["git-hook", "uninstall", str(invalid_path)],
                ["git-hook", "status", str(invalid_path)],
            ]

            for cmd in commands:
                result = self.run_heimdall_command(cmd, check=False)
                assert result.returncode == 1
                assert "Not a git repository" in result.stdout or result.stderr

    def test_git_hook_commands_help(self):
        """Test git hook commands help output."""
        commands = [
            ["git-hook", "install", "--help"],
            ["git-hook", "uninstall", "--help"],
            ["git-hook", "status", "--help"],
        ]

        for cmd in commands:
            result = self.run_heimdall_command(cmd)
            assert result.returncode == 0
            assert "Usage:" in result.stdout or result.stderr

    def test_git_hook_command_sequence(self, temp_git_repo):
        """Test complete git hook command sequence."""
        repo_path = str(temp_git_repo)

        # 1. Check initial status
        result = self.run_heimdall_command(["git-hook", "status", repo_path])
        assert result.returncode == 0
        assert "No post-commit hook installed" in result.stdout or result.stderr

        # 2. Install hook
        result = self.run_heimdall_command(["git-hook", "install", repo_path])
        assert result.returncode == 0

        # 3. Check status after installation
        result = self.run_heimdall_command(["git-hook", "status", repo_path])
        assert result.returncode == 0
        assert (
            "Heimdall post-commit hook is installed and active" in result.stdout
            or result.stderr
        )

        # 4. Uninstall hook
        result = self.run_heimdall_command(["git-hook", "uninstall", repo_path])
        assert result.returncode == 0

        # 5. Check final status
        result = self.run_heimdall_command(["git-hook", "status", repo_path])
        assert result.returncode == 0
        assert "No post-commit hook installed" in result.stdout or result.stderr

    def test_git_hook_error_messages(self):
        """Test that error messages are user-friendly."""
        # Test with non-existent path
        result = self.run_heimdall_command(
            ["git-hook", "install", "/non/existent/path"], check=False
        )

        assert result.returncode == 1
        error_output = result.stdout + result.stderr
        assert (
            "Failed to install git hook" in error_output
            or "Not a git repository" in error_output
        )

    def test_git_hook_multiple_operations(self, temp_git_repo):
        """Test multiple git hook operations in sequence."""
        repo_path = str(temp_git_repo)

        # Install -> Uninstall -> Install cycle
        for _ in range(2):
            # Install
            result = self.run_heimdall_command(["git-hook", "install", repo_path])
            assert result.returncode == 0

            hook_file = temp_git_repo / ".git" / "hooks" / "post-commit"
            assert hook_file.exists()

            # Uninstall
            result = self.run_heimdall_command(["git-hook", "uninstall", repo_path])
            assert result.returncode == 0

            assert not hook_file.exists()

    def test_git_hook_long_paths(self):
        """Test git hook commands with long repository paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create nested directory structure
            long_path = Path(temp_dir)
            for i in range(10):
                long_path = long_path / f"very_long_directory_name_{i}"

            repo_path = long_path / "test_repo"
            repo_path.mkdir(parents=True)

            # Initialize git repository
            subprocess.run(["git", "init"], cwd=repo_path, check=True)
            subprocess.run(
                ["git", "config", "user.name", "Test User"], cwd=repo_path, check=True
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo_path,
                check=True,
            )

            # Test commands work with long paths
            result = self.run_heimdall_command(["git-hook", "install", str(repo_path)])
            assert result.returncode == 0

            hook_file = repo_path / ".git" / "hooks" / "post-commit"
            assert hook_file.exists()


if __name__ == "__main__":
    """Allow running this test directly for debugging."""
    pytest.main([__file__, "-v"])
    print("✅ All git hook CLI integration tests completed!")
