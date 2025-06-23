# Unified CLI Architecture: Heimdall Command Consolidation

## Overview

This document outlines the architectural plan to consolidate the cognitive memory system's command-line interfaces into a single, unified `heimdall` command. The current system has redundant CLI implementations that need to be streamlined for better maintainability and user experience.

## Current Architecture Problems

### Redundant CLI Implementations

**Current State:**
```
memory_system/cli.py (Service Management + Some Cognitive Operations)
├── qdrant start/stop/status
├── serve mcp
├── shell (interactive)
├── load (delegates to CognitiveCLI)
└── monitor start/stop/status

interfaces/cli.py (CognitiveCLI - Full Cognitive Operations)
├── store_experience()
├── retrieve_memories()
├── load_memories()
├── consolidate_memories()
├── git operations
└── All command parsing/formatting

memory_system/interactive_shell.py (Interactive Mode)
├── Delegates to CognitiveCLI
├── Rich formatting and completion
└── Session management
```

### Key Issues

1. **Duplicate Command Parsing**: Both `memory_system/cli.py` and `interfaces/cli.py` implement command parsing
2. **Complex Delegation Chain**: Interactive shell → CognitiveCLI → Cognitive operations
3. **Split Responsibilities**: Some cognitive operations in memory_system CLI, most in interfaces CLI
4. **Import Dependencies**: Interactive shell imports from interfaces, creates coupling
5. **Multiple Entry Points**: Users need to know `memory_system` vs `cognitive-cli` commands

## Target Architecture

### Operations-First Design

**Target State:**
```
heimdall/
├── cli.py                 # Single unified CLI entry point
├── operations.py          # Pure cognitive operations (data layer)
├── interactive_shell.py   # Rich interactive interface
├── service_manager.py     # Infrastructure management
└── monitoring_service.py  # File monitoring service
```

**Clean Interface Separation:**
```
                    ┌─────────────────┐
                    │ CognitiveSystem │
                    └─────────────────┘
                             │
                    ┌─────────────────┐
                    │   Operations    │  ← Pure business logic
                    │    (Data)       │     Single source of truth
                    └─────────────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
    ┌───────────┐   ┌────────────┐   ┌──────────────┐
    │ CLI       │   │ MCP Server │   │   Future     │
    │(Terminal) │   │ (JSON/LLM) │   │ Interfaces   │
    └───────────┘   └────────────┘   └──────────────┘
            │
    ┌───────────┐
    │Interactive│
    │   Shell   │
    └───────────┘
```

### Command Interface Design

**Dual Entry Point Design:**
```bash
heimdall                    # Main command
├── qdrant start/stop/status        # Infrastructure management
├── monitor start/stop/status       # File monitoring
├── project init/list/clean         # Project management
├── store "experience"              # Cognitive operations
├── recall "query"                # Memory search (name recall or retrieve in current implementation)
├── load docs/ --recursive          # Content loading
├── git-load /repo --dry-run        # Git pattern loading
├── status --detailed               # System status
└── shell                           # Interactive mode

heimdall-mcp                # Dedicated MCP server (stdio)
├── Standard MCP protocol via stdio
├── AI-agnostic (works with Claude, Cline, Continue, etc.)
└── Standalone executable for MCP clients
```

### Separation of Concerns

**Operations Layer (heimdall/operations.py) - Single Source of Truth:**
- Pure cognitive functions (no interface dependencies)
- Returns structured data dictionaries
- Business logic and data processing
- Consumed by ALL interfaces (CLI, MCP, HTTP, Interactive)

**Interface Layers (Format-Specific):**

**CLI Layer (heimdall/cli.py):**
- Command parsing and validation
- Terminal-formatted output and user feedback
- Typer-based command routing
- Calls operations.py for data, formats for humans

**MCP Server (heimdall/mcp_server.py):**
- Standalone executable for AI-agnostic MCP protocol
- JSON formatting optimized for LLM consumption
- MCP protocol compliance via stdio
- Tool schemas and validation
- Calls operations.py for data, formats for AI models
- Works with Claude Code, Cline, Continue, and other MCP clients

**Interactive Shell (heimdall/interactive_shell.py):**
- Rich formatting with colors and panels
- Command completion and session state
- Enhanced user experience features
- Calls operations.py for data, formats with rich UI

**Future Interfaces (examples only, not currently planned):**
- REST API endpoints with JSON responses
- gRPC services with protobuf messages
- WebSocket connections for real-time updates
- All would call operations.py for data, format for specific consumers

## Implementation Plan

### Phase 1: Extract Pure Operations

