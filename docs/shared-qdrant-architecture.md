# Shared Qdrant Architecture Migration

## Problem Statement

Current architecture creates Docker container proliferation and installation friction:

1. **Container per project**: Each project gets `heimdall-{repo}-{hash}` + `qdrant-{repo}-{hash}` containers
2. **Disk waste**: Multiple identical Docker images (100MB+ each × N projects)
3. **Installation complexity**: 370-line bash setup script with Docker permission issues
4. **Scalability**: Unsustainable for users with many projects

## Solution: Single Shared Qdrant + Python Package

### Architecture Changes

**Before:**
```
Project A: heimdall-a-abc123 + qdrant-a-abc123 containers
Project B: heimdall-b-def456 + qdrant-b-def456 containers
Project C: heimdall-c-ghi789 + qdrant-c-ghi789 containers
```

**After:**
```
Single shared Qdrant container
├── project-a-abc123_concepts
├── project-a-abc123_contexts
├── project-a-abc123_episodes
├── project-b-def456_concepts
├── project-b-def456_contexts
├── project-b-def456_episodes
└── project-c-ghi789_...
```

### User Workflow

```bash
# One-time setup (starts shared Qdrant)
memory_system qdrant start

# In each project
pip install heimdall-mcp
memory_system project init    # Creates project-specific collections
cognitive-cli load .          # Uses project-scoped collections
```

## Feature Impact Analysis

### File Monitoring Impact

**Current Dependencies on Containers:**
- MonitoringService runs as daemon within per-project containers
- Environment variables like `MONITORING_TARGET_PATH` injected at container level
- PID files stored in `/tmp` within containers
- Health checks rely on container lifecycle

**Required Changes:**
- **Host-based Daemon**: Convert MonitoringService to run as host process using project-local PID files (`.heimdall/monitor.pid`)
- **Configuration Migration**: Replace container env vars with `.heimdall/config.yaml`:
  ```yaml
  project_id: "abc123"
  monitoring_target_path: "./docs"
  qdrant_url: "http://localhost:6333"
  monitoring_interval: 5.0
  ignore_patterns: [".git", "node_modules", "__pycache__"]
  ```
- **Process Management**: Update CLI commands to use PID-based supervision instead of Docker exec
- **Multi-Project Safety**: Handle multiple projects on same host without PID collisions

### Git Hooks Impact

**Current Container Dependencies:**
- Hooks detect project containers by name: `heimdall-{repo-name}-{project-hash}`
- Use `docker exec` to run commands within containers
- Fall back to host CLI only when containers missing

**Migration Path:**
- **Simplified Hook Template**: New hook always uses host CLI since no project containers exist:
  ```bash
  #!/usr/bin/env bash
  set -euo pipefail
  if command -v memory_system >/dev/null; then
      memory_system load-git incremental --cwd "$(git rev-parse --show-toplevel)"
  fi
  ```
- **Project Isolation**: Use `project_id` from `.heimdall/config.yaml` instead of container names
- **Backward Compatibility**: Provide deprecation shim for one release cycle
- **Safe Installation**: Preserve existing hook chaining logic but update execution

### Service Management Commands

**Command Mapping:**
```bash
# Old: Container-based
memory_system monitor start  # → docker compose up -d heimdall-{project}
memory_system monitor stop   # → docker compose down heimdall-{project}
memory_system monitor status # → docker ps | grep heimdall-{project}

# New: Host-based
memory_system monitor start  # → Python daemon + PID file in .heimdall/
memory_system monitor stop   # → kill PID from .heimdall/monitor.pid
memory_system monitor status # → check PID exists and responsive
```

**Implementation Changes:**
- Replace Docker lifecycle management with process supervision
- Move from system-wide to project-local PID files
- Update health checks from container status to process ping
- Maintain same CLI interface for backward compatibility

### Configuration Strategy

**Migration from Container Env to Config Files:**

| Container Environment | New Configuration |
|----------------------|-------------------|
| `MONITORING_TARGET_PATH` | `.heimdall/config.yaml: monitoring_target_path` |
| `PROJECT_ID` / `PROJECT_HASH` | `.heimdall/config.yaml: project_id` |
| `QDRANT_URL` | Keep as env var + config file fallback |
| `COGNITIVE_MEMORY_DB_PATH` | `.heimdall/config.yaml: db_path` |
| Container isolation | Qdrant collection namespacing |

