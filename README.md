# Heimdall MCP Server - Your AI Coding Assistant's Long-Term Memory

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](hhttps://github.com/lcbcFoo/heimdall-mcp-server/blob/main/README.mdttps://opensource.org/licenses/Apache-2.0)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)
[![MCP Protocol](https://img.shields.io/badge/MCP-compatible-brightgreen.svg)](https://modelcontextprotocol.io/)
[![Heimdall Demo Video](https://img.shields.io/badge/YouTube-red)](https://youtu.be/7X1gntAXsao)

**The Problem:** Your AI coding assistant has short-lived memory. Every chat session starts from a blank slate.

**The Solution:** Heimdall gives your LLM a persistent, growing, cognitive memory of your specific codebase, lessons and memories carry over time.


https://github.com/user-attachments/assets/120b3d32-72d1-4d42-b3ab-285e8a711981


## Key Features

- 🧠 **Context-Rich Memory**: Heimdall learns from your documentation, session insights, and development history, allowing your LLM to recall specific solutions and architectural patterns across conversations.
- 📚 **Git-Aware Context**: It indexes your project's entire git history, understanding not just what changed, but also who changed it, when, and context.
- 🔗 **Isolated & Organized**: Each project gets its own isolated memory space, ensuring that context from one project doesn't leak into another.
- ⚡ **Efficient Integration**: Built on the Model Context Protocol (MCP), it provides a standardized, low-overhead way for LLMs to access this powerful memory.

## 🚀 Getting Started

**Prerequisites**: Python 3.10+ and Docker (for Qdrant vector database).

Heimdall uses a shared Qdrant architecture - one Qdrant instance serves all your projects with isolated collections.

### 1. Install Heimdall

```bash
pip install heimdall-mcp
```

### 2. Navigate to Your Project

```bash
cd /path/to/your/project
```

### 3. Initialize Project Memory

This command sets up project-specific collections in the shared Qdrant instance:

```bash
# Initialize project and start Qdrant if needed
memory_system project init

# For Claude Code integration specifically
# This creates MCP server configuration
setup_claude_code_mcp.sh
```

**Note: this creates a `.heimdall/` directory in your project for configuration - you can commit this!**

### 4. Load Project Knowledge

Load your project's documentation and git history:

```bash
# Load all documentation from docs/ directory or specific documents you want
memory_system load docs/

# Load git commit history
memory_system load-git

# Or load everything at once
cognitive-cli load .
```

Your project's memory is now active and ready for your LLM.

#### Automatic File Monitoring

Start automatic file change detection:

```bash
# Start monitoring service
memory_system monitor start

# Check status
memory_system monitor status
```

### 5. Real-time Git Integration

Install git hooks for automatic memory updates on commits:

```bash
# Install the post-commit hook (Python-based, cross-platform)
python scripts/git_hook_installer.py --install
```

**Note**: If you have existing post-commit hooks, they'll be safely chained and preserved.

With git hooks configured, new memories are created automatically from commits. To remove:

```bash
python scripts/git_hook_installer.py --uninstall
```

#### Manual Git Updates

Load new commits manually:

```bash
# Load only new commits since last update
memory_system load-git incremental
```

## 🧹 Cleanup

To remove Heimdall from a project:

```bash
# Remove project collections from shared Qdrant
memory_system project clean <project_id>

# List projects to see available project IDs
memory_system project list

# Remove local configuration
rm -rf .heimdall/
```

This cleanly removes project-specific data while preserving the shared Qdrant instance for other projects.

## ⚙️ How It Works Under the Hood

Heimdall extracts unstructured knowledge from your documentation and structured data from your git history. This information is vectorized and stored in a Qdrant database. The LLM can then query this database using a simple set of tools to retrieve relevant, context-aware information.

```mermaid
graph TD
    %% Main client outside the server architecture
    AI_Assistant["🤖 AI Assistant (e.g., Claude)"]

    %% Top-level subgraph for the entire server
    subgraph Heimdall MCP Server Architecture

        %% 1. Application Interface Layer
        subgraph Application Interface
            MCP_Server["MCP Server (interfaces/mcp_server.py)"]
            CLI["CognitiveCLI (interfaces/cli.py)"]
            style MCP_Server fill:#b2ebf2,stroke:#00acc1,color:#212121
            style CLI fill:#b2ebf2,stroke:#00acc1,color:#212121
        end

        %% 2. Core Logic Engine
        style Cognitive_System fill:#ccff90,stroke:#689f38,color:#212121
        Cognitive_System["🧠 CognitiveSystem (core/cognitive_system.py)<br/>"]

        %% 3. Storage Layer (components side-by-side)
        subgraph Storage Layer
            Qdrant["🗂️ Qdrant Storage<br/><hr/>- Vector Similarity Search<br/>- Multi-dimensional Encoding"]
            SQLite["🗃️ SQLite Persistence<br/><hr/>- Memory Metadata & Connections<br/>- Caching & Retrieval Stats"]
        end

        %% 4. Output Formatting
        style Formatted_Response fill:#fff9c4,stroke:#fbc02d,color:#212121
        Formatted_Response["📦 Formatted MCP Response<br/><i>{ core, peripheral, bridge }</i>"]

        %% Define internal flow
        MCP_Server -- calls --> CLI
        CLI -- calls --> Cognitive_System

        Cognitive_System -- "1\. Vector search for candidates" --> Qdrant
        Cognitive_System -- "2\. Hydrates with metadata" --> SQLite
        Cognitive_System -- "3\. Performs Bridge Discovery" --> Formatted_Response

    end

    %% Define overall request/response flow between client and server
    AI_Assistant -- "recall_memorie" --> MCP_Server
    Formatted_Response -- "Returns structured memories" --> AI_Assistant

    %% --- Styling Block ---

    %% 1. Node Styling using Class Definitions
    classDef aiClientStyle fill:#dbeafe,stroke:#3b82f6,color:#1e3a8a
    classDef interfaceNodeStyle fill:#cffafe,stroke:#22d3ee,color:#0e7490
    classDef coreLogicStyle fill:#dcfce7,stroke:#4ade80,color:#166534
    classDef qdrantNodeStyle fill:#ede9fe,stroke:#a78bfa,color:#5b21b6
    classDef sqliteNodeStyle fill:#fee2e2,stroke:#f87171,color:#991b1b
    classDef responseNodeStyle fill:#fef9c3,stroke:#facc15,color:#854d0e

    %% 2. Assigning Classes to Nodes
    class AI_Assistant aiClientStyle
    class MCP_Server,CLI interfaceNodeStyle
    class Cognitive_System coreLogicStyle
    class Qdrant qdrantNodeStyle
    class SQLite sqliteNodeStyle
    class Formatted_Response responseNodeStyle

    %% 3. Link (Arrow) Styling
    %% Note: Styling edge label text is not reliably supported. This styles the arrow lines themselves.
    %% Primary request/response flow (links 0 and 1)
    linkStyle 0,1 stroke:#3b82f6,stroke-width:2px
    %% Internal application calls (links 2 and 3)
    linkStyle 2,3 stroke:#22d3ee,stroke-width:2px,stroke-dasharray: 5 5
    %% Internal data access calls (links 4 and 5)
    linkStyle 4,5 stroke:#9ca3af,stroke-width:2px
    %% Final processing call (link 6)
    linkStyle 6 stroke:#4ade80,stroke-width:2px

```

## LLM Tool Reference

You can instruct your LLM to use the following four tools to interact with its memory:

| Tool              | Description                                                          |
| :---------------- | :------------------------------------------------------------------- |
| `store_memory`    | Stores a new piece of information, such as an insight or a solution. |
| `recall_memories` | Performs a semantic search for relevant memories based on a query.   |
| `session_lessons` | Records a key takeaway from the current session for future use.      |
| `memory_status`   | Checks the health and statistics of the memory system.               |


## 💡 Best Practices

To maximize the effectiveness of Heimdall:

  * **Provide Quality Documentation:** Load detailed documentation with `memory_system load docs/`. Think architecture decision records, style guides, and API documentation.
  * **Use Project Isolation:** Each project gets its own collections in the shared Qdrant instance - no cross-project contamination.
  * **Maintain Good Git Hygiene:** Write clear and descriptive commit messages. A message like `feat(api): add user authentication endpoint` is far more valuable than `more stuff`.
  * **Monitor Your Memory:** Use `memory_status` tool regularly to check system health and memory statistics.
  * **Guide Your Assistant:** Use a system prompt (like a `CLAUDE.md` file) to instruct your LLM on *how* and *when* to use the available memory tools.

## Technology Stack:

- Vector Storage: Qdrant
- Sentiment analysis: NRCLex emotion lexicon
- Semantic analysis: spaCy
- Integration: Model Context Protocol (MCP)

## 🗺️Short Term Roadmap

  * [x] ~~Git `post-commit` hook for automatic, real-time memory updates~~ ✅ **Completed**
  * [x] ~~Watcher to auto-detect and load new documents in the `.heimdall-mcp` directory.~~ ✅ **Completed**
  * [x] ~~Release v0.1.0 publicly~~ ✅ **Completed**

## License

This project is licensed under the Apache 2.0 License.
