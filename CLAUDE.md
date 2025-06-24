## Project Overview

**Heimdall MCP Server** - An MCP server that provides Large Language Models with persistent memory across conversations. The system learns patterns from git history, stores insights from sessions, and enables intelligent knowledge consolidation for project-specific contexts.

**Core Capabilities:**
- Multi-dimensional memory encoding (semantic, emotional, temporal, contextual)
- Hierarchical memory storage (L0: Concepts, L1: Contexts, L2: Episodes)
- Bridge discovery for serendipitous connections between distant concepts
- Git pattern extraction (co-change patterns, maintenance hotspots, solution patterns)
- Session lessons framework for metacognitive learning

### Architecture Documents

- Architecture documents can be found on `docs/arch-docs`

## System Architecture

### Memory Hierarchy (3-Level System)
- **L0 (Concepts)**: High-level abstractions, principles, patterns
- **L1 (Contexts)**: Mid-level scenarios, domain knowledge, contextual information
- **L2 (Episodes)**: Specific experiences, interactions, detailed memories

### Core Components
- **Multi-Dimensional Encoder**: Converts experiences to rich vectors (semantic + emotional + temporal + contextual)
- **Dual Memory System**: Episodic (fast decay) + Semantic (slow decay) with consolidation
- **Context-Driven Activation**: Spreads activation through memory networks for retrieval
- **Bridge Discovery**: Finds unexpected connections between distant concepts

### Technology Stack
- **Vector Storage**: Qdrant with project-specific collections
- **Embeddings**: Sentence-BERT (all-MiniLM-L6-v2) + multi-dimensional extraction
- **Persistence**: SQLite for metadata, connections, and usage statistics
- **Integration**: MCP protocol for Claude Code integration

## Key File Structure

```
cognitive_memory/
├── core/                    # Core cognitive system interfaces
│   ├── cognitive_system.py  # Main CognitiveSystem class
│   ├── memory.py            # CognitiveMemory, BridgeMemory data structures
│   ├── interfaces.py        # Abstract interfaces (MemoryLoader, etc.)
│   └── config.py           # System configuration
├── encoding/               # Multi-dimensional encoding
│   ├── cognitive_encoder.py # Main encoder with dimension fusion
│   ├── sentence_bert.py    # SentenceBERT implementation
│   └── dimensions.py       # Rule-based dimension extraction
├── storage/                # Memory persistence
│   ├── qdrant_storage.py   # Vector database operations
│   ├── sqlite_persistence.py # Metadata storage
│   └── dual_memory.py      # Episodic/semantic memory system
├── retrieval/              # Memory retrieval and activation
│   ├── contextual_retrieval.py # Main retrieval coordinator
│   ├── basic_activation.py     # Activation spreading
│   └── bridge_discovery.py     # Serendipitous connections
├── git_analysis/           # Git commit storage
│   ├── commit.py           # Commit and FileChange data structures
│   ├── commit_loader.py    # Convert commits to memories
│   ├── history_miner.py    # Git history extraction
│   └── security.py         # Git data validation and sanitization
└── loaders/               # Memory loading interfaces
    ├── git_loader.py      # Git repository integration
    ├── markdown_loader.py # Main markdown processing coordinator
    └── markdown/          # Specialized markdown components
        ├── content_analyzer.py    # Linguistic analysis and classification
        ├── document_parser.py     # Markdown parsing and tree construction
        ├── memory_factory.py      # Memory creation and content assembly
        ├── connection_extractor.py # Relationship analysis
        └── chunk_processor.py     # Document chunking and grouping

heimdall/
├── cli.py                    # Unified CLI entry point (heimdall command)
├── operations.py             # Pure operations layer - business logic
├── mcp_server.py            # Standalone MCP server (heimdall-mcp command)
├── interactive_shell.py     # Interactive memory shell
├── display_utils.py         # Rich terminal formatting utilities
├── cli_commands/            # Modular CLI command implementations
│   ├── cognitive_commands.py   # Memory operations (store, recall, load, status)
│   ├── health_commands.py      # Health checks and shell access
│   ├── qdrant_commands.py      # Qdrant service management
│   ├── monitor_commands.py     # File monitoring service
│   └── project_commands.py     # Project collection management
└── cognitive_system/        # Service management utilities
    ├── service_manager.py      # Docker/Qdrant service management
    ├── monitoring_service.py   # Automatic file monitoring service
    ├── health_checker.py       # System health validation
    └── service_health.py       # Health check system for monitoring

interfaces/
├── cli.py                 # Legacy CognitiveCLI (deprecated)
├── mcp_server.py         # Legacy MCP server (deprecated)
└── mcp_tools/            # Individual MCP tool implementations
```

## Development Commands

