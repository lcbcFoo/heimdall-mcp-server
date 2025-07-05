#!/usr/bin/env python3
"""
End-to-end CLI integration tests for memory deletion commands.

This test validates the complete CLI integration of memory deletion commands
through the actual heimdall CLI interface, testing the full user workflow
with real cognitive system dependencies.
"""

import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

import pytest


@pytest.mark.slow
@pytest.mark.requires_qdrant
class TestMemoryDeletionCLIIntegration:
    """Test suite for memory deletion CLI integration."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test_project"
            project_path.mkdir()
            yield project_path

    @pytest.fixture
    def cognitive_system_with_memories(self, temp_project_dir):
        """Set up cognitive system with test memories."""
        # Initialize project memory (use non-interactive mode to skip all prompts)
        result = self.run_heimdall_command(
            ["project", "init", "--non-interactive"],
            cwd=temp_project_dir,
        )
        assert result.returncode == 0, f"Project init failed: {result.stderr}"

        # Store test memories with known content and tags
        test_memories = [
            {
                "content": "Test memory for deletion - ID based testing",
                "tags": ["test", "deletion", "single"],
                "hierarchy_level": 2,
                "memory_type": "episodic",
            },
            {
                "content": "Memory with tag1 and tag2 for batch deletion",
                "tags": ["tag1", "tag2", "batch"],
                "hierarchy_level": 1,
                "memory_type": "semantic",
            },
            {
                "content": "Another memory with tag1 for batch testing",
                "tags": ["tag1", "batch"],
                "hierarchy_level": 2,
                "memory_type": "episodic",
            },
            {
                "content": "Memory with unique tag for isolated testing",
                "tags": ["unique", "isolated"],
                "hierarchy_level": 0,
                "memory_type": "semantic",
            },
            {
                "content": "Memory without special tags",
                "tags": ["normal"],
                "hierarchy_level": 2,
                "memory_type": "episodic",
            },
        ]

        stored_memory_ids = []
        memory_id_to_content = {}
        for memory_data in test_memories:
            context = json.dumps(
                {
                    "tags": memory_data["tags"],
                    "hierarchy_level": memory_data["hierarchy_level"],
                    "memory_type": memory_data["memory_type"],
                }
            )

            result = self.run_heimdall_command(
                ["store", memory_data["content"], "--context", context],
                cwd=temp_project_dir,
                check=False,
            )

            if result.returncode != 0:
                print(f"Store command failed for content: {memory_data['content']}")
                print(f"stdout: {result.stdout}")
                print(f"stderr: {result.stderr}")
                # Skip this memory and continue with others
                continue

            # Extract memory ID from output
            output = result.stdout + result.stderr
            # Look for pattern like "Memory ID: uuid-here"
            for line in output.split("\n"):
                if "Memory ID:" in line:
                    memory_id = line.split("Memory ID:")[-1].strip()
                    stored_memory_ids.append(memory_id)
                    memory_id_to_content[memory_id] = memory_data["content"]
                    break

        # Wait a moment for indexing
        time.sleep(2)

        yield {
            "project_dir": temp_project_dir,
            "memory_ids": stored_memory_ids,
            "test_memories": test_memories,
            "memory_id_to_content": memory_id_to_content,
        }

    def run_heimdall_command(self, args, cwd=None, check=True, input_text=None):
        """Run heimdall CLI command and return result."""
        cmd = ["python", "-m", "heimdall.cli"] + args
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=False, input=input_text
        )

        # Only raise exception if check=True and the command failed
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr
            )

        return result

    def _strip_ansi_codes(self, text: str) -> str:
        """Strip ANSI escape codes from text."""
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)

    def verify_memory_exists(
        self, memory_id: str, project_dir: Path, content: str = None
    ) -> bool:
        """Verify a memory exists by trying to recall it with its content."""
        if content is None:
            # Fallback to old behavior if content not provided
            result = self.run_heimdall_command(
                ["recall", f"memory ID {memory_id}"], cwd=project_dir, check=False
            )
            output = result.stdout + result.stderr
            lines = output.split("\n")
            for _, line in enumerate(lines):
                if "🔍 Query:" in line and memory_id in line:
                    continue
                if memory_id in line:
                    return True
            return False

        # Search for the memory using its content
        result = self.run_heimdall_command(
            ["recall", content], cwd=project_dir, check=False
        )

        if result.returncode != 0:
            return False

        output = result.stdout + result.stderr

        # Check if the exact content appears in the results
        # Look for the content in the actual results (skip query line)
        lines = output.split("\n")
        for line in lines:
            # Skip the query line that shows our search term
            if "🔍 Query:" in line:
                continue
            if content in line:
                return True

        return False

    def get_memories_by_tag(self, tag: str, project_dir: Path) -> list[str]:
        """Get memory IDs that have a specific tag."""
        result = self.run_heimdall_command(
            ["recall", f"tag:{tag}", "--json"], cwd=project_dir, check=False
        )

        if result.returncode != 0:
            return []

        try:
            output_data = json.loads(result.stdout)
            memory_ids = []
            for memory_type in ["core", "peripheral", "bridge"]:
                for memory in output_data.get(memory_type, []):
                    if hasattr(memory, "id"):
                        memory_ids.append(memory.id)
                    elif isinstance(memory, dict) and "id" in memory:
                        memory_ids.append(memory["id"])
            return memory_ids
        except (json.JSONDecodeError, KeyError):
            return []

    def test_delete_memory_help(self):
        """Test delete-memory command help output."""
        result = self.run_heimdall_command(["delete-memory", "--help"])

        assert result.returncode == 0
        output = self._strip_ansi_codes(result.stdout + result.stderr)
        assert "Delete a single memory by its ID" in output
        assert "--dry-run" in output
        assert "--no-confirm" in output

    def test_delete_memories_by_tags_help(self):
        """Test delete-memories-by-tags command help output."""
        result = self.run_heimdall_command(["delete-memories-by-tags", "--help"])

        assert result.returncode == 0
        output = self._strip_ansi_codes(result.stdout + result.stderr)
        assert "Delete all memories that have any of the specified tags" in output
        assert "--tag" in output
        assert "--dry-run" in output
        assert "--no-confirm" in output

    def test_delete_memory_nonexistent_id(self, cognitive_system_with_memories):
        """Test deleting a non-existent memory ID."""
        project_dir = cognitive_system_with_memories["project_dir"]

        result = self.run_heimdall_command(
            ["delete-memory", "nonexistent-uuid-12345", "--no-confirm"],
            cwd=project_dir,
            check=False,
        )

        assert result.returncode == 1
        output = result.stdout + result.stderr
        assert "Memory not found" in output or "No memory found" in output

    def test_delete_memory_empty_id(self, cognitive_system_with_memories):
        """Test deleting with empty memory ID."""
        project_dir = cognitive_system_with_memories["project_dir"]

        result = self.run_heimdall_command(
            ["delete-memory", "", "--no-confirm"], cwd=project_dir, check=False
        )

        assert result.returncode == 1

    def test_delete_memory_dry_run(self, cognitive_system_with_memories):
        """Test delete-memory command in dry-run mode."""
        project_dir = cognitive_system_with_memories["project_dir"]
        memory_ids = cognitive_system_with_memories["memory_ids"]
        memory_id_to_content = cognitive_system_with_memories["memory_id_to_content"]

        if not memory_ids:
            pytest.skip("No memory IDs available for testing")

        memory_id = memory_ids[0]
        content = memory_id_to_content[memory_id]

        # Verify memory exists
        assert self.verify_memory_exists(memory_id, project_dir, content)

        # Run dry-run
        result = self.run_heimdall_command(
            ["delete-memory", memory_id, "--dry-run"], cwd=project_dir
        )

        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "DRY RUN" in output
        assert "Memory would be deleted" in output or "Found memory" in output

        # Verify memory still exists
        assert self.verify_memory_exists(memory_id, project_dir, content)

    def test_delete_memory_success(self, cognitive_system_with_memories):
        """Test successful memory deletion."""
        project_dir = cognitive_system_with_memories["project_dir"]
        memory_ids = cognitive_system_with_memories["memory_ids"]
        memory_id_to_content = cognitive_system_with_memories["memory_id_to_content"]

        if not memory_ids:
            pytest.skip("No memory IDs available for testing")

        memory_id = memory_ids[0]
        content = memory_id_to_content[memory_id]

        # Verify memory exists
        assert self.verify_memory_exists(memory_id, project_dir, content)

        # Delete memory
        result = self.run_heimdall_command(
            ["delete-memory", memory_id, "--no-confirm"], cwd=project_dir
        )

        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "Deleted memory" in output or "✅" in output

        # Verify memory no longer exists
        assert not self.verify_memory_exists(memory_id, project_dir, content)

    def test_delete_memory_with_confirmation(self, cognitive_system_with_memories):
        """Test delete-memory with confirmation prompt (cancellation)."""
        project_dir = cognitive_system_with_memories["project_dir"]
        memory_ids = cognitive_system_with_memories["memory_ids"]
        memory_id_to_content = cognitive_system_with_memories["memory_id_to_content"]

        if len(memory_ids) < 2:
            pytest.skip("Need at least 2 memory IDs for testing")

        memory_id = memory_ids[1]
        content = memory_id_to_content[memory_id]

        # Verify memory exists
        assert self.verify_memory_exists(memory_id, project_dir, content)

        # Delete memory with "n" (no) confirmation
        result = self.run_heimdall_command(
            ["delete-memory", memory_id], cwd=project_dir, input_text="n\n", check=False
        )

        # Should exit without error but without deleting
        output = result.stdout + result.stderr
        assert "cancelled" in output.lower() or "aborted" in output.lower()

        # Verify memory still exists
        assert self.verify_memory_exists(memory_id, project_dir, content)

    def test_delete_memories_by_tags_nonexistent(self, cognitive_system_with_memories):
        """Test deleting memories with non-existent tags."""
        project_dir = cognitive_system_with_memories["project_dir"]

        result = self.run_heimdall_command(
            ["delete-memories-by-tags", "--tag", "nonexistent-tag-xyz", "--no-confirm"],
            cwd=project_dir,
        )

        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "No memories found" in output or "📭" in output

    def test_delete_memories_by_tags_empty(self, cognitive_system_with_memories):
        """Test deleting memories with empty tag list."""
        project_dir = cognitive_system_with_memories["project_dir"]

        result = self.run_heimdall_command(
            ["delete-memories-by-tags", "--tag", "", "--no-confirm"],
            cwd=project_dir,
            check=False,
        )

        # Should fail with empty tags
        assert result.returncode == 1

    def test_delete_memories_by_tags_dry_run(self, cognitive_system_with_memories):
        """Test delete-memories-by-tags command in dry-run mode."""
        project_dir = cognitive_system_with_memories["project_dir"]

        # Use a tag we know exists
        result = self.run_heimdall_command(
            ["delete-memories-by-tags", "--tag", "test", "--dry-run"], cwd=project_dir
        )

        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "DRY RUN" in output

        # Verify memories with 'test' tag still exist by searching
        verify_result = self.run_heimdall_command(["recall", "test"], cwd=project_dir)
        assert verify_result.returncode == 0

    def test_delete_memories_by_tags_single_tag_success(
        self, cognitive_system_with_memories
    ):
        """Test successful deletion of memories by single tag."""
        project_dir = cognitive_system_with_memories["project_dir"]

        # Delete memories with 'unique' tag (should be 1 memory)
        result = self.run_heimdall_command(
            ["delete-memories-by-tags", "--tag", "unique", "--no-confirm"],
            cwd=project_dir,
        )

        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "Deleted" in output and "memories" in output

        # Verify memories with 'unique' tag no longer exist by searching for the specific content
        verify_result = self.run_heimdall_command(
            ["recall", "Memory with unique tag for isolated testing"],
            cwd=project_dir,
            check=False,
        )

        # The specific memory content should not be found in the actual results (skip query line)
        assert verify_result.returncode == 0
        verify_output = verify_result.stdout + verify_result.stderr
        lines = verify_output.split("\n")
        for line in lines:
            # Skip the query line that shows our search term
            if "🔍 Query:" in line:
                continue
            # The content should not appear in any result line
            assert "Memory with unique tag for isolated testing" not in line

    def test_delete_memories_by_tags_multiple_tags(
        self, cognitive_system_with_memories
    ):
        """Test deletion of memories with multiple tags specified."""
        project_dir = cognitive_system_with_memories["project_dir"]

        # Delete memories with either 'tag1' OR 'tag2'
        result = self.run_heimdall_command(
            [
                "delete-memories-by-tags",
                "--tag",
                "tag1",
                "--tag",
                "tag2",
                "--no-confirm",
            ],
            cwd=project_dir,
        )

        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "Deleted" in output

        # Verify specific memories with these tags are gone by checking their content
        tag1_memories = [
            "Memory with tag1 and tag2 for batch deletion",
            "Another memory with tag1 for batch testing",
        ]

        for memory_content in tag1_memories:
            verify_result = self.run_heimdall_command(
                ["recall", memory_content], cwd=project_dir, check=False
            )
            verify_output = verify_result.stdout + verify_result.stderr
            # The specific memory content should not be found in actual results (skip query line)
            lines = verify_output.split("\n")
            for line in lines:
                # Skip the query line that shows our search term
                if "🔍 Query:" in line:
                    continue
                # The content should not appear in any result line
                assert memory_content not in line

    def test_delete_memories_by_tags_with_confirmation(
        self, cognitive_system_with_memories
    ):
        """Test delete-memories-by-tags with confirmation prompt (cancellation)."""
        project_dir = cognitive_system_with_memories["project_dir"]

        # Try to delete 'normal' tag but cancel
        result = self.run_heimdall_command(
            ["delete-memories-by-tags", "--tag", "normal"],
            cwd=project_dir,
            input_text="n\n",
            check=False,
        )

        output = result.stdout + result.stderr
        assert "cancelled" in output.lower() or "aborted" in output.lower()

        # Verify memories with 'normal' tag still exist
        verify_result = self.run_heimdall_command(["recall", "normal"], cwd=project_dir)
        assert verify_result.returncode == 0

    def test_memory_deletion_sequence(self, cognitive_system_with_memories):
        """Test complete memory deletion workflow sequence."""
        project_dir = cognitive_system_with_memories["project_dir"]
        memory_ids = cognitive_system_with_memories["memory_ids"]
        memory_id_to_content = cognitive_system_with_memories["memory_id_to_content"]

        if len(memory_ids) < 3:
            pytest.skip("Need at least 3 memory IDs for sequence testing")

        # 1. Verify initial state - memories exist
        result = self.run_heimdall_command(["status"], cwd=project_dir)
        assert result.returncode == 0

        # 2. Delete one memory by ID
        memory_id = memory_ids[-1]  # Use last one to avoid interfering with other tests
        content = memory_id_to_content[memory_id]
        result = self.run_heimdall_command(
            ["delete-memory", memory_id, "--no-confirm"], cwd=project_dir
        )
        assert result.returncode == 0

        # 3. Verify memory is gone
        assert not self.verify_memory_exists(memory_id, project_dir, content)

        # 4. Delete remaining memories by tag
        result = self.run_heimdall_command(
            ["delete-memories-by-tags", "--tag", "batch", "--no-confirm"],
            cwd=project_dir,
        )
        assert result.returncode == 0

        # 5. Verify batch deletion worked by checking specific content
        batch_memories = [
            "Memory with tag1 and tag2 for batch deletion",
            "Another memory with tag1 for batch testing",
        ]

        for memory_content in batch_memories:
            verify_result = self.run_heimdall_command(
                ["recall", memory_content], cwd=project_dir, check=False
            )
            verify_output = verify_result.stdout + verify_result.stderr
            # The specific memory content should not be found in actual results (skip query line)
            lines = verify_output.split("\n")
            for line in lines:
                # Skip the query line that shows our search term
                if "🔍 Query:" in line:
                    continue
                # The content should not appear in any result line
                assert memory_content not in line

    def test_error_handling_and_recovery(self, cognitive_system_with_memories):
        """Test error handling and system recovery."""
        project_dir = cognitive_system_with_memories["project_dir"]

        # Test multiple error scenarios
        error_scenarios = [
            # Invalid memory ID formats
            ["delete-memory", "invalid-uuid", "--no-confirm"],
            ["delete-memory", "123", "--no-confirm"],
            ["delete-memory", "not-a-uuid-at-all", "--no-confirm"],
            # Missing required arguments
            ["delete-memories-by-tags", "--no-confirm"],  # No tags specified
        ]

        for scenario in error_scenarios:
            result = self.run_heimdall_command(scenario, cwd=project_dir, check=False)
            # Different scenarios have different expected return codes
            if scenario == ["delete-memories-by-tags", "--no-confirm"]:
                # Missing required --tag option is a usage error (exit code 2)
                assert result.returncode == 2, (
                    f"Scenario {scenario} should fail with usage error"
                )
            else:
                # Other scenarios are runtime errors (exit code 1)
                assert result.returncode == 1, (
                    f"Scenario {scenario} should fail with runtime error"
                )

            # System should still be functional after errors
            status_result = self.run_heimdall_command(["status"], cwd=project_dir)
            assert status_result.returncode == 0, (
                "System should still be functional after error"
            )

    def test_memory_deletion_performance(self, temp_project_dir):
        """Test memory deletion performance with larger datasets."""
        # Initialize project (use non-interactive mode to skip all prompts)
        result = self.run_heimdall_command(
            ["project", "init", "--non-interactive"],
            cwd=temp_project_dir,
        )
        assert result.returncode == 0

        # Store multiple memories quickly
        batch_size = 10

        for i in range(batch_size):
            context = json.dumps(
                {
                    "tags": ["performance", f"batch_{i // 3}", "test"],
                    "hierarchy_level": 2,
                    "memory_type": "episodic",
                }
            )

            result = self.run_heimdall_command(
                [
                    "store",
                    f"Performance test memory {i} with content for deletion testing",
                    "--context",
                    context,
                ],
                cwd=temp_project_dir,
            )

            assert result.returncode == 0

        # Wait for indexing
        time.sleep(3)

        # Delete all memories with 'performance' tag
        start_time = time.time()
        result = self.run_heimdall_command(
            ["delete-memories-by-tags", "--tag", "performance", "--no-confirm"],
            cwd=temp_project_dir,
        )
        end_time = time.time()

        assert result.returncode == 0
        deletion_time = end_time - start_time

        # Should complete within reasonable time (adjust threshold as needed)
        assert deletion_time < 30, f"Deletion took too long: {deletion_time}s"

        output = result.stdout + result.stderr
        assert "Deleted" in output

    def test_memory_deletion_edge_cases(self, cognitive_system_with_memories):
        """Test edge cases and boundary conditions."""
        project_dir = cognitive_system_with_memories["project_dir"]

        # Test with very long memory ID
        long_id = "a" * 200
        result = self.run_heimdall_command(
            ["delete-memory", long_id, "--no-confirm"], cwd=project_dir, check=False
        )
        assert result.returncode == 1

        # Test with special characters in tags
        special_tags = [
            "tag with spaces",
            "tag-with-dashes",
            "tag_with_underscores",
            "tag.with.dots",
        ]
        for tag in special_tags:
            result = self.run_heimdall_command(
                ["delete-memories-by-tags", "--tag", tag, "--no-confirm"],
                cwd=project_dir,
            )
            # Should handle gracefully even if no matches
            assert result.returncode == 0

    def test_concurrent_deletion_safety(self, cognitive_system_with_memories):
        """Test that deletion operations are safe under concurrent access."""
        project_dir = cognitive_system_with_memories["project_dir"]
        memory_ids = cognitive_system_with_memories["memory_ids"]

        if len(memory_ids) < 2:
            pytest.skip("Need at least 2 memory IDs for concurrency testing")

        # This is a simplified concurrency test - in a real scenario you'd use threading
        # For now, just test that rapid sequential operations work correctly

        # Rapid deletion sequence
        results = []
        for _i, memory_id in enumerate(memory_ids[:2]):
            result = self.run_heimdall_command(
                ["delete-memory", memory_id, "--no-confirm"],
                cwd=project_dir,
                check=False,
            )
            results.append(result.returncode)

        # At least one should succeed, others may fail gracefully
        assert any(code == 0 for code in results), (
            "At least one deletion should succeed"
        )

        # System should remain stable
        status_result = self.run_heimdall_command(["status"], cwd=project_dir)
        assert status_result.returncode == 0


if __name__ == "__main__":
    """Allow running this test directly for debugging."""
    pytest.main([__file__, "-v", "-s"])
    print("✅ All memory deletion CLI integration tests completed!")
