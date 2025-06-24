"""
MCP Response Formatting Utilities.

This module provides utilities for formatting cognitive memory data
for optimal LLM consumption through the MCP protocol.
"""

from datetime import datetime
from typing import Any

from cognitive_memory.core.memory import BridgeMemory, CognitiveMemory
from heimdall.display_utils import format_source_info


def format_memory_for_llm(memory: CognitiveMemory) -> dict[str, Any]:
    """
    Format a CognitiveMemory object for LLM consumption.

    Args:
        memory: The memory to format

    Returns:
        Formatted memory data with rich metadata
    """
    # Get hierarchy level name
    level_names = {0: "L0 (Concept)", 1: "L1 (Context)", 2: "L2 (Episode)"}
    level_name = level_names.get(memory.hierarchy_level, f"L{memory.hierarchy_level}")

    # Format source information
    source_info = format_source_info(memory)

    formatted = {
        "id": memory.id,
        "content": memory.content,
        "hierarchy_level": memory.hierarchy_level,
        "hierarchy_name": level_name,
        "memory_type": memory.memory_type,
        "strength": memory.strength,
        "importance_score": memory.importance_score,
        "source_info": source_info,
        "created_date": memory.created_date.isoformat()
        if memory.created_date
        else None,
        "last_accessed": memory.last_accessed.isoformat()
        if memory.last_accessed
        else None,
        "access_count": memory.access_count,
        "tags": memory.tags or [],
    }

    # Add temporal context if available
    if memory.modified_date:
        formatted["modified_date"] = memory.modified_date.isoformat()
    if memory.source_date:
        formatted["source_date"] = memory.source_date.isoformat()

    # Add relevant metadata
    if memory.metadata:
        # Include important metadata fields
        metadata_fields = [
            "loader_type",
            "source_path",
            "title",
            "pattern_type",
            "lesson_type",
        ]
        filtered_metadata = {
            k: v for k, v in memory.metadata.items() if k in metadata_fields
        }
        if filtered_metadata:
            formatted["metadata"] = filtered_metadata

    return formatted


def format_bridge_memory_for_llm(bridge: BridgeMemory) -> dict[str, Any]:
    """
    Format a BridgeMemory object for LLM consumption.

    Args:
        bridge: The bridge memory to format

    Returns:
        Formatted bridge memory data
    """
    source_info = format_source_info(bridge.memory)

    return {
        "id": bridge.memory.id,
        "content": bridge.memory.content,
        "bridge_score": bridge.bridge_score,
        "novelty_score": bridge.novelty_score,
        "connection_potential": bridge.connection_potential,
        "explanation": bridge.explanation,
        "source_info": source_info,
        "created_date": bridge.memory.created_date.isoformat()
        if bridge.memory.created_date
        else None,
        "hierarchy_level": bridge.memory.hierarchy_level,
        "memory_type": bridge.memory.memory_type,
    }