**Config File Schema:**
```yaml
# .heimdall/config.yaml
project_id: "myproject_abc123"
qdrant_url: "http://localhost:6333"
monitoring:
  target_path: "./docs"
  interval_seconds: 5.0
  ignore_patterns: [".git", "node_modules"]
git:
  auto_load: true
  max_commits_per_hook: 1
database:
  path: "./.heimdall/cognitive_memory.db"
```

## Implementation Plan

### Phase 1: Core Migration Infrastructure (Week 1-2)

**1. Configuration System**
```python
# cognitive_memory/core/project_config.py
@dataclass
class ProjectConfig:
    project_id: str
    qdrant_url: str = "http://localhost:6333"
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    git: GitConfig = field(default_factory=GitConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)

    @classmethod
    def load_from_project(cls, path: Path) -> "ProjectConfig":
        """Load config from .heimdall/config.yaml with env var fallbacks"""
```

**2. Host-based MonitoringService**
- Refactor `memory_system/monitoring_service.py`:
  - Remove Docker dependencies
  - Use project-local PID files: `.heimdall/monitor.pid`
  - Read config from `.heimdall/config.yaml`
  - Handle multi-project PID collision prevention

**3. Update Service Manager**
- Modify `memory_system/service_manager.py` for single shared instance
- Replace per-project Docker logic with simple shared docker-compose.yml

**4. Project-Scoped Collections**
- Update `QdrantCollectionManager` collection naming:
  ```python
  # Current: "cognitive_concepts"
  # New: f"{project_id}_concepts"
  ```

### Phase 2: Feature Migration (Week 2-3)

**1. File Monitoring Migration**
- Create `memory_system/host_monitoring.py` with host-based daemon
- Update CLI commands to use PID-based supervision
- Add configuration loading from `.heimdall/config.yaml`
- Implement multi-project safety checks

**2. Git Hook Migration**
- Create new hook template in `templates/git/post-commit-v2.sh`
- Update `scripts/git-hook-installer.sh` for new template
- Add deprecation shim for container-based hooks
- Maintain safe installation/uninstallation logic

**3. CLI Extensions**
```bash
memory_system project init           # Setup collections for current project
memory_system project list           # List all projects
memory_system project clean <name>   # Remove project collections
```

**4. Update Existing Commands**
- Modify `cognitive-cli` to use project-scoped collections
- Project detection from current working directory

### Phase 3: Clean Package (Week 3-4)

**Remove Legacy Code**
- Delete `scripts/setup_project_memory.sh` (370 lines)
- Remove `docker/docker-compose.template.yml`
- Clean up per-project Docker logic

**Package Distribution**
- Standard PyPI packaging workflow
- Update documentation

## Technical Details

### Project Identification
```python
def get_project_id(path: str) -> str:
    """Generate project ID from path."""
    project_hash = hashlib.sha256(path.encode()).hexdigest()[:8]
    repo_name = os.path.basename(path)
    return f"{repo_name}_{project_hash}"
```

### Collection Naming
```python
def get_collection_names(project_id: str) -> dict:
    """Get collection names for project."""
    return {
        0: f"{project_id}_concepts",
        1: f"{project_id}_contexts",
        2: f"{project_id}_episodes"
    }
```

### Configuration
```yaml
# ~/.heimdall/config.yaml
qdrant:
  url: "http://localhost:6333"

projects:
  "/path/to/proj-a": "proj-a_abc123"
  "/path/to/proj-b": "proj-b_def456"
```

## Benefits

| Current | New |
|---------|-----|
| N × 2 containers per project | 1 shared container |
| N × 100MB+ disk usage | 1 × 100MB disk usage |
| Complex Docker setup scripts | `pip install` + simple CLI |
| Docker permission issues | Pure Python, no permissions |
| Container management overhead | Standard Python package |

## Implementation Notes

- Keep all Qdrant features: hierarchical collections, metadata filtering, performance
- No data migration needed (fresh start approach)
- Existing CLI architecture (`memory_system`, `cognitive-cli`) extends naturally
- Project isolation maintained through collection naming
- Backward compatibility not required

## Timeline

**Total: 3-4 weeks**
- Week 1-2: Shared Qdrant service + collection scoping
- Week 2-3: CLI extensions + project management
- Week 3-4: Package cleanup + distribution
