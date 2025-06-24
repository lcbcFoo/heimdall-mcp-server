#!/usr/bin/env python3
"""
Standalone MCP Server for Cognitive Memory System.

This module implements a Model Context Protocol (MCP) server that provides
LLMs with secure, controlled access to cognitive memory operations through
a standardized interface, enabling persistent memory across conversations
and intelligent knowledge consolidation.

This is a standalone server that uses the operations layer directly,
making it AI-agnostic and suitable for use with Claude Code, Cline, Continue, etc.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from typing import Any

import uvicorn
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
)
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from cognitive_memory.core.interfaces import CognitiveSystem
from cognitive_memory.core.version import get_version_info
from cognitive_memory.main import initialize_system, initialize_with_config
from heimdall.display_utils import format_source_info
from heimdall.operations import CognitiveOperations

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HeimdallMCPServer:
    """
    Standalone MCP Server for cognitive memory system using operations layer.

    Provides LLMs with access to cognitive memory operations through
    the Model Context Protocol, including storing experiences,
    recalling memories, recording session lessons, and checking system status.

    This server uses the operations layer directly for clean separation of concerns.
    """

    def __init__(self, cognitive_system: CognitiveSystem):
        """
        Initialize MCP server with cognitive system.

        Args:
            cognitive_system: The cognitive system interface to wrap
        """
        self.cognitive_system = cognitive_system
        self.operations = CognitiveOperations(cognitive_system)
        self.server: Server = Server("heimdall-cognitive-memory")
        self._register_handlers()

        logger.info("Heimdall MCP Server initialized")

    def _format_memory_results(self, result_data: dict[str, Any]) -> str:
        """
        Format memory retrieval results optimized for LLM consumption using JSON structure.

        Args:
            result_data: Dictionary from operations.retrieve_memories()

        Returns:
            str: JSON-structured formatted string optimized for LLM processing
        """
        if not result_data["success"]:
            return f"❌ Error retrieving memories: {result_data['error']}"

        if result_data["total_count"] == 0:
            return f"No memories found for query: '{result_data['query']}'"

        formatted_results: dict[str, Any] = {
            "query": result_data["query"],
            "total_results": result_data["total_count"],
            "memories": {},
        }

        # Process each memory type
        for memory_type in ["core", "peripheral", "bridge"]:
            memories = result_data.get(memory_type, [])
            if memories:
                formatted_results["memories"][memory_type] = []

                for memory_item in memories:
                    if memory_type == "bridge" and hasattr(memory_item, "memory"):
                        # Handle BridgeMemory objects
                        bridge_mem = memory_item
                        memory = bridge_mem.memory

                        memory_data = {
                            "type": "bridge",
                            "content": memory.content,
                            "metadata": {
                                "id": memory.id,
                                "hierarchy_level": memory.hierarchy_level,
                                "memory_type": memory.memory_type,
                                "novelty_score": round(bridge_mem.novelty_score, 3),
                                "bridge_score": round(bridge_mem.bridge_score, 3),
                                "connection_potential": round(
                                    bridge_mem.connection_potential, 3
                                ),
                                "source": format_source_info(memory),
                                "created_date": memory.created_date.isoformat()
                                if memory.created_date
                                else None,
                                "last_accessed": memory.last_accessed.isoformat()
                                if memory.last_accessed
                                else None,
                                "access_count": memory.access_count,
                                "importance_score": memory.importance_score,
                                "tags": memory.tags,
                            },
                        }

                    else:
                        # Handle regular CognitiveMemory objects
                        memory = memory_item

                        # Use similarity score from metadata if available, otherwise fallback to memory strength
                        score = memory.metadata.get("similarity_score", memory.strength)

                        memory_data = {
                            "type": memory.memory_type,
                            "content": memory.content,
                            "metadata": {
                                "id": memory.id,
                                "hierarchy_level": memory.hierarchy_level,
                                "strength": round(score, 3),
                                "source": format_source_info(memory),
                                "created_date": memory.created_date.isoformat()
                                if memory.created_date
                                else None,
                                "last_accessed": memory.last_accessed.isoformat()
                                if memory.last_accessed
                                else None,
                                "access_count": memory.access_count,
                                "importance_score": memory.importance_score,
                                "tags": memory.tags,
                            },
                        }

                    formatted_results["memories"][memory_type].append(memory_data)

        return json.dumps(formatted_results, ensure_ascii=False, separators=(",", ":"))

    def _register_handlers(self) -> None:
        """Register MCP protocol handlers."""

        @self.server.list_tools()  # type: ignore[misc]
        async def list_tools() -> list[Tool]:
            """List available MCP tools."""
            return [
                Tool(
                    name="store_memory",
                    description="Store new experiences or knowledge in cognitive memory for future recall",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Content to store in cognitive memory",
                            },
                            "context": {
                                "type": "object",
                                "description": "Optional context and metadata",
                                "properties": {
                                    "hierarchy_level": {
                                        "type": "integer",
                                        "description": "Memory hierarchy level: 0=concept, 1=context, 2=episode",
                                        "minimum": 0,
                                        "maximum": 2,
                                    },
                                    "memory_type": {
                                        "type": "string",
                                        "enum": ["episodic", "semantic"],
                                        "description": "Type of memory to store",
                                    },
                                    "importance_score": {
                                        "type": "number",
                                        "minimum": 0.0,
                                        "maximum": 1.0,
                                        "description": "Importance score for the memory (0.0-1.0)",
                                    },
                                    "tags": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Categorization tags for the memory",
                                    },
                                    "source_info": {
                                        "type": "string",
                                        "description": "Description of the memory source",
                                    },
                                },
                            },
                        },
                        "required": ["text"],
                    },
                ),
                Tool(
                    name="recall_memories",
                    description="Retrieve memories based on query with rich contextual information",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query for memory retrieval",
                            },
                            "types": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": ["core", "peripheral", "bridge"],
                                },
                                "description": "Types of memories to retrieve (default: all)",
                            },
                            "max_results": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 50,
                                "description": "Maximum number of memories to return (default: 10)",
                            },
                            "include_bridges": {
                                "type": "boolean",
                                "description": "Include bridge discoveries for novel connections (default: true)",
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="session_lessons",
                    description="Capture and consolidate key learnings from current session for future reference. This tool encourages metacognitive reflection - thinking about what you've learned that would be valuable after 'critical amnesia' between sessions.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "lesson_content": {
                                "type": "string",
                                "description": "Key insight, pattern, or learning from this session",
                            },
                            "lesson_type": {
                                "type": "string",
                                "enum": [
                                    "discovery",
                                    "pattern",
                                    "solution",
                                    "warning",
                                    "context",
                                ],
                                "description": "Type of lesson: discovery (new insights), pattern (systematic approaches), solution (technical fixes), warning (things to avoid), context (situational information)",
                            },
                            "session_context": {
                                "type": "string",
                                "description": "What was being worked on or the situation context",
                            },
                            "importance": {
                                "type": "string",
                                "enum": ["low", "medium", "high", "critical"],
                                "description": "Importance level for future retrieval prioritization",
                            },
                        },
                        "required": ["lesson_content"],
                    },
                ),
                Tool(
                    name="memory_status",
                    description="Get cognitive memory system health and statistics",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "detailed": {
                                "type": "boolean",
                                "description": "Include detailed configuration information (default: false)",
                            }
                        },
                    },
                ),
            ]

        @self.server.call_tool()  # type: ignore[misc]
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Handle MCP tool calls."""
            try:
                if name == "store_memory":
                    return await self._store_memory(arguments)
                elif name == "recall_memories":
                    return await self._recall_memories(arguments)
                elif name == "session_lessons":
                    return await self._session_lessons(arguments)
                elif name == "memory_status":
                    return await self._memory_status(arguments)
                else:
                    return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]
            except Exception as e:
                logger.error(f"Error in tool {name}: {e}")
                return [
                    TextContent(
                        type="text", text=f"❌ Error executing {name}: {str(e)}"
                    )
                ]

    async def _store_memory(self, arguments: dict) -> list[TextContent]:
        """Handle store_memory tool calls."""
        text = arguments.get("text", "")
        context = arguments.get("context", {})

        if not text.strip():
            return [
                TextContent(type="text", text="❌ Error: Memory text cannot be empty")
            ]

        try:
            # Add source_type for deterministic content-type decay detection
            if "source_type" not in context:
                context["source_type"] = "store_memory"

            # Store the experience using operations layer
            result = self.operations.store_experience(text=text, context=context)

            if result["success"]:
                # Get hierarchy level and memory type from result
                hierarchy_level = result["hierarchy_level"]
                memory_type = result["memory_type"]

                level_names = {0: "L0 (Concept)", 1: "L1 (Context)", 2: "L2 (Episode)"}
                level_name = level_names.get(hierarchy_level, f"L{hierarchy_level}")

                response = f"✓ Stored: {level_name}, {memory_type}"

                return [TextContent(type="text", text=response)]
            else:
                return [
                    TextContent(
                        type="text",
                        text=f"❌ Failed to store experience: {result['error']}",
                    )
                ]

        except Exception as e:
            logger.error(f"Error storing memory: {e}")
            return [TextContent(type="text", text=f"❌ Error storing memory: {str(e)}")]

    async def _recall_memories(self, arguments: dict) -> list[TextContent]:
        """Handle recall_memories tool calls."""
        query = arguments.get("query", "")
        types_filter = arguments.get("types", None)  # Use None for all types by default
        max_results = arguments.get("max_results", 10)
        # include_bridges = arguments.get("include_bridges", True)  # TODO: Implement bridge discovery

        if not query.strip():
            return [TextContent(type="text", text="❌ Error: Query cannot be empty")]

        try:
            # Retrieve memories using operations layer
            result = self.operations.retrieve_memories(
                query=query, types=types_filter, limit=max_results
            )

            if not result["success"]:
                return [
                    TextContent(
                        type="text",
                        text=f"❌ Error retrieving memories: {result['error']}",
                    )
                ]

            # Format the response as JSON for optimal LLM processing
            formatted_response = self._format_memory_results(result)
            return [TextContent(type="text", text=formatted_response)]

        except Exception as e:
            logger.error(f"Error recalling memories: {e}")
            return [
                TextContent(type="text", text=f"❌ Error recalling memories: {str(e)}")
            ]

    async def _session_lessons(self, arguments: dict) -> list[TextContent]:
        """Handle session_lessons tool calls."""
        lesson_content = arguments.get("lesson_content", "")
        lesson_type = arguments.get("lesson_type", "discovery")
        session_context = arguments.get("session_context", "")
        importance = arguments.get("importance", "medium")

        if not lesson_content.strip():
            return [
                TextContent(
                    type="text", text="❌ Error: Lesson content cannot be empty"
                )
            ]

        # Provide metacognitive prompting guidance
        if len(lesson_content) < 20:  # Very short lesson
            return [
                TextContent(
                    type="text",
                    text="❌ Lesson too brief. Expand with specific insights, patterns, or context for future sessions.",
                )
            ]

        try:
            # Create rich metadata for session lesson
            lesson_metadata = {
                "loader_type": "session_lesson",
                "lesson_type": lesson_type,
                "session_context": session_context,
                "importance_level": importance,
                "stored_at": datetime.now().isoformat(),
            }

            # Map importance to score
            importance_scores = {
                "low": 0.3,
                "medium": 0.6,
                "high": 0.8,
                "critical": 1.0,
            }

            context = {
                "source_type": "session_lesson",  # For deterministic content-type decay detection
                "hierarchy_level": 1,  # Context level for lessons
                "memory_type": "semantic",  # Lessons are semantic knowledge
                "importance_score": importance_scores.get(importance, 0.6),
                "tags": ["session_lesson", lesson_type],
                "source_info": f"Session Lesson ({lesson_type})",
                "metadata": lesson_metadata,
            }

            # Store the lesson using operations layer
            result = self.operations.store_experience(
                text=lesson_content, context=context
            )

            if result["success"]:
                response = f"✓ Lesson recorded: {lesson_type}, {importance}"

                return [TextContent(type="text", text=response)]
            else:
                return [
                    TextContent(
                        type="text",
                        text=f"❌ Failed to store session lesson: {result['error']}",
                    )
                ]

        except Exception as e:
            logger.error(f"Error storing session lesson: {e}")
            return [
                TextContent(
                    type="text", text=f"❌ Error storing session lesson: {str(e)}"
                )
            ]

    async def _memory_status(self, arguments: dict) -> list[TextContent]:
        """Handle memory_status tool calls."""
        detailed = arguments.get("detailed", False)

        try:
            # Get status using operations layer
            result = self.operations.get_system_status(detailed=detailed)

            if not result["success"]:
                return [
                    TextContent(
                        type="text",
                        text=f"❌ Unable to retrieve system status: {result['error']}",
                    )
                ]

            # Format status as JSON for optimal LLM processing
            version_info = get_version_info()
            formatted_status = {
                "system_status": "healthy",
                "version": version_info,
                "memory_counts": result["memory_counts"],
                "timestamp": datetime.now().isoformat(),
            }

            if detailed:
                # Add detailed configuration
                formatted_status.update(
                    {
                        "system_config": result.get("system_config", {}),
                        "storage_stats": result.get("storage_stats", {}),
                        "embedding_info": result.get("embedding_info", {}),
                        "detailed_config": {
                            "embedding_model": "all-MiniLM-L6-v2",
                            "embedding_dimensions": 384,
                            "activation_threshold": 0.7,
                            "bridge_discovery_k": 5,
                            "max_activations": 50,
                        },
                    }
                )

            response = json.dumps(
                formatted_status, ensure_ascii=False, separators=(",", ":")
            )
            return [TextContent(type="text", text=response)]

        except Exception as e:
            logger.error(f"Error getting memory status: {e}")
            return [
                TextContent(
                    type="text", text=f"❌ Error getting system status: {str(e)}"
                )
            ]

    async def run_stdio(self) -> None:
        """Run MCP server with stdio transport."""
        logger.info("Starting Heimdall MCP Server (stdio mode)")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, write_stream, self.server.create_initialization_options()
            )

    async def run_http(self, host: str = "127.0.0.1", port: int = 8080) -> None:
        """Run MCP server with HTTP transport."""
        logger.info(f"Starting Heimdall MCP Server (HTTP mode on {host}:{port})")

        # Health check endpoint
        async def health_check(request: Any) -> Any:
            """Health check endpoint for container monitoring."""
            try:
                # Basic health check - verify cognitive system is responsive
                status_result = self.operations.get_system_status()
                if status_result["success"]:
                    return JSONResponse(
                        {
                            "status": "healthy",
                            "service": "heimdall-mcp-server",
                            "timestamp": datetime.now().isoformat(),
                            "version": get_version_info(),
                        }
                    )
                else:
                    return JSONResponse(
                        {
                            "status": "unhealthy",
                            "service": "heimdall-mcp-server",
                            "error": status_result["error"],
                            "timestamp": datetime.now().isoformat(),
                        },
                        status_code=503,
                    )
            except Exception as e:
                return JSONResponse(
                    {
                        "status": "unhealthy",
                        "service": "heimdall-mcp-server",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    },
                    status_code=503,
                )

        # Create Starlette app with health endpoint
        app = Starlette(
            routes=[
                Route("/health", health_check, methods=["GET"]),
                Route("/status", health_check, methods=["GET"]),  # Alias for health
            ]
        )

        # Create SSE transport for MCP
        transport = SseServerTransport("/mcp")

        # Mount MCP server on the transport
        app.mount("/mcp", transport.create_app(self.server))

        # Run the server
        config = uvicorn.Config(
            app=app, host=host, port=port, log_level="info", access_log=True
        )
        server = uvicorn.Server(config)
        await server.serve()


