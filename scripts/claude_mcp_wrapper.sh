#!/bin/bash

# MCP wrapper for shared Qdrant architecture
# Uses host-installed memory_system command instead of per-project containers

# Run MCP server on host with clean stdio (all logs to /dev/null)
if command -v memory_system >/dev/null 2>&1; then
    exec memory_system serve mcp 2>/dev/null
else
    echo "Error: memory_system command not found. Please install heimdall-mcp package." >&2
    exit 1
fi
