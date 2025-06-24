"""
Cross-platform data directory management for Heimdall shared resources.

This module provides standardized locations for shared data following OS conventions:
- Linux: ~/.local/share/heimdall/
- macOS: ~/Library/Application Support/heimdall/
- Windows: %LOCALAPPDATA%\\heimdall\\
"""

import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

try:
    import platformdirs

    PLATFORMDIRS_AVAILABLE = True
except ImportError:
    PLATFORMDIRS_AVAILABLE = False


def get_heimdall_data_dir() -> Path:
    """
    Get cross-platform Heimdall data directory.

    Returns:
        Path: Platform-appropriate data directory for Heimdall

    Examples:
        Linux: ~/.local/share/heimdall/
        macOS: ~/Library/Application Support/heimdall/
        Windows: %LOCALAPPDATA%\\heimdall\\
    """
    if PLATFORMDIRS_AVAILABLE:
        return Path(platformdirs.user_data_dir("heimdall", "heimdall-mcp"))
    else:
        # Fallback for systems without platformdirs
        home = Path.home()
        if os.name == "nt":  # Windows
            return home / "AppData" / "Local" / "heimdall"
        elif os.name == "posix":
            if "darwin" in os.uname().sysname.lower():  # macOS
                return home / "Library" / "Application Support" / "heimdall"
            else:  # Linux and other Unix
                return home / ".local" / "share" / "heimdall"
        else:
            # Generic fallback
            return home / ".heimdall-shared"


def get_qdrant_data_dir() -> Path:
    """
    Get shared Qdrant data directory.

    Returns:
        Path: Directory for shared Qdrant vector database storage
    """
    return get_heimdall_data_dir() / "qdrant"


def get_models_data_dir() -> Path:
    """
    Get shared models directory.

    Returns:
        Path: Directory for shared ML models and embeddings
    """
    return get_heimdall_data_dir() / "models"


def get_logs_data_dir() -> Path:
    """
    Get shared logs directory.

    Returns:
        Path: Directory for shared system logs
    """
    return get_heimdall_data_dir() / "logs"


def ensure_data_directories() -> None:
    """
    Ensure all required data directories exist.

    Creates the directory structure if it doesn't exist:
    - heimdall/
    - heimdall/qdrant/
    - heimdall/models/
    - heimdall/logs/
    """
    directories = [
        get_heimdall_data_dir(),
        get_qdrant_data_dir(),
        get_models_data_dir(),
        get_logs_data_dir(),
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def get_data_directory_info() -> dict[str, str]:
    """
    Get information about data directory locations.

    Returns:
        dict: Mapping of directory names to their absolute paths
    """
    return {
        "heimdall_data": str(get_heimdall_data_dir()),
        "qdrant_data": str(get_qdrant_data_dir()),
        "models_data": str(get_models_data_dir()),
        "logs_data": str(get_logs_data_dir()),
    }


def initialize_shared_environment() -> None:
    """
    Initialize shared data directories and set environment variables.

    This function:
    1. Creates all required data directories
    2. Sets environment variables for various model caching systems
    3. Ensures consistent model storage location across all components
    """
    ensure_data_directories()

    models_dir = get_models_data_dir()

    # Set environment variables for model caching
    # ONNX provider
    os.environ.setdefault("MODEL_CACHE_DIR", str(models_dir))

    # HuggingFace transformers cache
    hf_cache = models_dir / "huggingface_cache"
    os.environ.setdefault("TRANSFORMERS_CACHE", str(hf_cache))
    os.environ.setdefault("HF_HOME", str(hf_cache))

    # Sentence Transformers cache
    os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(models_dir))

    # ONNX-specific paths (used by cognitive_memory/encoding/onnx_provider.py)
    os.environ.setdefault("ONNX_MODEL_PATH", str(models_dir / "all-MiniLM-L6-v2.onnx"))
    os.environ.setdefault("ONNX_TOKENIZER_PATH", str(models_dir / "tokenizer"))
    os.environ.setdefault("ONNX_CONFIG_PATH", str(models_dir / "model_config.json"))