async def main() -> None:
    """Main entry point for standalone MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Heimdall Cognitive Memory MCP Server")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument(
        "--mode",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="HTTP port (only used in http mode)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="HTTP host (only used in http mode)",
    )

    args = parser.parse_args()

    try:
        # Initialize cognitive system
        if args.config:
            cognitive_system = initialize_with_config(args.config)
        else:
            cognitive_system = initialize_system("default")

        # Create and run MCP server
        mcp_server = HeimdallMCPServer(cognitive_system)

        if args.mode == "stdio":
            await mcp_server.run_stdio()
        elif args.mode == "http":
            await mcp_server.run_http(host=args.host, port=args.port)
        else:
            logger.error(f"Unknown transport mode: {args.mode}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Failed to start Heimdall MCP server: {e}")
        sys.exit(1)


def run_server(
    cognitive_system: CognitiveSystem, port: int | None = None, host: str = "127.0.0.1"
) -> None:
    """
    Run the MCP server with the given cognitive system.

    Args:
        cognitive_system: The cognitive system to use
        port: Optional port for HTTP mode (None for stdio)
        host: Host to bind to for HTTP mode
    """
    # Create MCP server instance
    mcp_server = HeimdallMCPServer(cognitive_system)

    if port:
        # Run in HTTP mode
        asyncio.run(mcp_server.run_http(host=host, port=port))
    else:
        # Run in stdio mode
        asyncio.run(mcp_server.run_stdio())


if __name__ == "__main__":
    asyncio.run(main())
