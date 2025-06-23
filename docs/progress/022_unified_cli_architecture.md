# 022 - Unified CLI Architecture: Heimdall Command Consolidation

## Overview
Consolidate the cognitive memory system's fragmented command-line interfaces into a single, unified `heimdall` command. This milestone addresses architectural issues with redundant CLI implementations by creating a clean operations-first design with separate interface layers for CLI, MCP, and interactive shell.

## Status
- **Started**: 2025-06-23
- **Current Step**: Phase 1 Complete - Operations Layer
- **Completion**: 14% (1/7 phases complete)
- **Expected Completion**: 2025-06-27

## Objectives
- [x] Create unified operations layer as single source of truth
- [ ] Consolidate CLI commands under single `heimdall` entry point
- [ ] Create standalone `heimdall-mcp` server for AI-agnostic MCP protocol
- [ ] Migrate interactive shell to use operations layer
- [ ] Remove redundant code and clean up architecture
- [ ] Maintain feature parity throughout transition
- [x] Achieve clean separation of concerns between data and interface layers

## Implementation Progress

### Step 1: Extract Pure Operations Layer
**Status**: ✅ COMPLETED
**Date Range**: 2025-06-23 - 2025-06-23

#### Tasks Completed
- ✅ Created `heimdall/operations.py` with `CognitiveOperations` class
- ✅ Extracted cognitive methods from `interfaces/cli.py` CognitiveCLI class
- ✅ Removed ALL formatting/printing - return structured data only
- ✅ Designed data-first interfaces: store_experience(), retrieve_memories(), get_system_status()
- ✅ Designed data-first interfaces: consolidate_memories(), load_memories(), load_git_patterns()
- ✅ Created comprehensive unit tests with 36 test cases covering all operations
- ✅ Implemented clean architecture with single source of truth for cognitive operations

#### Key Accomplishments
- **Pure Operations Layer**: Created `heimdall/operations.py` with no interface dependencies
- **Data-First Design**: All methods return structured dictionaries for flexible formatting
- **Complete Test Coverage**: 36 unit tests covering all operations including edge cases
- **Clean Architecture**: Single source of truth for cognitive business logic
- **Interface Independence**: Operations layer can be consumed by any interface (CLI, MCP, HTTP)

#### Architecture Details
```python
class CognitiveOperations:
    def store_experience(text, context) -> Dict[str, Any]        # Experience storage
    def retrieve_memories(query, types, limit) -> Dict[str, Any] # Memory retrieval
    def get_system_status(detailed) -> Dict[str, Any]           # System status
    def consolidate_memories(dry_run) -> Dict[str, Any]         # Memory consolidation
    def load_memories(source_path, **kwargs) -> Dict[str, Any]  # Content loading
    def load_git_patterns(repo_path, **kwargs) -> Dict[str, Any] # Git pattern loading
```

#### Current Work
- Phase 1 complete - ready for Phase 2

### Step 2: Enhance Unified CLI
**Status**: Ready to Start
**Date Range**: 2025-06-23 - 2025-06-24

#### Tasks Completed
- None yet

#### Current Work
- Ready to begin with operations layer complete

#### Next Tasks
- Add cognitive command groups to `heimdall/cli.py`
- Import and call `operations.py` methods for data
- Implement terminal-specific formatting for structured data
- Add commands: store, recall, load, git-load, status with proper console output
- Test unified CLI functionality

### Step 3: Create Standalone MCP Server
**Status**: Not Started
**Date Range**: 2025-06-25 - 2025-06-25

#### Tasks Completed
- None yet

#### Current Work
- Waiting for Step 1-2 completion

#### Next Tasks
- Create `heimdall/mcp_server.py` as standalone MCP server
- Import operations layer and implement tool methods
- Add `main()` function for standalone execution
- Format data for LLM consumption (JSON optimized)
- Test MCP functionality with operations layer
- Verify AI-agnostic compatibility (Claude Code, Cline, Continue)

### Step 4: Update Interactive Shell
**Status**: Not Started
**Date Range**: 2025-06-25 - 2025-06-26

#### Tasks Completed
- None yet

#### Current Work
- Waiting for Step 1-3 completion

#### Next Tasks
- Update `heimdall/interactive_shell.py` imports
- Replace CognitiveCLI delegation with direct operations calls
- Implement rich formatting for structured data with panels and colors
- Update command completion and help systems
- Test interactive shell with new operations layer

### Step 5: Restructure and Create Final Entry Points
**Status**: Not Started
**Date Range**: 2025-06-26 - 2025-06-26

#### Tasks Completed
- None yet

#### Current Work
- Waiting for Step 1-4 completion

#### Next Tasks
- Rename `memory_system/` directory to `heimdall/`
- Update `pyproject.toml` console script entries for `heimdall` and `heimdall-mcp`
- Update all import statements throughout codebase
- Update documentation and help text references
- Remove MCP wrapper script (`scripts/claude_mcp_wrapper.sh`)

