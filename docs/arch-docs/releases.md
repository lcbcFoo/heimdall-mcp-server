# Release Management Architecture

## Overview

This document describes the release management process for the Heimdall MCP package, covering automated and manual release workflows, version management, and distribution to PyPI.

## Package Configuration

The package uses modern Python packaging standards defined in `pyproject.toml`:
- Package name: `heimdall-mcp`
- Python 3.10+ compatibility
- CLI entry points for `cognitive-cli` and `memory_system` commands
- Comprehensive dependency management

See `pyproject.toml` for complete configuration details.

## Release Workflows

### 1. Automated GitHub Actions Release

**File**: `.github/workflows/release.yml`

**Triggers**:
- **GitHub Release creation**: Automatically uploads to PyPI
- **Manual workflow dispatch**: Choose TestPyPI or PyPI

**Required Secrets**:
- `PYPI_API_TOKEN`: PyPI upload authentication
- `TEST_PYPI_API_TOKEN`: TestPyPI upload authentication

### 2. Manual Release Script

**File**: `scripts/release.py`

**Features**:
- Package validation and dependency checking
- Clean artifact management
- Source and wheel distribution building
- Quality validation with twine
- Upload options for TestPyPI and PyPI

**Usage**:
```bash
# Dry run (build and validate only)
python scripts/release.py --no-upload

# Test release to TestPyPI
python scripts/release.py --test-upload

# Production release to PyPI
python scripts/release.py --upload
```

## Release Process

### Development Release (Testing)

1. **Prepare and test locally**:
   ```bash
   python scripts/release.py --no-upload
   ```

2. **Upload to TestPyPI**:
   ```bash
   python scripts/release.py --test-upload
   ```

3. **Validate installation**:
   ```bash
   pip install --index-url https://test.pypi.org/simple/ heimdall-mcp
   cognitive-cli --help
   memory_system project init
   ```

### Production Release

#### Option A: GitHub Release (Recommended)

1. Go to GitHub repo → Releases → "Create a new release"
2. Create new tag: `v0.2.0` (semantic versioning)
3. Add release title and notes
4. Click "Publish release" - GitHub Actions handles the rest

#### Option B: Manual Release

1. **Local release**:
   ```bash
   python scripts/release.py --upload
   ```

2. **Tag release**:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```

## Version Management

### Semantic Versioning

Format: `MAJOR.MINOR.PATCH`
- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

### Version Sources

- **Primary**: `pyproject.toml` version field
- **Runtime**: `cognitive_memory/core/version.py`
- **Git tags**: Should match pyproject.toml version

## Distribution Architecture

### Entry Points

Installation creates CLI commands:
- `heimdall` - CLI to manage projects and access heimdall features

### Dependencies

Core dependencies include Qdrant client, ONNX runtime, MCP protocol, and CLI frameworks. See `pyproject.toml` for complete dependency specifications.

## Security Considerations

### Supply Chain Security

- Pin dependency versions with appropriate constraints
- Use consistent build environments (GitHub Actions)
- Validate distributions with twine before upload

## Troubleshooting

### Common Issues

**Import Errors During Validation**:
```bash
pip install -e .
python -c "import cognitive_memory"
```

**Build Failures**:
```bash
pip install build twine
rm -rf build/ dist/ *.egg-info/
python -m build
```

**Upload Authentication**:
```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=your-api-token
```

### Debug Commands

```bash
# Validate distribution
python -m twine check dist/*

# Test local installation
pip install dist/heimdall_mcp-*.whl
```