def format_memory_list_for_llm(
    memories: list[CognitiveMemory],
    bridges: list[BridgeMemory] | None = None,
    query: str = "",
    max_display: int = 10,
) -> str:
    """
    Format a list of memories for LLM display.

    Args:
        memories: List of memories to format
        bridges: Optional list of bridge memories
        query: The original search query
        max_display: Maximum number of memories to display in detail

    Returns:
        Formatted text representation
    """
    if not memories and not bridges:
        return f"No memories found for query: '{query}'"

    response = f"📋 Retrieved {len(memories)} memories"
    if bridges:
        response += f" and {len(bridges)} bridges"
    response += f" for: '{query}'\n\n"

    # Separate memories by type for organized display
    core_memories = []
    peripheral_memories = []

    for memory in memories:
        # Classify as core vs peripheral based on strength/importance
        if memory.strength >= 0.7 or memory.importance_score >= 0.7:
            core_memories.append(memory)
        else:
            peripheral_memories.append(memory)

    # Display core memories
    if core_memories:
        response += f"CORE MEMORIES ({len(core_memories)}):\n\n"
        for i, memory in enumerate(core_memories[: max_display // 2], 1):
            response += _format_single_memory_display(memory, i)

    # Display bridge memories if present
    if bridges:
        response += f"\nBRIDGE MEMORIES ({len(bridges)}):\n\n"
        for i, bridge in enumerate(bridges[:3], 1):  # Show top 3 bridges
            response += _format_single_bridge_display(bridge, i)

    # Display peripheral memories
    if peripheral_memories:
        displayed_peripheral = min(
            len(peripheral_memories), max_display - len(core_memories)
        )
        response += f"\nPERIPHERAL MEMORIES ({len(peripheral_memories)}): [showing {displayed_peripheral}]\n\n"
        for i, memory in enumerate(peripheral_memories[:displayed_peripheral], 1):
            response += _format_single_memory_display(memory, i + len(core_memories))

    return response


def _format_single_memory_display(memory: CognitiveMemory, index: int) -> str:
    """Format a single memory for display."""
    # Truncate content if too long
    content = memory.content
    if len(content) > 150:
        content = content[:147] + "..."

    source_info = format_source_info(memory)

    display = f"{index}. [{memory.memory_type}] {content}\n"
    display += f"   ID: {memory.id}, Level: L{memory.hierarchy_level}, Strength: {memory.strength:.2f}\n"
    display += f"   Source: {source_info}\n"
    display += f"   Created: {memory.created_date.strftime('%Y-%m-%d %H:%M') if memory.created_date else 'Unknown'}"
    display += f", Accessed: {memory.access_count} times\n\n"

    return display


def _format_single_bridge_display(bridge: BridgeMemory, index: int) -> str:
    """Format a single bridge memory for display."""
    content = bridge.memory.content
    if len(content) > 120:
        content = content[:117] + "..."

    source_info = format_source_info(bridge.memory)

    display = f"{index}. [bridge] {content}\n"
    display += f"   ID: {bridge.memory.id}, Bridge Score: {bridge.bridge_score:.2f}\n"
    display += f"   Novelty: {bridge.novelty_score:.2f}, Connection: {bridge.connection_potential:.2f}\n"
    display += f"   {bridge.explanation}\n"
    display += f"   Source: {source_info}\n\n"

    return display


def format_storage_response(
    success: bool,
    memory_id: str | None = None,
    hierarchy_level: int = 2,
    memory_type: str = "episodic",
    error_message: str | None = None,
) -> str:
    """
    Format a storage operation response.

    Args:
        success: Whether the storage was successful
        memory_id: ID of stored memory (if successful)
        hierarchy_level: Hierarchy level of stored memory
        memory_type: Type of stored memory
        error_message: Error message (if failed)

    Returns:
        Formatted response text
    """
    if success:
        level_names = {0: "L0 (Concept)", 1: "L1 (Context)", 2: "L2 (Episode)"}
        level_name = level_names.get(hierarchy_level, f"L{hierarchy_level}")

        response = "✓ Experience stored successfully\n\n"
        if memory_id:
            response += f"Memory ID: {memory_id}\n"
        response += f"Hierarchy Level: {level_name}\n"
        response += f"Memory Type: {memory_type}\n"
        response += f"Stored At: {datetime.now().isoformat()}Z\n\n"
        response += "This knowledge is now available for future recall and will contribute to pattern recognition."

        return response
    else:
        error_msg = error_message or "Unknown error occurred"
        return f"❌ Failed to store experience: {error_msg}"


def format_system_status(
    memory_counts: dict[str, int],
    system_health: str = "healthy",
    recent_activity: dict[str, str] | None = None,
    detailed: bool = False,
) -> str:
    """
    Format system status information.

    Args:
        memory_counts: Dictionary of memory counts by type
        system_health: Overall system health status
        recent_activity: Recent activity timestamps
        detailed: Whether to include detailed configuration

    Returns:
        Formatted status text
    """
    response = "📊 COGNITIVE MEMORY SYSTEM STATUS\n"
    response += "=" * 40 + "\n\n"

    # System health
    health_icon = "✅" if system_health == "healthy" else "⚠️"
    response += f"System Status: {health_icon} {system_health.upper()}\n\n"

    # Memory counts
    response += "Memory Counts:\n"
    response += f"  Total Memories: {memory_counts.get('total', 0):,}\n"
    response += f"  L0 (Concepts): {memory_counts.get('level_0', 0)} memories\n"
    response += f"  L1 (Contexts): {memory_counts.get('level_1', 0)} memories\n"
    response += f"  L2 (Episodes): {memory_counts.get('level_2', 0)} memories\n"
    response += "  \n"
    response += f"  Episodic Memories: {memory_counts.get('episodic', 0)}\n"
    response += f"  Semantic Memories: {memory_counts.get('semantic', 0)}\n"

    if memory_counts.get("session_lessons", 0) > 0:
        response += f"  Session Lessons: {memory_counts.get('session_lessons', 0)}\n"

    # Recent activity
    if recent_activity:
        response += "\nRecent Activity:\n"
        if "last_storage" in recent_activity:
            response += f"  Last Storage: {recent_activity['last_storage']}\n"
        if "last_retrieval" in recent_activity:
            response += f"  Last Retrieval: {recent_activity['last_retrieval']}\n"
        if "last_consolidation" in recent_activity:
            response += (
                f"  Last Consolidation: {recent_activity['last_consolidation']}\n"
            )

    # Detailed configuration
    if detailed:
        response += "\n🔧 DETAILED CONFIGURATION\n"
        response += f"{'-' * 30}\n"
        response += "Embedding Model: all-MiniLM-L6-v2 (384 dimensions)\n"
        response += "Activation Threshold: 0.7\n"
        response += "Bridge Discovery K: 5\n"
        response += "Max Activations: 50\n"

    response += f"\n\n🧠 The cognitive memory system is operating with {memory_counts.get('total', 0)} total memories."

    return response


def create_error_response(
    error_type: str, message: str, retry_seconds: int | None = None
) -> dict[str, Any]:
    """
    Create a standardized error response.

    Args:
        error_type: Type of error (e.g., 'system_unavailable', 'invalid_input')
        message: Human-readable error message
        retry_seconds: Optional retry delay for transient errors

    Returns:
        Structured error response
    """
    response = {"success": False, "error": error_type, "message": message}

    if retry_seconds:
        response["retry_in_seconds"] = retry_seconds

    return response