**Goal**: Create clean operations layer as single source of truth

**Steps:**
1. Create `heimdall/operations.py` with `CognitiveOperations` class
2. Extract cognitive methods from `interfaces/cli.py` CognitiveCLI class
3. Remove ALL formatting/printing - return structured data only
4. Design data-first interfaces for all consumers

**Operations Interface Design:**
```python
class CognitiveOperations:
    def store_experience(self, text: str, context: dict = None) -> dict:
        """Returns: {"memory_id": "...", "hierarchy_level": 1, "memory_type": "episodic", "success": True}"""

    def retrieve_memories(self, query: str, types: list = None, limit: int = 10) -> dict:
        """Returns: {"core": [...], "peripheral": [...], "bridge": [...], "total_count": 42}"""

    def get_system_status(self, detailed: bool = False) -> dict:
        """Returns: {"memory_counts": {...}, "system_config": {...}, "storage_stats": {...}}"""

    def consolidate_memories(self, dry_run: bool = False) -> dict:
        """Returns: {"total_episodic": 100, "consolidated": 15, "failed": 2, "skipped": 83}"""

    def load_memories(self, source_path: str, **kwargs) -> dict:
        """Returns: {"success": True, "memories_loaded": 50, "processing_time": 2.1, ...}"""

    def load_git_patterns(self, repo_path: str, **kwargs) -> dict:
        """Returns: {"success": True, "patterns_loaded": 25, "commits_processed": 100, ...}"""
```

**There is NO NEED to Keep CognitiveCLI temporarily for MCP server compatibility during transition**

The entire implementation will be done in a single release.

### Phase 2: Enhance Unified CLI

**Goal**: Add cognitive commands using operations layer

**Steps:**
1. Add cognitive command groups to `heimdall/cli.py`
2. Import and call `operations.py` methods for data
3. Format structured data for terminal output
4. Commands to add with terminal-specific formatting:

```python
@app.command("store")
def store_cmd(text: str, context_json: str = None):
    ops = CognitiveOperations(cognitive_system)
    result = ops.store_experience(text, parse_context(context_json))

    if result["success"]:
        console.print(f"✓ Stored: L{result['hierarchy_level']}, {result['memory_type']}")
    else:
        console.print("✗ Failed to store experience", style="red")

@app.command("recall")
def recall_cmd(query: str, types: list[str] = None, limit: int = 10):
    ops = CognitiveOperations(cognitive_system)
    results = ops.retrieve_memories(query, types, limit)

    # Terminal-specific formatting with colors and structure
    for memory_type, memories in results.items():
        if memories:
            console.print(f"[bold]{memory_type.upper()}[/bold] ({len(memories)})")
            for memory in memories:
                console.print(f"  {memory.content[:100]}...")
```

### Phase 2.5: Create Standalone MCP Server

**Goal**: Create dedicated `heimdall-mcp` executable using operations layer

**Steps:**
1. Create `heimdall/mcp_server.py` as standalone MCP server
2. Import operations layer: `from heimdall.operations import CognitiveOperations`
3. Implement `main()` function for standalone execution
4. Update all tool methods to use operations and format for LLM consumption:

```python
# heimdall/mcp_server.py
async def _store_memory(self, arguments: dict):
    result = self.operations.store_experience(text, context)
    if result["success"]:
        return [TextContent(type="text", text=f"✓ Stored: L{result['hierarchy_level']}, {result['memory_type']}")]

async def _recall_memories(self, arguments: dict):
    results = self.operations.retrieve_memories(query, types_filter, max_results)
    formatted_json = self._format_memory_results_for_llm(results)
    return [TextContent(type="text", text=formatted_json)]

def main():
    # Standalone MCP server entry point
    import asyncio
    asyncio.run(serve_mcp())
```

5. Test MCP functionality thoroughly with new operations layer
6. Verify AI-agnostic compatibility (Claude Code, Cline, Continue)

### Phase 3: Update Interactive Shell

**Goal**: Migrate interactive shell to operations layer

**Steps:**
1. Update `heimdall/interactive_shell.py` imports
2. Replace CognitiveCLI delegation with direct operations calls
3. Implement rich formatting for structured data
4. Update command completion and help systems

```python
def _retrieve_memories(self, query: str, full_output: bool = False):
    ops = CognitiveOperations(self.cognitive_system)
    results = ops.retrieve_memories(query)

    # Rich interactive formatting with panels and colors
    for memory_type, memories in results.items():
        if memories:
            content = self._format_memories_rich(memories, full_output)
            panel = Panel(content, title=f"🎯 {memory_type.upper()} ({len(memories)})")
            self.console.print(panel)
```

