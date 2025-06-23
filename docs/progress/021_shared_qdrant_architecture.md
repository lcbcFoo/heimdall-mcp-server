# 021 - Shared Qdrant Architecture Migration

## Overview
Migration from per-project Docker containers to a single shared Qdrant instance with Python package distribution. This milestone eliminates container proliferation, simplifies installation, and reduces resource consumption while maintaining project isolation through collection namespacing.

## Status
- **Started**: 2025-06-23
- **Current Step**: Phase 3, Step 7 (Legacy Code Removal)
- **Completion**: 75% (6/8 steps completed)
- **Expected Completion**: 2025-07-21 (4 weeks)

## Objectives
- [ ] Implement shared Qdrant architecture with project-scoped collections
- [ ] Refactor file monitoring service to eliminate container dependencies
- [ ] Update git hooks to use host CLI instead of container exec
- [ ] Create project management CLI commands
- [ ] Package as standard Python distribution
- [ ] Remove legacy Docker complexity

## Implementation Progress

### Phase 1: Core Migration Infrastructure (Week 1-2)

#### Step 1: Configuration System
**Status**: Completed
**Date Range**: 2025-06-23 - 2025-06-23

**Tasks**:
- [x] Extended existing `cognitive_memory/core/config.py` with project ID generation function
- [x] Implemented `.heimdall/config.yaml` loading with environment variable fallbacks
- [x] Enhanced `detect_project_config()` to support new YAML format with legacy fallback
- [x] Added `project_id` field to `SystemConfig` dataclass with automatic population
- [x] Created comprehensive unit tests in `tests/unit/test_config.py`

**Implementation Details**:
- Added `get_project_id()` function generating deterministic IDs in format `{repo_name}_{hash8}`
- Enhanced `detect_project_config()` to load `.heimdall/config.yaml` with mapping to environment variables
- Maintained full backward compatibility with existing Docker Compose detection
- Project ID automatically populated in `SystemConfig.from_env()` for immediate use

#### Step 2: Project-Scoped Collections
**Status**: Completed
**Date Range**: 2025-06-23 - 2025-06-23

**Tasks**:
- [x] Update QdrantCollectionManager for namespaced collections (`{project_id}_concepts`)
- [x] Implement collection naming strategy for hierarchical memory (L0/L1/L2)
- [x] Add project detection from current working directory (uses existing `get_project_id()` from config.py)
- [x] Create collection management utilities

**Implementation Details**:
- Modified `QdrantCollectionManager.__init__()` to accept `project_id` parameter and generate project-scoped collection names
- Updated collection naming from hardcoded `cognitive_*` to `{project_id}_concepts/contexts/episodes` format
- Enhanced `HierarchicalMemoryStorage` constructor to pass project_id to collection manager
- Updated `create_hierarchical_storage()` factory function to accept project_id parameter
- Modified `cognitive_memory/factory.py` to pass `config.project_id` to storage layer
- Added collection management utilities:
  - `list_project_collections()` - List collections for specific project
  - `get_all_projects()` - Discover project IDs from existing collections
  - `delete_project_collections()` - Clean up project collections
- Updated integration tests (`test_storage_pipeline.py`, `test_end_to_end_system.py`) with project-scoped MockQdrantClient
- Created comprehensive unit tests in `tests/unit/test_project_scoped_collections.py` with 7 test scenarios
- All tests passing, ensuring project isolation and proper collection naming

#### Step 3: Service Manager Updates
**Status**: Completed
**Date Range**: 2025-06-23 - 2025-06-23

**Tasks**:
- [x] Modify `memory_system/service_manager.py` for single shared Qdrant
- [x] Create simplified docker-compose.yml for shared instance
- [x] Remove per-project Docker container logic
- [x] Add shared Qdrant health checks

**Implementation Details**:
- Updated `QdrantManager` to use fixed container name `heimdall-shared-qdrant` instead of project-specific names
- Simplified `docker-compose.template.yml` from 109 to 35 lines, removing variable substitution complexity
- Implemented `_start_docker_shared()` method using docker-compose for service management
- Added `_cleanup_legacy_containers()` to automatically remove old project-specific containers
- Standardized on fixed port 6333 for shared instance instead of dynamic project-based ports
- Updated status checking and health monitoring to work with shared architecture
- Maintained full CLI compatibility - all `memory_system qdrant` commands work unchanged

### Phase 2: Feature Migration (Week 2-3)

#### Step 4: Host-based File Monitoring Migration
**Status**: Completed
**Date Range**: 2025-06-23 - 2025-06-23

**Design Decision**: Instead of creating parallel `host_monitoring.py`, refactor existing `monitoring_service.py` to eliminate container dependencies while maintaining CLI compatibility.