### Step 6: Remove Redundant Code
**Status**: Not Started
**Date Range**: 2025-06-26 - 2025-06-27

#### Tasks Completed
- None yet

#### Current Work
- Waiting for Step 1-5 completion

#### Next Tasks
- Delete `interfaces/cli.py` after all consumers migrated
- Delete `interfaces/mcp_server.py` after standalone MCP server created
- Remove `interfaces/` directory if empty
- Clean up unused dependencies and dead code
- Update remaining imports that reference old paths

### Step 7: Validation and Testing
**Status**: Not Started
**Date Range**: 2025-06-27 - 2025-06-27

#### Tasks Completed
- None yet

#### Current Work
- Waiting for Step 1-6 completion

#### Next Tasks
- Test all existing functionality via `heimdall` command
- Verify interactive shell operations
- Validate service management commands (qdrant, monitor, project)
- Test cognitive operations (store, recall, load, git-load)
- Update integration tests and documentation
- Verify feature parity with original implementation

## Technical Notes

### Key Architecture Changes
- **Operations-First Design**: Single `CognitiveOperations` class containing all business logic
- **Clean Interface Separation**: CLI, MCP, and Interactive interfaces consume operations layer
- **Dual Entry Points**: `heimdall` for terminal use, `heimdall-mcp` for AI clients
- **Data-First APIs**: All operations return structured dictionaries, interfaces format appropriately

### Operations Layer Interface Design
```python
class CognitiveOperations:
    def store_experience(self, text: str, context: dict = None) -> dict
    def retrieve_memories(self, query: str, types: list = None, limit: int = 10) -> dict
    def get_system_status(self, detailed: bool = False) -> dict
    def consolidate_memories(self, dry_run: bool = False) -> dict
    def load_memories(self, source_path: str, **kwargs) -> dict
    def load_git_patterns(self, repo_path: str, **kwargs) -> dict
```

### Directory Structure Changes
```
Current: memory_system/ + interfaces/
Target:  heimdall/ (unified)
         ├── cli.py (terminal interface)
         ├── operations.py (business logic)
         ├── mcp_server.py (AI interface)
         ├── interactive_shell.py (rich UI)
         ├── service_manager.py (infrastructure)
         └── monitoring_service.py (file monitoring)
```

## Dependencies
- **Internal**: All core cognitive_memory modules (encoding, storage, retrieval)
- **External**: typer (CLI), rich (formatting), mcp (protocol)
- **Blocking**: None - can proceed immediately
- **Blocked by**: None

## Risks & Mitigation

### Risk: Import dependency issues during restructure
**Mitigation**: Update imports systematically using IDE refactoring tools, test after each phase

### Risk: Loss of functionality during consolidation
**Mitigation**: Comprehensive testing at each phase, maintain feature parity validation checklist

### Risk: MCP compatibility issues with new operations layer
**Mitigation**: Test MCP server thoroughly with Claude Code, Cline, and Continue clients

### Risk: Interactive shell regression
**Mitigation**: Preserve rich formatting capabilities, test all interactive commands

## Resources
- [Unified CLI Architecture Document](../arch-docs/unified-cli-architecture.md)
- Current implementations: `memory_system/cli.py`, `interfaces/cli.py`, `interfaces/mcp_server.py`
- Target interfaces: Terminal CLI, MCP Protocol, Interactive Shell
- Operations layer pattern: Clean Architecture, Dependency Inversion

## Summary

### Phase 1 Achievements
✅ **Operations Layer Complete** - Successfully extracted pure business logic from existing CLI implementations into a single, clean operations layer. This provides:

- **Single Source of Truth**: All cognitive operations centralized in `heimdall/operations.py`
- **Interface Independence**: No formatting or printing dependencies - returns structured data
- **Comprehensive Coverage**: All existing CLI functionality preserved and enhanced
- **Clean Architecture**: Data-first design enabling multiple interface types
- **Robust Testing**: 36 unit tests covering all operations and edge cases

### Files Created
- `heimdall/operations.py` - Pure operations layer with `CognitiveOperations` class
- `heimdall/__init__.py` - Package initialization
- `tests/unit/heimdall/test_operations.py` - Comprehensive unit test suite

### Architecture Benefits
The operations layer enables clean separation between business logic and interface formatting, making it easy to add new interfaces (CLI, MCP, HTTP, gRPC) that consume the same operations but format data appropriately for their consumers.

### Next Steps
Ready to proceed to Phase 2: Enhance Unified CLI to consume the operations layer and provide terminal-specific formatting.

## Change Log
- **2025-06-23**: Initial progress plan created based on architecture document
- **2025-06-23**: Phase 1 completed - Pure operations layer with comprehensive testing