### Phase 4: Create Dedicated MCP Server and Restructure

**Goal**: Complete transition to `heimdall` command and create standalone MCP server

**Steps:**
1. Create `heimdall/mcp_server.py` as standalone MCP server entry point
2. Rename `memory_system/` directory to `heimdall/`
3. Update `pyproject.toml` console script entries:
   ```toml
   [project.scripts]
   heimdall = "heimdall.cli:main"
   heimdall-mcp = "heimdall.mcp_server:main"
   ```
4. Update all import statements throughout codebase
5. Update documentation and help text references
6. Remove MCP wrapper script (`scripts/claude_mcp_wrapper.sh`)

### Phase 5: Remove Redundant Code

**Goal**: Clean up obsolete files after all consumers migrated

**Steps:**
1. **Only after MCP server and interactive shell are migrated** - delete `interfaces/cli.py`
2. **After standalone MCP server created** - delete `interfaces/mcp_server.py`
3. Remove `interfaces/` directory if empty
4. Remove MCP wrapper script (`scripts/claude_mcp_wrapper.sh`)
5. Update remaining imports that reference old paths
6. Clean up unused dependencies and dead code

### Phase 6: Validation and Testing

**Goal**: Ensure feature parity and reliability

**Steps:**
1. Test all existing functionality via `heimdall` command
2. Verify interactive shell operations
3. Validate service management commands
4. Test cognitive operations (store, retrieve, load, etc.)
5. Update integration tests and documentation

## Future Extension Benefits

### Example: How New Interfaces Could Be Added

The operations-first design makes adding future interfaces straightforward (not currently planned, just examples):

**Hypothetical HTTP REST API:**
```python
# Future example: heimdall/http_server.py (NOT PLANNED FOR CURRENT IMPLEMENTATION)
@app.post("/api/memories")
async def store_memory(request: StoreRequest):
    ops = CognitiveOperations(cognitive_system)
    result = ops.store_experience(request.text, request.context)
    return JSONResponse({
        "memory_id": result["memory_id"],
        "success": result["success"],
        "hierarchy_level": result["hierarchy_level"],
        "timestamp": datetime.now().isoformat()
    })

@app.get("/api/memories/search")
async def search_memories(query: str, types: list[str] = None):
    ops = CognitiveOperations(cognitive_system)
    results = ops.retrieve_memories(query, types)
    return JSONResponse({
        "query": query,
        "results": results,
        "total_count": results.get("total_count", 0)
    })
```

**Hypothetical gRPC Service:**
```python
# Future example: heimdall/grpc_server.py (NOT PLANNED FOR CURRENT IMPLEMENTATION)
class CognitiveMemoryService(cognitive_memory_pb2_grpc.CognitiveMemoryServicer):
    def StoreMemory(self, request, context):
        ops = CognitiveOperations(self.cognitive_system)
        result = ops.store_experience(request.text, dict(request.context))

        return cognitive_memory_pb2.StoreResponse(
            memory_id=result["memory_id"],
            success=result["success"]
        )
```

### Clean Architecture Principles

- **Single Source of Truth**: Operations layer contains all business logic
- **Interface Independence**: Each interface formats data appropriately
- **Dependency Inversion**: Interfaces depend on operations, not vice versa
- **Open/Closed Principle**: Easy to add new interfaces without changing operations
- **DRY Principle**: No duplicate cognitive logic across interfaces

## Success Criteria

1. **Dual Command Structure**: All functionality via `heimdall` command, MCP via `heimdall-mcp`
2. **No Duplication**: No redundant CLI implementations
3. **Clean Separation**: Operations layer independent of CLI concerns
4. **AI-Agnostic MCP**: Standalone MCP server works with any MCP client
5. **Maintainability**: Easy to add new interfaces (HTTP, gRPC, etc.)
6. **User Experience**: Consistent command structure and help system
7. **Feature Parity**: All existing functionality preserved

## Risks and Mitigations

**Risk**: Import dependency issues during restructure
**Mitigation**: Update imports systematically, use IDE refactoring tools

**Risk**: Loss of functionality during consolidation
**Mitigation**: Comprehensive testing at each phase, feature parity validation

## Timeline Estimate

- **Phase 1-2**: 1-2 days (Extract operations, enhance CLI)
- **Phase 3-4**: 1 day (Update shell, rename structure)
- **Phase 5-6**: 1 day (Cleanup, testing, validation)

**Total**: 3-4 days for complete transition to unified `heimdall` architecture.
