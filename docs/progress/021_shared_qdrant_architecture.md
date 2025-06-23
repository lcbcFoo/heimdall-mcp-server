# 021 - Shared Qdrant Architecture Migration

## Overview
Migration from per-project Docker containers to a single shared Qdrant instance with Python package distribution. This milestone eliminates container proliferation, simplifies installation, and reduces resource consumption while maintaining project isolation through collection namespacing.

## Status
- **Started**: 2025-06-23
- **Current Step**: Phase 3, Step 8 (Python Package Setup) - Final Polish
- **Completion**: 95% (8/8 steps completed, testing phase)
- **Expected Completion**: 2025-06-23 (same day completion)

## Objectives
- [x] Implement shared Qdrant architecture with project-scoped collections
- [x] Refactor file monitoring service to eliminate container dependencies
- [x] Update git hooks to use host CLI instead of container exec
- [x] Create project management CLI commands
- [x] Package as standard Python distribution
- [x] Remove legacy Docker complexity

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
**Status**: Completed
**Date Range**: 2025-06-23 - 2025-06-23

**Tasks**:
- [x] Remove `scripts/setup_project_memory.sh` (370 lines) - legacy Docker setup script
- [x] Keep `docker/docker-compose.template.yml` (already updated for shared architecture)
- [x] Clean up per-project Docker logic throughout codebase
- [x] Remove container-specific environment variable handling
- [x] Remove 9 obsolete shell scripts replaced by CLI commands
- [x] Update remaining scripts for shared architecture

**Implementation Details**:
- Removed legacy 370-line Docker setup script that created per-project containers
- Eliminated 9 obsolete shell scripts that duplicated CLI functionality:
  - `scripts/stop_memory.sh`, `scripts/start_memory.sh` → replaced by `memory_system qdrant` commands
  - `scripts/load_project_content.sh` → replaced by `memory_system load`
  - `scripts/list_memory_projects.sh` → replaced by `memory_system project list`
  - `scripts/cleanup_memory.sh` → replaced by `memory_system project clean`
  - `scripts/monitor_memory_usage.sh`, `scripts/analyze_container_size.sh` → per-project monitoring obsolete
  - `scripts/git-hook-installer.sh`, `scripts/post-commit-hook.sh` → replaced by Python versions
- Updated `setup_claude_code_mcp.sh` to use `memory_system project init` instead of legacy container setup
- Updated `scripts/claude_mcp_wrapper.sh` to use host-based `memory_system serve mcp` instead of container exec
- Updated all script references throughout codebase to point to new CLI commands
- Kept appropriate container detection logic in config.py for environment detection
- Reduced total shell scripts from 16+ to 5 essential ones (75% reduction)

**Benefits Achieved**:
- **Simplified Installation**: No more complex 370-line bash setup scripts
- **Unified CLI**: All functionality accessible through `memory_system` command
- **Reduced Maintenance**: Eliminated script duplication and per-project container logic
- **Cleaner Codebase**: 75% reduction in shell scripts, focusing on Python-based solutions

#### Step 8: Python Package Setup
**Status**: Completed (Testing Phase)
**Date Range**: 2025-06-23 - 2025-06-23

**Tasks**:
- [x] Configure standard PyPI packaging with pyproject.toml
- [x] Update installation documentation for pip install workflow
- [x] Test pip install workflow locally with editable install
- [x] Create release automation scripts and GitHub Actions workflow
- [x] Document release process in docs/arch-docs/releases.md
- [x] Fix Docker compose file packaging issues with embedded templates
- [x] Add support for both `docker compose` and `docker-compose` commands

**Implementation Details**:
- **Package Configuration**: Updated `pyproject.toml` with proper metadata, version 0.2.2, broader Python support (3.10+), and enhanced classifiers
- **Installation Documentation**: Completely rewrote `README.md` installation section with new pip workflow, replaced Docker container setup with simple `pip install heimdall-mcp`
- **CLI Testing**: Successfully tested both `cognitive-cli` and `memory_system` command interfaces work correctly when installed
- **Release Automation**: Created comprehensive release infrastructure:
  - `scripts/release.py` - Automated release script with validation, building, and upload capabilities
  - `.github/workflows/release.yml` - GitHub Actions workflow for automated releases
  - `.pypirc.template` - PyPI authentication template for easier setup
  - `docs/arch-docs/releases.md` - Complete release management documentation
- **Docker Integration Fix**: Resolved packaging issues by embedding Docker compose template directly in code (eliminates external file dependencies)
- **Cross-Platform Docker Support**: Added fallback logic to support both modern `docker compose` and legacy `docker-compose` commands

**Key Achievements**:
- **Standard Python Packaging**: Clean pip install workflow with no external dependencies
- **Automated Release Pipeline**: Both manual and GitHub Actions-based release workflows
- **Cross-Platform Compatibility**: Works on Windows, macOS, Linux with Python 3.10+
- **Embedded Resources**: No external file dependencies for Docker compose templates
- **Comprehensive Documentation**: Complete release process and troubleshooting guides

**Current Issues (Testing Phase)**:
- Docker compose command compatibility (fixed with fallback logic)
- Temporary file cleanup in service manager (needs polish)
- Container name conflicts and port binding error handling (needs improvement)
- Docker daemon availability checking (needs better error messages)

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
- **2025-06-23**: Completed Phase 1 (Steps 1-3) - Core migration infrastructure with shared Qdrant architecture
- **2025-06-23**: Completed Phase 2 (Steps 4-6) - Feature migration with host-based monitoring, Python git hooks, and project management CLI
- **2025-06-23**: Completed Phase 3 (Steps 7-8) - Legacy code removal and Python package setup with comprehensive release automation
- **2025-06-23**: **MILESTONE COMPLETED** - Shared Qdrant architecture migration finished same day, now in final testing and polish phase

**Final Status**: All 8 steps completed. System successfully migrated from per-project Docker containers to shared Qdrant architecture with standard Python packaging. Ready for production release after final Docker integration polish.
