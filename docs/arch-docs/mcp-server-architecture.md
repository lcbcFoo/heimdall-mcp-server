# Heimdall MCP Server: Cognitive Memory for LLMs

## Overview

The Heimdall MCP Server provides LLMs with persistent memory capabilities across conversations through the Model Context Protocol (MCP). It enables AI assistants to store experiences, recall relevant knowledge, and build long-term understanding of projects and contexts.

**Architecture**: Standalone MCP server using operations layer for clean separation of concerns
**Installation**: Standard Python package via `pip install heimdall-mcp`

## Quick Installation & Setup

### Step 1: Install Heimdall
```bash
# Install via pip (requires Python 3.10+)
pip install heimdall-mcp

# Verify installation
heimdall --version
```

### Step 2: Initialize Project
```bash
# Navigate to your project directory
cd /path/to/your/project

# Initialize Heimdall for this project (auto-starts Qdrant if needed)
heimdall project init

# Verify system health
heimdall doctor
```

### Step 3: Configure Your LLM Client

Choose your LLM client and add the MCP server configuration:

#### Claude Code
Add to `~/.config/claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "heimdall": {
      "command": "python",
      "args": ["-m", "heimdall.mcp_server"]
    }
  }
}
```

#### Cursor
1. Open Cursor Settings → Features → MCP
2. Add server:
   - **Name**: `heimdall`
   - **Command**: `python`
   - **Args**: `["-m", "heimdall.mcp_server"]`

#### Cline (VS Code Extension)
Add to Cline MCP settings:
```json
{
  "mcpServers": {
    "heimdall": {
      "command": "python",
      "args": ["-m", "heimdall.mcp_server"]
    }
  }
}
```

#### Continue (VS Code Extension)
Add to `config.json`:
```json
{
  "models": [...],
  "mcpServers": {
    "heimdall": {
      "command": "python",
      "args": ["-m", "heimdall.mcp_server"]
    }
  }
}
```

#### Roo AI
```bash
roo config mcp add heimdall python -m heimdall.mcp_server
```

#### Other MCP Clients
Generic configuration:
- **Command**: `python`
- **Args**: `["-m", "heimdall.mcp_server"]`
- **Transport**: `stdio`

### Step 4: Restart Your LLM Client

After configuration, restart your LLM client. You should see 4 new memory tools available:

- 🧠 **store_memory** - Store experiences and insights
- 🔍 **recall_memories** - Search and retrieve relevant memories
- 📚 **session_lessons** - Record key learnings for future sessions
- 📊 **memory_status** - Check system health and statistics

## Architecture

### Current Implementation

The Heimdall MCP Server uses a **clean operations-first architecture** with standalone deployment:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   LLM Client    │    │ Heimdall MCP    │    │ Operations      │
│ (Claude, etc.)  │◄──►│    Server       │◄──►│    Layer        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                               │                        │
                               │                        ▼
                               │               ┌─────────────────┐
                               │               │ CognitiveSystem │
                               │               │   (Core Logic)  │
                               │               └─────────────────┘
                               ▼                        │
                    ┌─────────────────────────┐        │
                    │ Shared Qdrant Instance  │◄───────┘
                    │ Project-Scoped Collections │
                    └─────────────────────────┘
```

### Key Components

1. **Standalone MCP Server** (`heimdall/mcp_server.py`)
   - No CLI dependencies - uses operations layer directly
   - AI-agnostic - works with any MCP client
   - Stdio transport for local integrations

2. **Operations Layer** (`heimdall/operations.py`)
   - Pure business logic, no interface dependencies
   - Returns structured data for flexible formatting
   - Single source of truth for cognitive operations

3. **Shared Qdrant Architecture**
   - Single Docker container serving all projects
   - Project isolation via collection namespacing
   - Automatic service management

4. **Project-Scoped Collections**
   - Each project gets: `{project_id}_concepts`, `{project_id}_contexts`, `{project_id}_episodes`
   - Isolation without container overhead
   - Easy project management and cleanup

### Technology Stack

- **MCP Protocol**: Official Python SDK for standardized LLM integration
- **Transport**: stdio (Standard Input/Output) for local clients

## Available MCP Tools

### 1. store_memory
Store new experiences or knowledge in cognitive memory.

**Input Schema**:
```json
{
  "text": "Content to store in memory",
  "context": {
    "hierarchy_level": 2,
    "memory_type": "episodic",
    "importance_score": 0.8,
    "tags": ["debugging", "react"],
    "source_info": "React debugging session"
  }
}
```

**Example Response**:
```
✓ Stored: L2 (Episode), episodic
```

### 2. recall_memories
Retrieve memories based on query with rich contextual information.

**Input Schema**:
```json
{
  "query": "React performance optimization",
  "types": ["core", "peripheral", "bridge"],
  "max_results": 10,
  "include_bridges": true
}
```

**Example Response**:
```json
{
  "query": "React performance optimization",
  "total_results": 5,
  "memories": {
    "core": [
      {
        "type": "episodic",
        "content": "Found that React components re-render unnecessarily when...",
        "metadata": {
          "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
          "hierarchy_level": 1,
          "strength": 0.89,
          "source": "💭 Manual Entry",
          "created_date": "2024-01-15T16:30:00Z",
          "tags": ["react", "performance"]
        }
      }
    ],
    "peripheral": [...],
    "bridge": [...]
  }
}
```

### 3. session_lessons
Capture key learnings from current session for future reference.

**Input Schema**:
```json
{
  "lesson_content": "When debugging API integration issues, always check network tab first...",
  "lesson_type": "pattern",
  "session_context": "Working on payment API integration",
  "importance": "high"
}
```

**Example Response**:
```
✓ Lesson recorded: pattern, high
```

### 4. memory_status
Get cognitive memory system health and statistics.

**Input Schema**:
```json
{
  "detailed": true
}
```

**Example Response**:
```json
{
  "system_status": "healthy",
  "version": "0.2.2",
  "memory_counts": {
    "total": 1247,
    "episodic": 856,
    "semantic": 391
  },
  "timestamp": "2024-01-15T17:50:00Z"
}
```

## Troubleshooting

### Common Issues

#### "Qdrant collections not found"
```bash
# Initialize project collections
heimdall project init

# Or restart Qdrant
heimdall qdrant restart
```

#### "MCP server not responding"
```bash
# Check if system is healthy
heimdall doctor

# Verify Qdrant is running
heimdall qdrant status

# Check project initialization
heimdall project list
```

#### "Python module not found"
```bash
# Verify installation
pip show heimdall-mcp

# Reinstall if needed
pip install --upgrade heimdall-mcp

# Check Python path
python -c "import heimdall.mcp_server; print('OK')"
```

#### "Docker not available"
```bash
# Install Docker and start daemon
# On macOS: Docker Desktop
# On Linux: sudo systemctl start docker
# On Windows: Docker Desktop

# Verify Docker is running
docker --version
docker ps
```

## Development & Extension

### Adding New MCP Tools

To extend the MCP server with new tools:

1. Add method to `CognitiveOperations` class
2. Register new tool in `HeimdallMCPServer._register_handlers()`
3. Implement tool handler method
4. Add unit tests

### Testing

```bash
# Run unit tests
python -m pytest tests/unit/heimdall/

# Test MCP server directly
python -m heimdall.mcp_server --help

# Test operations layer
python -c "
from heimdall.operations import CognitiveOperations
from cognitive_memory.main import initialize_system
ops = CognitiveOperations(initialize_system('default'))
print(ops.get_system_status())
"
```