**Tasks**:
- [x] Refactor `memory_system/monitoring_service.py` to remove Docker container dependencies
- [x] Replace container environment variables with `.heimdall/config.yaml` configuration loading
- [x] Implement project-local PID files (`.heimdall/monitor.pid`) instead of container-based process management
- [x] Add multi-project PID collision prevention in existing service
- [x] Keep existing CLI interface (`memory_system monitor`) with minimal changes, just improving commands to be clear about the monitoring service
- [x] Remove `memory_system/host_monitoring.py` (created prematurely, causes code duplication)

**Implementation Details**:
- Refactored `MonitoringService.__init__()` to accept `project_root` parameter and use centralized configuration
- Updated configuration to use `get_project_paths()` and `get_monitoring_config()` from `cognitive_memory/core/config.py`
- Replaced hardcoded `/tmp/monitoring.pid` with project-local `.heimdall/monitor.pid` files
- Added automatic stale PID cleanup using `ProjectPaths.cleanup_stale_pid()` method
- Updated all PID file operations to use project-specific paths preventing multi-project collisions
- Modified CLI interface to accept optional `--project-root` parameter while maintaining backward compatibility
- Updated module docstring and class descriptions to reflect host-based (not container-based) architecture
- Integrated with centralized monitoring configuration priority logic (env vars > config file > defaults)
- Maintained all existing CLI commands (`memory_system monitor start/stop/restart/status/health`) with identical behavior

**Rationale**:
- Maintains backward compatibility and familiar CLI interface
- Eliminates code duplication between two monitoring services
- Provides seamless upgrade path for existing users
- Follows single responsibility principle with one monitoring service
- Enables true multi-project isolation without container overhead

#### Step 5: Git Hook Migration
**Status**: Completed
**Date Range**: 2025-06-23 - 2025-06-23

**Design Decision**: Implemented Python-based hooks instead of bash templates for superior cross-platform compatibility and direct integration with cognitive memory system.

**Tasks**:
- [x] Replace `scripts/post-commit-hook.sh` with `scripts/post_commit_hook.py` (Python-based)
- [x] Replace `scripts/git-hook-installer.sh` with `scripts/git_hook_installer.py` (Python-based)
- [x] Remove all Docker container dependencies from hook logic
- [x] Integrate with centralized configuration system from `cognitive_memory/core/config.py`
- [x] Implement cross-platform compatibility (Windows, macOS, Linux)
- [x] Maintain existing hook chaining and safety features
- [x] Test hook installation/uninstallation safety across platforms
- [x] Test hook chaining with existing hooks (backup/restore functionality verified)

**Implementation Details**:
- Created `scripts/post_commit_hook.py` with GitPython for git operations and direct function calls to `CognitiveCLI`
- Implemented `scripts/git_hook_installer.py` with comprehensive installation/uninstallation logic using pathlib
- Added silent operation mode with loguru suppression for clean git output
- Integrated with project-local logging via `get_project_paths()` from centralized config
- Used typer/rich for enhanced CLI experience with fallback to basic interface
- Maintained all existing safety features: backup/restore, chaining, status checking
- Eliminated subprocess overhead by calling `cli.load_git_patterns()` directly with `max_commits=1`
- Added concise output showing only commit hash and memory count: "Processed commit abc123: 1 memory loaded"
- Implemented comprehensive chaining with existing hooks: backup creation, restoration, and safe execution ordering
- Added colored output with ANSI codes for enhanced user experience (GREEN for success, BLUE for info, RED for errors)

**Benefits Achieved**:
- **Cross-platform**: Works on Windows, macOS, Linux without bash dependencies
- **Direct Integration**: Function calls instead of subprocess overhead (eliminates Docker exec)
- **Clean Output**: Suppressed verbose logging, shows only essential information
- **Better Error Handling**: Python exception handling with graceful degradation
- **Maintainability**: Single language codebase consistent with project patterns

#### Step 6: Project Management CLI
**Status**: Completed
**Date Range**: 2025-06-23 - 2025-06-23

**Tasks**:
- [x] Add `memory_system project init` command (also detects qdrant status and starts qdrant if needed)
- [x] Add `memory_system project list` command
- [x] Add `memory_system project clean <name>` command
- [x] Update existing CLI commands for project-scoped operations
- [x] Add project auto-detection from working directory

**Implementation Details**:
- Added comprehensive `project` subcommand group to `memory_system/cli.py` with three main commands
- **`memory_system project init`**: Initializes project-specific collections and setup
  - Auto-detects current working directory as project root if not specified
  - Automatically starts Qdrant if not running (configurable with `--no-auto-start-qdrant`)
  - Creates project-scoped Qdrant collections (`{project_id}_concepts/contexts/episodes`)
  - Generates `.heimdall/config.yaml` configuration file if it doesn't exist
  - Shows comprehensive project information table with project ID, collections, and paths
  - Supports JSON output for programmatic usage
