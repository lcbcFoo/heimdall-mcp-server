# 021 - Shared Qdrant Architecture Migration

## Overview
Migration from per-project Docker containers to a single shared Qdrant instance with Python package distribution. This milestone eliminates container proliferation, simplifies installation, and reduces resource consumption while maintaining project isolation through collection namespacing.

## Status
- **Started**: 2025-06-23
- **Current Step**: Phase 2, Step 5 (Git Hook Migration)
- **Completion**: 50% (4/8 steps completed)
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
**Status**: Not Started
**Date Range**: 2025-07-02 - 2025-07-09

**Tasks**:
- [ ] Create new hook template `templates/git/post-commit-v2.sh`
- [ ] Update `scripts/git-hook-installer.sh` for simplified host CLI execution
- [ ] Remove Docker exec dependencies from hooks
- [ ] Add deprecation shim for container-based hooks
- [ ] Test hook installation/uninstallation safety

#### Step 6: Project Management CLI
**Status**: Not Started
**Date Range**: 2025-07-07 - 2025-07-14

**Tasks**:
- [ ] Add `memory_system project init` command (also detects qdrant status and starts qdrant if needed)
- [ ] Add `memory_system project list` command
- [ ] Add `memory_system project clean <name>` command
- [ ] Update existing CLI commands for project-scoped operations
- [ ] Add project auto-detection from working directory

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
