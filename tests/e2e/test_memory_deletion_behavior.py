#!/usr/bin/env python3
"""
Behavioral tests for memory deletion operations.

This test validates that deletion commands correctly identify and remove
the right memories while preserving all other memories. Tests actual
data integrity and precision of deletion operations.
"""

import json
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import pytest


@pytest.mark.slow
@pytest.mark.requires_qdrant
class TestMemoryDeletionBehavior:
    """Test suite for memory deletion behavioral correctness."""

    @pytest.fixture
    def cognitive_system_setup(self):
        """Set up a cognitive system with precisely controlled test data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "behavior_test"
            project_path.mkdir()

            # Initialize project (answer 'n' to both file monitoring and MCP integration questions)
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "heimdall.cli",
                    "project",
                    "init",
                    "--non-interactive",
                ],
                cwd=project_path,
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, f"Project init failed: {result.stderr}"

            # Define test memories with specific, controlled data
            test_memories = [
                {
                    "id": "target_1",
                    "content": "Memory TARGET_1 for ID deletion testing - unique content Alpha",
                    "tags": ["target", "alpha", "id_test"],
                    "expected_in_deletion": True,
                },
                {
                    "id": "preserve_1",
                    "content": "Memory PRESERVE_1 should remain after ID deletion - unique content Beta",
                    "tags": ["preserve", "beta", "keep"],
                    "expected_in_deletion": False,
                },
                {
                    "id": "tag_victim_1",
                    "content": "Memory TAG_VICTIM_1 has deletion_tag - unique content Gamma",
                    "tags": ["victim", "deletion_tag", "gamma"],
                    "expected_in_deletion": True,  # Will be deleted by tag
                },
                {
                    "id": "tag_victim_2",
                    "content": "Memory TAG_VICTIM_2 also has deletion_tag - unique content Delta",
                    "tags": ["victim", "deletion_tag", "delta"],
                    "expected_in_deletion": True,  # Will be deleted by tag
                },
                {
                    "id": "safe_similar",
                    "content": "Memory SAFE_SIMILAR has similar but different tags - unique content Epsilon",
                    "tags": [
                        "victim",
                        "deletion_tag_different",
                        "epsilon",
                    ],  # Note: different tag
                    "expected_in_deletion": False,  # Should NOT be deleted
                },
                {
                    "id": "safe_partial",
                    "content": "Memory SAFE_PARTIAL has partial tag match - unique content Zeta",
                    "tags": ["victim", "tag", "zeta"],  # Note: "tag" not "deletion_tag"
                    "expected_in_deletion": False,  # Should NOT be deleted
                },
                {
                    "id": "case_test",
                    "content": "Memory CASE_TEST for case sensitivity - unique content Eta",
                    "tags": ["VICTIM", "DELETION_TAG", "eta"],  # Different case
                    "expected_in_deletion": False,  # Should NOT be deleted (case sensitive)
                },
            ]

            # Store all test memories and collect their actual IDs
            stored_memories = {}
            for memory_data in test_memories:
                context = json.dumps(
                    {
                        "tags": memory_data["tags"],
                        "hierarchy_level": 2,
                        "memory_type": "episodic",
                    }
                )

                result = subprocess.run(
                    [
                        "python",
                        "-m",
                        "heimdall.cli",
                        "store",
                        memory_data["content"],
                        "--context",
                        context,
                    ],
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                )

                assert result.returncode == 0, (
                    f"Failed to store {memory_data['id']}: {result.stderr}"
                )

                # Extract actual memory ID from output
                output = result.stdout + result.stderr
                actual_id = None
                for line in output.split("\n"):
                    if "Memory ID:" in line:
                        actual_id = line.split("Memory ID:")[-1].strip()
                        break

                assert actual_id, f"Could not extract memory ID for {memory_data['id']}"

                stored_memories[memory_data["id"]] = {
                    "actual_id": actual_id,
                    "content": memory_data["content"],
                    "tags": memory_data["tags"],
                    "expected_in_deletion": memory_data["expected_in_deletion"],
                }

            # Wait for indexing
            time.sleep(3)

            yield {"project_path": project_path, "memories": stored_memories}

    def run_command(self, args, cwd, input_text=None):
        """Run heimdall command and return result."""
        cmd = ["python", "-m", "heimdall.cli"] + args
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=False, input=input_text
        )
        return result

    def verify_memory_exists(self, content_snippet: str, project_path: Path) -> bool:
        """Verify a memory exists by searching for unique content."""
        result = self.run_command(["recall", content_snippet], project_path)
        if result.returncode != 0:
            return False

        output = result.stdout + result.stderr

        # Check if "No memories found" appears
        if "No memories found" in output or "📭" in output:
            return False

        # Check if the content appears in the results (not just in the query echo)
        lines = output.split("\n")
        for line in lines:
            if content_snippet.lower() in line.lower() and "query:" not in line.lower():
                return True

        return False

    def get_all_memories_with_tag(self, tag: str, project_path: Path) -> list[str]:
        """Get all memories that contain a specific tag by searching."""
        result = self.run_command(["recall", f"tag {tag}", "--json"], project_path)
        if result.returncode != 0:
            return []

        # Since we can't rely on JSON parsing working perfectly,
        # let's use a simpler approach - search for the tag
        result2 = self.run_command(["recall", tag], project_path)
        if result2.returncode != 0:
            return []

        # Count how many results we get
        output = result2.stdout + result2.stderr
        if "No memories found" in output or "📭" in output:
            return []

        # Return non-empty list if we found results (exact count doesn't matter for our test)
        # Look for "Total results: 0" specifically to avoid false negatives
        if "Total results: 0" in output:
            return []
        elif "Total results:" in output:
            return ["found"]
        else:
            return []

    def test_delete_memory_by_id_precision(self, cognitive_system_setup):
        """Test that ID-based deletion removes exactly the target memory."""
        setup = cognitive_system_setup
        project_path = setup["project_path"]
        memories = setup["memories"]

        # Choose target memory for deletion
        target_memory = memories["target_1"]
        target_id = target_memory["actual_id"]
        target_content = target_memory["content"]

        # Verify all memories exist before deletion
        for memory_key, memory_info in memories.items():
            exists = self.verify_memory_exists(memory_info["content"], project_path)
            assert exists, (
                f"Memory {memory_key} should exist before deletion but doesn't"
            )

        # Delete the target memory
        result = self.run_command(
            ["delete-memory", target_id, "--no-confirm"], project_path
        )

        assert result.returncode == 0, f"Deletion failed: {result.stderr}"

        # Verify target memory is gone
        target_exists = self.verify_memory_exists(target_content, project_path)
        assert not target_exists, (
            f"Target memory {target_id} should be deleted but still exists"
        )

        # Verify all other memories still exist
        for memory_key, memory_info in memories.items():
            if memory_key == "target_1":
                continue  # Skip the deleted one

            exists = self.verify_memory_exists(memory_info["content"], project_path)
            assert exists, (
                f"Memory {memory_key} should still exist after target deletion but is gone"
            )

    def test_delete_memories_by_tags_precision(self, cognitive_system_setup):
        """Test that tag-based deletion removes exactly memories with specified tags."""
        setup = cognitive_system_setup
        project_path = setup["project_path"]
        memories = setup["memories"]

        # Verify all memories exist before deletion
        for memory_key, memory_info in memories.items():
            exists = self.verify_memory_exists(memory_info["content"], project_path)
            assert exists, f"Memory {memory_key} should exist before deletion"

        # Delete memories with "deletion_tag"
        result = self.run_command(
            ["delete-memories-by-tags", "--tag", "deletion_tag", "--no-confirm"],
            project_path,
        )

        assert result.returncode == 0, f"Tag-based deletion failed: {result.stderr}"

        # Verify the correct memories were deleted
        expected_deleted = ["tag_victim_1", "tag_victim_2"]
        expected_preserved = ["preserve_1", "safe_similar", "safe_partial", "case_test"]

        for memory_key in expected_deleted:
            exists = self.verify_memory_exists(
                memories[memory_key]["content"], project_path
            )
            assert not exists, f"Memory {memory_key} should be deleted but still exists"

        for memory_key in expected_preserved:
            exists = self.verify_memory_exists(
                memories[memory_key]["content"], project_path
            )
            assert exists, f"Memory {memory_key} should be preserved but was deleted"

    def test_tag_deletion_does_not_match_partial_tags(self, cognitive_system_setup):
        """Test that tag deletion is exact - doesn't match partial tag names."""
        setup = cognitive_system_setup
        project_path = setup["project_path"]
        memories = setup["memories"]

        # Delete memories with tag "tag" (should NOT match "deletion_tag")
        result = self.run_command(
            ["delete-memories-by-tags", "--tag", "tag", "--no-confirm"], project_path
        )

        assert result.returncode == 0, f"Tag deletion failed: {result.stderr}"

        # Verify that memories with "deletion_tag" are NOT deleted
        for memory_key in ["tag_victim_1", "tag_victim_2"]:
            exists = self.verify_memory_exists(
                memories[memory_key]["content"], project_path
            )
            assert exists, (
                f"Memory {memory_key} should NOT be deleted by partial tag match"
            )

        # Verify that memory with exact "tag" IS deleted
        safe_partial_exists = self.verify_memory_exists(
            memories["safe_partial"]["content"], project_path
        )
        assert not safe_partial_exists, "Memory with exact 'tag' should be deleted"

    def test_case_sensitivity_in_tag_deletion(self, cognitive_system_setup):
        """Test that tag deletion is case sensitive."""
        setup = cognitive_system_setup
        project_path = setup["project_path"]
        memories = setup["memories"]

        # Try to delete with lowercase tag when memory has uppercase
        result = self.run_command(
            [
                "delete-memories-by-tags",
                "--tag",
                "victim",  # lowercase
                "--no-confirm",
            ],
            project_path,
        )

        assert result.returncode == 0

        # Memory with uppercase "VICTIM" should NOT be deleted
        case_test_exists = self.verify_memory_exists(
            memories["case_test"]["content"], project_path
        )
        assert case_test_exists, (
            "Memory with uppercase tags should not be deleted by lowercase tag search"
        )

        # Memories with lowercase "victim" should be deleted
        for memory_key in [
            "tag_victim_1",
            "tag_victim_2",
            "safe_similar",
            "safe_partial",
        ]:
            exists = self.verify_memory_exists(
                memories[memory_key]["content"], project_path
            )
            assert not exists, (
                f"Memory {memory_key} with lowercase 'victim' tag should be deleted"
            )

    def test_multiple_tags_or_logic(self, cognitive_system_setup):
        """Test that multiple tags use OR logic (delete if ANY tag matches)."""
        setup = cognitive_system_setup
        project_path = setup["project_path"]
        memories = setup["memories"]

        # Delete memories that have EITHER "alpha" OR "gamma" tags
        result = self.run_command(
            [
                "delete-memories-by-tags",
                "--tag",
                "alpha",
                "--tag",
                "gamma",
                "--no-confirm",
            ],
            project_path,
        )

        assert result.returncode == 0

        # Memories with "alpha" or "gamma" should be deleted
        expected_deleted = [
            "target_1",
            "tag_victim_1",
        ]  # target_1 has alpha, tag_victim_1 has gamma
        expected_preserved = [
            "preserve_1",
            "tag_victim_2",
            "safe_similar",
            "safe_partial",
            "case_test",
        ]

        for memory_key in expected_deleted:
            exists = self.verify_memory_exists(
                memories[memory_key]["content"], project_path
            )
            assert not exists, (
                f"Memory {memory_key} should be deleted (has alpha or gamma tag)"
            )

        for memory_key in expected_preserved:
            exists = self.verify_memory_exists(
                memories[memory_key]["content"], project_path
            )
            assert exists, (
                f"Memory {memory_key} should be preserved (no alpha or gamma tag)"
            )

    def test_deletion_is_permanent_and_complete(self, cognitive_system_setup):
        """Test that deletion completely removes memory from all storage layers."""
        setup = cognitive_system_setup
        project_path = setup["project_path"]
        memories = setup["memories"]

        target_memory = memories["preserve_1"]
        target_content = target_memory["content"]
        target_id = target_memory["actual_id"]

        # Verify memory exists with multiple search approaches
        exists_by_content = self.verify_memory_exists(target_content, project_path)
        # Use a more specific search for tags - search for unique content that has the preserve tag
        exists_by_tag = self.verify_memory_exists("PRESERVE_1", project_path)

        assert exists_by_content, "Memory should be findable by content before deletion"
        assert exists_by_tag, (
            "Memory should be findable by specific content before deletion"
        )

        # Delete the memory
        result = self.run_command(
            ["delete-memory", target_id, "--no-confirm"], project_path
        )

        assert result.returncode == 0

        # Verify memory is completely gone
        exists_by_content_after = self.verify_memory_exists(
            target_content, project_path
        )
        exists_by_tag_after = self.verify_memory_exists("PRESERVE_1", project_path)

        assert not exists_by_content_after, (
            "Memory should not be findable by content after deletion"
        )
        assert not exists_by_tag_after, (
            "Memory should not be findable by specific content after deletion"
        )

        # Try to delete the same memory again - should fail gracefully
        result2 = self.run_command(
            ["delete-memory", target_id, "--no-confirm"], project_path
        )

        assert result2.returncode == 1, "Deleting already-deleted memory should fail"

    def test_dry_run_does_not_delete_anything(self, cognitive_system_setup):
        """Test that dry-run mode shows what would be deleted but doesn't delete."""
        setup = cognitive_system_setup
        project_path = setup["project_path"]
        memories = setup["memories"]

        # Run dry-run deletion by ID
        target_id = memories["target_1"]["actual_id"]
        result = self.run_command(
            ["delete-memory", target_id, "--dry-run"], project_path
        )

        assert result.returncode == 0
        assert "DRY RUN" in (result.stdout + result.stderr)

        # Verify memory still exists
        exists = self.verify_memory_exists(
            memories["target_1"]["content"], project_path
        )
        assert exists, "Memory should still exist after dry-run"

        # Run dry-run deletion by tags
        result2 = self.run_command(
            ["delete-memories-by-tags", "--tag", "deletion_tag", "--dry-run"],
            project_path,
        )

        assert result2.returncode == 0
        assert "DRY RUN" in (result2.stdout + result2.stderr)

        # Verify all memories still exist
        for memory_key, memory_info in memories.items():
            exists = self.verify_memory_exists(memory_info["content"], project_path)
            assert exists, f"Memory {memory_key} should still exist after tag dry-run"

    def test_nonexistent_id_deletion_fails_safely(self, cognitive_system_setup):
        """Test that attempting to delete non-existent ID fails without affecting other memories."""
        setup = cognitive_system_setup
        project_path = setup["project_path"]
        memories = setup["memories"]

        # Try to delete non-existent memory
        fake_id = str(uuid.uuid4())
        result = self.run_command(
            ["delete-memory", fake_id, "--no-confirm"], project_path
        )

        assert result.returncode == 1, "Deleting non-existent memory should fail"

        # Verify all existing memories are unaffected
        for memory_key, memory_info in memories.items():
            exists = self.verify_memory_exists(memory_info["content"], project_path)
            assert exists, (
                f"Memory {memory_key} should be unaffected by failed deletion"
            )

    def test_empty_tag_deletion_fails_safely(self, cognitive_system_setup):
        """Test that deletion with empty/invalid tags fails safely."""
        setup = cognitive_system_setup
        project_path = setup["project_path"]
        memories = setup["memories"]

        # Try various invalid tag scenarios
        invalid_scenarios = [
            ["--tag", ""],  # Empty tag
            ["--tag", "   "],  # Whitespace only
        ]

        for scenario in invalid_scenarios:
            self.run_command(
                ["delete-memories-by-tags"] + scenario + ["--no-confirm"], project_path
            )

            # Should either fail or find no results
            # Either way, no memories should be deleted
            for memory_key, memory_info in memories.items():
                exists = self.verify_memory_exists(memory_info["content"], project_path)
                assert exists, (
                    f"Memory {memory_key} should be unaffected by invalid tag deletion"
                )


if __name__ == "__main__":
    """Allow running this test directly for debugging."""
    pytest.main([__file__, "-v", "-s"])
    print("✅ All memory deletion behavior tests completed!")