- **`memory_system project list`**: Lists all projects in shared Qdrant instance
  - Discovers projects by parsing collection names in shared Qdrant
  - Shows collection details with `--collections` flag (vector counts, point counts)
  - Supports JSON output for integration with other tools
  - Handles empty Qdrant instances gracefully
- **`memory_system project clean`**: Removes project collections from shared Qdrant
  - Takes project ID as argument (use `list` command to see available projects)
  - Safety features: confirmation prompt (bypass with `--yes`), dry-run mode
  - Comprehensive error handling and progress reporting
  - Shows detailed results of deletion operations
- Enhanced existing CLI commands (`load`, `load-git incremental`, `shell`) with project context display
- Project auto-detection integrated throughout using centralized `get_project_id()` function
- All commands automatically detect and display current project context for user awareness
- Proper error handling and rich console output with progress indicators
- Complete CLI help system with detailed descriptions and examples

**User Workflow Integration**:
```bash
# Initialize project (auto-starts Qdrant if needed)
memory_system project init

# Load content into project-specific collections
memory_system load docs/

# List all projects to see what's available
memory_system project list --collections

# Clean up a specific project
memory_system project clean my_project_abc123 --dry-run
memory_system project clean my_project_abc123 --yes
```

**Benefits Achieved**:
- **Seamless Project Management**: Users can easily initialize, list, and clean up projects
- **Auto-Service Management**: Qdrant automatically started when needed, reducing friction
- **Project Isolation**: Each project gets its own collections while sharing Qdrant instance
- **User Awareness**: All commands show project context for clarity
- **Safety Features**: Confirmation prompts and dry-run modes prevent accidental data loss
- **Integration Ready**: JSON output supports automation and scripting workflows

### Phase 3: Package Distribution (Week 3-4)

#### Step 7: Legacy Code Removal
**Status**: Not Started
**Date Range**: 2025-07-14 - 2025-07-21

**Tasks**:
- [ ] Remove `scripts/setup_project_memory.sh` (370 lines)
- [ ] Delete `docker/docker-compose.template.yml`
- [ ] Clean up per-project Docker logic throughout codebase
- [ ] Remove container-specific environment variable handling

#### Step 8: Python Package Setup
**Status**: Not Started
**Date Range**: 2025-07-16 - 2025-07-21

**Tasks**:
- [ ] Configure standard PyPI packaging (setup.py/pyproject.toml)
- [ ] Update installation documentation
- [ ] Test pip install workflow
- [ ] Create release automation

## Technical Notes

### Architecture Changes
**Before**: Each project gets `heimdall-{repo}-{hash}` + `qdrant-{repo}-{hash}` containers
**After**: Single shared Qdrant with collections: `{project_id}_concepts`, `{project_id}_contexts`, `{project_id}_episodes`

### Key Components
- **Project Identification**: `{repo_name}_{hash8}` from absolute path
- **Collection Naming**: `{project_id}_{memory_level}` for hierarchical isolation
- **Configuration**: `.heimdall/config.yaml` per project with shared global defaults
- **Process Management**: Refactored monitoring service with project-local PID files

### User Workflow
```bash
# Per project
pip install heimdall-mcp

# Automatically detects if qdrant is running - if not starts qdrant docker
memory_system project init
cognitive-cli load .
```

## Dependencies
- **External**: Docker for shared Qdrant only, Python packaging tools
- **Internal**: All existing cognitive memory modules require collection scoping updates
- **Blocking**: None (fresh implementation approach)

## Risks & Mitigation

### Risks
- **Data Migration**: Existing projects lose memory data
- **Configuration Complexity**: Multiple config sources (env vars + files)
- **Service Refactoring**: Breaking changes to monitoring service internal architecture

### Mitigation
- **Fresh Start Approach**: No backward compatibility required, clean slate
- **Configuration Hierarchy**: Clear precedence order (CLI > env > config file > defaults)
- **Backward Compatible Refactoring**: Maintain existing CLI interface while updating internal implementation
- **Robust PID Management**: Proper cleanup, collision detection, health checks

## Resources
- **Architecture Document**: `docs/shared-qdrant-architecture.md`
- **Current Container Logic**: `memory_system/service_manager.py`, `scripts/setup_project_memory.sh`
- **Monitoring Service**: `memory_system/monitoring_service.py`
- **Collection Management**: `cognitive_memory/storage/qdrant_storage.py`

## Change Log
- **2025-06-23**: Initial milestone creation and task breakdown
- **2025-06-23**: Completed Phase 1, Step 2 (Project-Scoped Collections) - Implemented project-isolated collection naming with comprehensive testing
- **2025-06-23**: Completed Phase 1, Step 3 (Service Manager Updates) - Implemented shared Qdrant architecture with legacy container cleanup
- **2025-06-23**: Updated Step 4 approach - Refactor existing monitoring service instead of creating parallel implementation to avoid code duplication and maintain CLI compatibility
