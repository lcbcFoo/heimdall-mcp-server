Task MISSING

Task: Implement Download-on-First-Use Model Storage

  Objective: Replace packaged models with shared directory + GitHub releases to eliminate duplicate storage across virtual environments.

  Changes Required:

  1. Update pyproject.toml: Remove models from package data
  # Remove: "data/models/*", "data/models/tokenizer/*"
  cognitive_memory = ["storage/migrations/*.sql"]
  2. Add model download function to heimdall/cognitive_system/data_dirs.py:
  def ensure_models_available() -> Path:
      """Download models to shared directory if not present."""
      # Check if models exist in shared dir
      # If not, download from GitHub releases
      # Extract to ~/.local/share/heimdall/models/
  3. Create GitHub release with models:
  cd cognitive_memory/data
  zip -r heimdall-models-v0.2.10.zip models/
  gh release create v0.2.10 heimdall-models-v0.2.10.zip
  4. Update initialization: Call ensure_models_available() in initialize_shared_environment()
  5. Update config: Point MODEL_CACHE_DIR to shared directory

  Benefits:
  - Single model copy across all venv installations (~60MB saved per environment)
  - Smaller pip package
  - Faster installs
  - Industry standard approach (like spaCy, HuggingFace)


----

 Shared Model Storage Implementation

  Current Model Storage:

  - Location: ./data/models (project-local, legacy path)
  - Configuration: EmbeddingConfig.model_cache_dir
  - Environment Variable: MODEL_CACHE_DIR

  Updated Shared Model Storage (Option B):

  # Shared data directory structure
  ~/.local/share/heimdall/           # Linux
  ├── qdrant/                        # Shared Qdrant storage
  │   ├── aliases/
  │   ├── collections/
  │   └── meta.json
  ├── models/                        # 🆕 Shared model cache
  │   ├── all-MiniLM-L6-v2.onnx     # ONNX model
  │   ├── tokenizer/                 # Tokenizer files
  │   │   ├── tokenizer.json
  │   │   └── special_tokens_map.json
  │   ├── model_config.json          # Model configuration
  │   └── huggingface_cache/         # HuggingFace downloads
  └── logs/                          # 🆕 Shared logs (optional)

  # Per-project (unchanged)
  ./project/.heimdall/
  ├── config.yaml
  └── cognitive_memory.db

  Implementation Changes:

  Step 1: Update Data Directory Utility

  # heimdall/cognitive_system/data_dirs.py
  from pathlib import Path
  import platformdirs

  def get_heimdall_data_dir() -> Path:
      """Get cross-platform Heimdall data directory."""
      return Path(platformdirs.user_data_dir("heimdall", "heimdall-mcp"))

  def get_qdrant_data_dir() -> Path:
      """Get Qdrant data directory."""
      return get_heimdall_data_dir() / "qdrant"

  def get_models_data_dir() -> Path:  # 🆕
      """Get shared models directory."""
      return get_heimdall_data_dir() / "models"

  def get_logs_data_dir() -> Path:  # 🆕
      """Get shared logs directory."""
      return get_heimdall_data_dir() / "logs"

  def ensure_data_directories() -> None:
      """Ensure all data directories exist."""
      get_qdrant_data_dir().mkdir(parents=True, exist_ok=True)
      get_models_data_dir().mkdir(parents=True, exist_ok=True)  # 🆕
      get_logs_data_dir().mkdir(parents=True, exist_ok=True)   # 🆕

  Step 2: Update EmbeddingConfig Default

  # In cognitive_memory/core/config.py
  @dataclass
  class EmbeddingConfig:
      """Configuration for embedding models."""

      model_name: str = "all-MiniLM-L6-v2"
      model_cache_dir: str = _get_default_model_cache_dir()  # 🆕 Dynamic default
      embedding_dimension: int = 384
      batch_size: int = 32
      device: str = "auto"

  def _get_default_model_cache_dir() -> str:
      """Get default model cache directory using standard data dirs."""
      try:
          from heimdall.cognitive_system.data_dirs import get_models_data_dir
          return str(get_models_data_dir())
      except ImportError:
          # Fallback for backward compatibility
          return "./data/models"

  Step 3: Update Environment Variable Handling

  # Set shared model directory as environment variable during system init
  import os
  from heimdall.cognitive_system.data_dirs import get_models_data_dir, ensure_data_directories

  def initialize_shared_environment():
      """Initialize shared data directories and environment variables."""
      ensure_data_directories()

      # Set environment variables for model caching
      models_dir = get_models_data_dir()

      # Set for ONNX provider
      os.environ.setdefault("MODEL_CACHE_DIR", str(models_dir))

      # Set for HuggingFace transformers (used by some components)
      os.environ.setdefault("TRANSFORMERS_CACHE", str(models_dir / "huggingface_cache"))
      os.environ.setdefault("HF_HOME", str(models_dir / "huggingface_cache"))

      # Set for Sentence Transformers
      os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(models_dir))

  Step 4: Migration Strategy

  # heimdall/cognitive_system/migration.py
  def migrate_legacy_data() -> None:
      """Migrate data from legacy locations to shared directories."""

      # Migrate models from ./data/models to shared location
      legacy_model_dir = Path("./data/models")
      if legacy_model_dir.exists():
          shared_models_dir = get_models_data_dir()

          print(f"Migrating models from {legacy_model_dir} to {shared_models_dir}")

          for model_file in legacy_model_dir.rglob("*"):
              if model_file.is_file():
                  relative_path = model_file.relative_to(legacy_model_dir)
                  target_path = shared_models_dir / relative_path
                  target_path.parent.mkdir(parents=True, exist_ok=True)

                  if not target_path.exists():
                      import shutil
                      shutil.copy2(model_file, target_path)
                      print(f"  Copied: {relative_path}")

          print("✅ Model migration completed")

      # Migrate Docker volumes (existing tmp_qdrant_storage)
      # This would be handled by Docker volume migration logic

  Step 5: Update Health Checker

  # Update health checker to verify new standard directories
  def check_data_directories():
      """Check that standard data directories exist and are accessible."""
      checks = {}

      try:
          from heimdall.cognitive_system.data_dirs import (
              get_heimdall_data_dir,
              get_qdrant_data_dir,
              get_models_data_dir
          )

          # Check main data directory
          data_dir = get_heimdall_data_dir()
          checks["heimdall_data_dir"] = {
              "status": "✅ PASS" if data_dir.exists() else "❌ FAIL",
              "path": str(data_dir),
              "message": "Heimdall data directory accessible"
          }

          # Check models directory
          models_dir = get_models_data_dir()
          checks["models_dir"] = {
              "status": "✅ PASS" if models_dir.exists() else "❌ FAIL",
              "path": str(models_dir),
              "message": "Shared models directory accessible"
          }

          # Check Qdrant directory
          qdrant_dir = get_qdrant_data_dir()
          checks["qdrant_dir"] = {
              "status": "✅ PASS" if qdrant_dir.exists() else "❌ FAIL",
              "path": str(qdrant_dir),
              "message": "Shared Qdrant directory accessible"
          }

      except Exception as e:
          checks["data_dirs_error"] = {
              "status": "❌ FAIL",
              "message": f"Error checking data directories: {e}"
          }

      return checks

  Benefits of Shared Model Storage:

  1. 💾 Space Efficiency: Models downloaded once, used by all projects
  2. ⚡ Faster Setup: New projects don't need to re-download models
  3. 🧹 Easy Cleanup: User knows exactly where models are stored
  4. 💾 Predictable Backup: Standard location for backup/restore
  5. 🔄 Version Management: Easier to upgrade/manage model versions
  6. 📂 OS Compliance: Follows platform-specific data directory conventions