def ensure_models_available() -> Path:
    """
    Download models to shared directory if not present.

    Implements download-on-first-use pattern for ML models, downloading from
    GitHub releases if models are not found in the shared directory.

    Returns:
        Path: Directory containing the downloaded models

    Raises:
        RuntimeError: If model download fails
    """
    models_dir = get_models_data_dir()

    # Check if critical model files exist
    critical_files = [
        models_dir / "all-MiniLM-L6-v2.onnx",
        models_dir / "tokenizer" / "tokenizer.json",
        models_dir / "model_config.json",
    ]

    if all(file.exists() for file in critical_files):
        return models_dir

    # Models missing, need to download
    print(f"Models not found in {models_dir}, downloading...")

    try:
        _download_models_from_github(models_dir)
        print("✅ Models downloaded successfully")
        return models_dir
    except Exception as e:
        raise RuntimeError(f"Failed to download models: {e}") from e


def _download_models_from_github(target_dir: Path) -> None:
    """
    Download and extract models from GitHub releases.

    Args:
        target_dir: Directory to extract models to
    """
    # Import version information
    try:
        from cognitive_memory.core.version import SYSTEM_VERSION

        version = SYSTEM_VERSION
    except ImportError:
        version = "0.2.10"  # Fallback version

    # GitHub release configuration
    github_repo = "lcbcFoo/heimdall-mcp-server"
    release_tag = f"v{version}"
    asset_name = f"heimdall-models-v{version}.zip"

    download_url = (
        f"https://github.com/{github_repo}/releases/download/{release_tag}/{asset_name}"
    )

    # Create target directory
    target_dir.mkdir(parents=True, exist_ok=True)

    # Download to temporary file
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp_file:
        temp_path = Path(temp_file.name)

        try:
            print(f"Downloading models from {download_url}...")
            urllib.request.urlretrieve(download_url, temp_path)

            # Extract zip file
            print(f"Extracting models to {target_dir}...")
            with zipfile.ZipFile(temp_path, "r") as zip_file:
                # Extract to temporary directory first
                with tempfile.TemporaryDirectory() as extract_dir:
                    zip_file.extractall(extract_dir)

                    # Find the models directory in extracted content
                    extract_path = Path(extract_dir)
                    models_src = None

                    # Look for models directory in extracted content
                    for item in extract_path.rglob("models"):
                        if item.is_dir():
                            models_src = item
                            break

                    if not models_src:
                        # If no models directory found, assume all files are models
                        models_src = extract_path

                    # Copy files to target directory
                    for item in models_src.rglob("*"):
                        if item.is_file():
                            relative_path = item.relative_to(models_src)
                            target_file = target_dir / relative_path
                            target_file.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(item, target_file)

        finally:
            # Clean up temporary file
            temp_path.unlink(missing_ok=True)


def migrate_legacy_data() -> None:
    """
    Migrate data from legacy locations to shared directories.

    This function moves existing model data from project-local locations
    to the shared data directory to avoid duplication.
    """
    # Migrate models from ./data/models to shared location
    legacy_model_dir = Path("./data/models")
    if legacy_model_dir.exists():
        shared_models_dir = get_models_data_dir()

        print(f"Migrating models from {legacy_model_dir} to {shared_models_dir}")

        migrated_files = []
        for model_file in legacy_model_dir.rglob("*"):
            if model_file.is_file():
                relative_path = model_file.relative_to(legacy_model_dir)
                target_path = shared_models_dir / relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)

                if not target_path.exists():
                    shutil.copy2(model_file, target_path)
                    migrated_files.append(str(relative_path))

        if migrated_files:
            print(f"  Migrated {len(migrated_files)} files:")
            for file in migrated_files[:5]:  # Show first 5 files
                print(f"    • {file}")
            if len(migrated_files) > 5:
                print(f"    ... and {len(migrated_files) - 5} more files")
        else:
            print(
                "  No new files to migrate (all files already exist in shared location)"
            )

        print("✅ Model migration completed")
