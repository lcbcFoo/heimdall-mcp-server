# 021 - Shared Qdrant Architecture Migration

## Overview
Migration from per-project Docker containers to a single shared Qdrant instance with Python package distribution. This milestone eliminates container proliferation, simplifies installation, and reduces resource consumption while maintaining project isolation through collection namespacing.

## Status
- **Started**: 2025-06-23
- **Current Step**: Phase 1, Step 3 (Service Manager Updates)
- **Completion**: 25% (2/8 steps completed)
- **Expected Completion**: 2025-07-21 (4 weeks)

## Objectives
- [ ] Implement shared Qdrant architecture with project-scoped collections
- [ ] Migrate file monitoring from container-based to host-based daemon
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
**Status**: Not Started
**Date Range**: 2025-06-26 - 2025-07-01

**Tasks**:
- [ ] Modify `memory_system/service_manager.py` for single shared Qdrant
- [ ] Create simplified docker-compose.yml for shared instance
- [ ] Remove per-project Docker container logic
- [ ] Add shared Qdrant health checks

### Phase 2: Feature Migration (Week 2-3)

#### Step 4: Host-based File Monitoring
**Status**: Not Started
**Date Range**: 2025-06-30 - 2025-07-07

**Tasks**:
- [ ] Create `memory_system/host_monitoring.py` with host-based daemon
- [ ] Replace container environment variables with `.heimdall/config.yaml`
- [ ] Implement project-local PID files (`.heimdall/monitor.pid`)
- [ ] Add multi-project PID collision prevention
- [ ] Update CLI commands for PID-based supervision

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
- **Process Management**: Host-based daemons with project-local PID files

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
- **Process Management**: Host daemons more complex than container lifecycle

### Mitigation
- **Fresh Start Approach**: No backward compatibility required, clean slate
- **Configuration Hierarchy**: Clear precedence order (CLI > env > config file > defaults)
- **Robust PID Management**: Proper cleanup, collision detection, health checks

## Resources
- **Architecture Document**: `docs/shared-qdrant-architecture.md`
- **Current Container Logic**: `memory_system/service_manager.py`, `scripts/setup_project_memory.sh`
- **Monitoring Service**: `memory_system/monitoring_service.py`
- **Collection Management**: `cognitive_memory/storage/qdrant_storage.py`

## Change Log
- **2025-06-23**: Initial milestone creation and task breakdown
- **2025-06-23**: Completed Phase 1, Step 2 (Project-Scoped Collections) - Implemented project-isolated collection naming with comprehensive testing
