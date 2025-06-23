#!/bin/bash
set -e

# Setup for Claude Code MCP integration with shared Qdrant architecture
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_HASH=$(echo "$(pwd)" | sha256sum | cut -c1-8)
REPO_NAME=$(basename "$(pwd)")
MCP_NAME="heimdall-$REPO_NAME-$PROJECT_HASH"
WRAPPER_SCRIPT="$SCRIPT_DIR/scripts/claude_mcp_wrapper.sh"

echo "🧠 Setting up Claude Code MCP for Heimdall..."

# Initialize project with shared Qdrant architecture
echo "🔧 Initializing project memory..."
if command -v memory_system >/dev/null 2>&1; then
    memory_system project init --no-auto-start-qdrant || echo "⚠️  Project already initialized"
else
    echo "⚠️  memory_system command not found. Please install heimdall-mcp package first."
    echo "   Run: pip install heimdall-mcp"
fi

# Configure Claude MCP
if claude mcp list | grep -q "$MCP_NAME"; then
    echo "⚠️  MCP already configured: $MCP_NAME"
else
    claude mcp add --scope project --transport stdio "$MCP_NAME" "$WRAPPER_SCRIPT"
    echo "✅ MCP configured: $MCP_NAME"
fi

echo "✅ Setup complete! MCP tools available in Claude Code."