### Unified CLI Commands
```bash
# Memory operations
heimdall store "Experience text"           # Store experience with context
heimdall recall "query text"              # Retrieve memories with semantic search
heimdall load /path/to/file               # Load memories from files/directories
heimdall git-load /path/to/repo           # Load git commit patterns
heimdall status                           # System status and memory statistics

# Service management
heimdall qdrant start                     # Start Qdrant vector database
heimdall qdrant stop                      # Stop Qdrant service
heimdall qdrant status                    # Check Qdrant status
heimdall qdrant logs                      # View Qdrant logs

# Health and diagnostics
heimdall doctor                           # Full system health check
heimdall shell                            # Interactive memory shell

# File monitoring service
heimdall monitor start                    # Start automatic file monitoring
heimdall monitor stop                     # Stop file monitoring
heimdall monitor restart                  # Restart monitoring service
heimdall monitor status                   # Check monitoring service status
heimdall monitor health                   # Detailed monitoring health check

# Project management
heimdall project init                     # Initialize project memory collection
heimdall project list                     # List available projects
heimdall project clean                    # Clean up project containers
```

### Standalone MCP Server
```bash
# AI-agnostic MCP server
heimdall-mcp                              # Start MCP server (stdio mode)
python -m heimdall.mcp_server            # Alternative execution method
```

## MCP Integration

The system provides 4 MCP tools for Claude Code integration:

### Available MCP Tools
- **`store_memory`**: Store experiences and insights with multi-dimensional context
- **`recall_memories`**: Semantic search with categorized results (core/peripheral/bridge)
- **`session_lessons`**: Record key learnings for future sessions (metacognitive reflection)
- **`memory_status`**: System health and memory statistics

### Setup for Claude Code
```bash
# From any project directory
/path/to/heimdall-mcp-server/setup_claude_code_mcp.sh

# This creates project-specific memory isolation
# Each project gets its own Docker containers and memory space
```

## Git Integration Features

### Data Stored as Memories
- **Commit History**: Each git commit stored as a cognitive memory with full metadata
- **File Changes**: Detailed file modification information (additions, deletions, change types)
- **Development Context**: Commit messages, authors, timestamps, and affected files

### Loading Git History
```bash
# Load git commit history into memory
./scripts/load_project_content.sh --git-only

# Preview what would be loaded
./scripts/load_project_content.sh --dry-run
```

## Docker Architecture

### Project Isolation Strategy
Each project directory gets isolated Docker containers:
- Human-readable naming: `heimdall-{repo-name}-{project-hash}`
- Separate Qdrant containers: `qdrant-{repo-name}-{project-hash}`
- Unique ports: `6333 + hash % 1000`
- Isolated data volumes and networks
- Project-specific Qdrant collections

### Container Management
```bash
# Setup project memory (from project directory)
/path/to/heimdall-mcp-server/scripts/setup_project_memory.sh

# Cleanup project containers
/path/to/heimdall-mcp-server/scripts/setup_project_memory.sh --cleanup

# Rebuild containers
/path/to/heimdall-mcp-server/scripts/setup_project_memory.sh --rebuild
```

## Testing Strategy

### Test Categories
- **Unit Tests**: Individual component testing (`tests/unit/`)
- **Integration Tests**: Integration of components with minimized/no-mocks workflows (`tests/integration/`)
- **E2E Tests**: Complete system scenarios (`tests/e2e/`)

## Configuration Management

### Environment Variables

- See ./docker/Dockerfile, ./docker/docker-compose.template.yml, ./scripts/setup_project_memory.sh

### Configuration Files
- `.env` files for environment-specific settings
- `cognitive_memory/core/config.py` for system defaults

## Development Workflow

1. **Read Progress Documentation**: Always check `docs/progress/` before starting.
2. **READ and FOLLOW** `./docs/progress/README.md` on any development tasks
3. **Update Progress**: Document significant changes in appropriate progress file
4. **ALWAYS** commit at milestones. Never git add all files, manually list the files you worked on.

## Heimdall MCP Tools Usage

- Heimdall MCP Tool usage is **HIGHLY ENCOURAGED**
- This tool allows you to recall_memories: remember what past versions of you had significant effort to learn
- It also allows you to give session_lessons: important lessons that the future you can use

### Strategic MCP Tool Usage

- **`recall_memories`** - Call before any development task to get architecture, patterns, key files, data flows, context, decisions.
- **`store_memory`** - Store architectural decisions, file relationships, and project conventions.
- **`session_lessons`** - Record valuable insights, learnings, exploration results, large-effort tasks key findings and other valuable info from this session
- **`memory_status`** - Check system health and statistics

### Development Workflow with MCP

1. **Start with `recall_memories`** - Get relevant context before coding/debugging
2. **Use `store_memory` for discoveries** - Document patterns and relationships
3. **Ask about `session_lessons`** - If valuable insights emerged, suggest the user if you should store them
4. **Build project knowledge** - Each session should add understanding via stored memories
5. Before using `store_memory` and `session_lessons` summarize to the user what you learned and if he approves the memory

### When to Use Each Tool

- **`recall_memories`**: Before coding, when user mentions features/errors, exploring architecture
- **`store_memory`**: Architecture decisions, file relationships, project conventions, design patterns
- **`session_lessons`**: User signals value ("well done", that was tricky", "good approach"), breakthrough moments. Split big lessons into smaller contexts.

## Quality Standards

### Code Quality Requirements
- Must pass pre-commit git hook checks. No bypass.
