"""
ONNX-based embedding provider for semantic embedding generation.

This module provides an ONNX Runtime-based implementation for generating
high-quality semantic embeddings, replacing the PyTorch-based sentence-transformers
stack for significant memory and dependency reduction.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
from loguru import logger
from tokenizers import Tokenizer

from ..core.config import EmbeddingConfig
from ..core.interfaces import EmbeddingProvider


class ONNXEmbeddingProvider(EmbeddingProvider):
    """
    ONNX Runtime-based embedding provider implementing the EmbeddingProvider interface.

    Provides semantic embeddings using ONNX models with tokenizers library
    for tokenization, replacing the PyTorch + transformers + sentence-transformers stack.
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        tokenizer_path: str | Path | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        """
        Initialize the ONNX embedding provider.

        Args:
            model_path: Path to the ONNX model file. If None, uses package resource.
            tokenizer_path: Path to the tokenizer directory. If None, uses package resource.
            config_path: Path to the model config JSON. If None, uses package resource.
        """
        self.embedding_config = EmbeddingConfig.from_env()

        # Use provided paths or get from package resources
        self.model_path = (
            Path(model_path)
            if model_path
            else self._get_package_resource_path(
                f"{self.embedding_config.model_name}.onnx"
            )
        )

        self.tokenizer_path = (
            Path(tokenizer_path)
            if tokenizer_path
            else self._get_package_resource_path("tokenizer")
        )

        self.config_path = (
            Path(config_path)
            if config_path
            else self._get_package_resource_path("model_config.json")
        )

        logger.info(
            "Initializing ONNX embedding provider",
            model_path=str(self.model_path),
            tokenizer_path=str(self.tokenizer_path),
        )

        try:
            # Load model configuration
            self._load_config()

            # Initialize ONNX Runtime session
            self._load_onnx_model()

            # Initialize tokenizer
            self._load_tokenizer()

            logger.info(
                "ONNX embedding provider loaded successfully",
                embedding_dim=self.embedding_dimension,
                model_name=self.model_name,
            )

        except Exception as e:
            logger.error(
                "Failed to load ONNX embedding provider",
                model_path=str(self.model_path),
                error=str(e),
            )
            raise RuntimeError(
                f"Failed to initialize ONNX embedding provider: {e}"
            ) from e

    def _get_package_resource_path(self, filename: str) -> Path:
        """Get path to a resource file from shared data directory."""
        from heimdall.cognitive_system.data_dirs import get_models_data_dir

        model_path = get_models_data_dir() / filename
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model file not found: {model_path}. "
                f"Run 'heimdall project init' to download required models."
            )
        return model_path

    def _load_config(self) -> None:
        """Load model configuration from JSON file."""
        try:
            with open(self.config_path) as f:
                config = json.load(f)

            self.model_name = config["model_name"]
            self.max_length = config["max_length"]
            self.embedding_dimension = int(config["embedding_dimension"])

            logger.debug("Model configuration loaded", config=config)

        except Exception as e:
            logger.error("Failed to load model configuration", error=str(e))
            raise

    def _load_onnx_model(self) -> None:
        """Load ONNX model using ONNX Runtime."""
        try:
            # Create ONNX Runtime session with optimizations
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = (
                ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            )

            self.ort_session = ort.InferenceSession(
                str(self.model_path),
                sess_options,
                providers=["CPUExecutionProvider"],  # CPU-only for consistency
            )

            # Get input/output info
            self.input_names = [inp.name for inp in self.ort_session.get_inputs()]
            self.output_names = [out.name for out in self.ort_session.get_outputs()]

            logger.debug(
                "ONNX model loaded", inputs=self.input_names, outputs=self.output_names
            )

        except Exception as e:
            logger.error("Failed to load ONNX model", error=str(e))
            raise

    def _load_tokenizer(self) -> None:
        """Load tokenizer from the tokenizer directory."""
        try:
            # Load tokenizer from the saved directory
            tokenizer_file = self.tokenizer_path / "tokenizer.json"
            if not tokenizer_file.exists():
                raise FileNotFoundError(f"Tokenizer file not found: {tokenizer_file}")

            self.tokenizer = Tokenizer.from_file(str(tokenizer_file))

            logger.debug("Tokenizer loaded successfully")

        except Exception as e:
            logger.error("Failed to load tokenizer", error=str(e))
            raise

    def _tokenize_text(self, text: str) -> dict[str, np.ndarray]:
        """
        Tokenize text using the loaded tokenizer.

        Args:
            text: Input text to tokenize

        Returns:
            Dictionary with input_ids and attention_mask as numpy arrays
        """
        # Tokenize the text
        encoding = self.tokenizer.encode(text)

        # Get token IDs and create attention mask
        input_ids = encoding.ids
        attention_mask = [1] * len(input_ids)

        # Pad or truncate to max_length
        if len(input_ids) > self.max_length:
            input_ids = input_ids[: self.max_length]
            attention_mask = attention_mask[: self.max_length]
        else:
            padding_length = self.max_length - len(input_ids)
            input_ids.extend([0] * padding_length)  # 0 is typically the pad token
            attention_mask.extend([0] * padding_length)

        return {
            "input_ids": np.array([input_ids], dtype=np.int64),
            "attention_mask": np.array([attention_mask], dtype=np.int64),
        }

    def _tokenize_batch(self, texts: list[str]) -> dict[str, np.ndarray]:
        """
        Tokenize a batch of texts.

        Args:
            texts: List of input texts to tokenize

        Returns:
            Dictionary with input_ids and attention_mask as numpy arrays
        """
        all_input_ids = []
        all_attention_masks = []

        for text in texts:
            # Tokenize individual text
            encoding = self.tokenizer.encode(text)
            input_ids = encoding.ids
            attention_mask = [1] * len(input_ids)

            # Pad or truncate to max_length
            if len(input_ids) > self.max_length:
                input_ids = input_ids[: self.max_length]
                attention_mask = attention_mask[: self.max_length]
            else:
                padding_length = self.max_length - len(input_ids)
                input_ids.extend([0] * padding_length)
                attention_mask.extend([0] * padding_length)

            all_input_ids.append(input_ids)
            all_attention_masks.append(attention_mask)

        return {
            "input_ids": np.array(all_input_ids, dtype=np.int64),
            "attention_mask": np.array(all_attention_masks, dtype=np.int64),
        }

    def _run_inference(
        self, input_ids: np.ndarray, attention_mask: np.ndarray
    ) -> np.ndarray:
        """
        Run ONNX inference to get embeddings.

        Args:
            input_ids: Token IDs array
            attention_mask: Attention mask array

        Returns:
            Normalized embedding vectors
        """
        # Prepare inputs for ONNX Runtime
        ort_inputs = {"input_ids": input_ids, "attention_mask": attention_mask}

        # Run inference
        ort_outputs = self.ort_session.run(self.output_names, ort_inputs)

        # Extract embeddings (first output)
        embeddings = ort_outputs[0]

        # Ensure embeddings are 2D (batch_size, embedding_dim)
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)

        return embeddings.astype(np.float32)  # type: ignore[no-any-return]

    def encode(self, text: str) -> np.ndarray:
        """
        Encode a single text into a semantic embedding vector.

        Args:
            text: Input text to encode

        Returns:
            np.ndarray: Semantic embedding vector
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for encoding")
            return np.zeros(self.embedding_dimension, dtype=np.float32)

        try:
            # Tokenize the text
            tokens = self._tokenize_text(text.strip())

            # Run ONNX inference
            embeddings = self._run_inference(
                tokens["input_ids"], tokens["attention_mask"]
            )

            # Return single embedding
            embedding = embeddings[0]

            logger.debug(
                "Text encoded successfully",
                text_length=len(text),
                embedding_shape=embedding.shape,
            )

            return embedding  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(
                "Failed to encode text",
                text_preview=text[:100] + "..." if len(text) > 100 else text,
                error=str(e),
            )
            # Return zero vector as fallback
            return np.zeros(self.embedding_dimension, dtype=np.float32)

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        """
        Encode multiple texts into semantic embedding vectors.

        Args:
            texts: List of input texts to encode

        Returns:
            np.ndarray: Batch of semantic embedding vectors
        """
        if not texts:
            logger.warning("Empty text list provided for batch encoding")
            return np.zeros((0, self.embedding_dimension), dtype=np.float32)

        # Filter out empty texts and track indices
        filtered_texts = []
        valid_indices = []

        for i, text in enumerate(texts):
            if text and text.strip():
                filtered_texts.append(text.strip())
                valid_indices.append(i)
            else:
                logger.warning(f"Empty text at index {i} in batch")

        if not filtered_texts:
            logger.warning("No valid texts in batch after filtering")
            return np.zeros((len(texts), self.embedding_dimension), dtype=np.float32)

        try:
            # Tokenize the batch
            tokens = self._tokenize_batch(filtered_texts)

            # Run ONNX inference
            embeddings = self._run_inference(
                tokens["input_ids"], tokens["attention_mask"]
            )

            # If we had empty texts, we need to reconstruct the full batch
            if len(valid_indices) != len(texts):
                full_embeddings = np.zeros(
                    (len(texts), self.embedding_dimension), dtype=np.float32
                )
                for i, valid_idx in enumerate(valid_indices):
                    full_embeddings[valid_idx] = embeddings[i]
                embeddings = full_embeddings

            logger.debug(
                "Batch encoded successfully",
                batch_size=len(texts),
                valid_texts=len(filtered_texts),
                embedding_shape=embeddings.shape,
            )

            return embeddings

        except Exception as e:
            logger.error(
                "Failed to encode text batch",
                batch_size=len(texts),
                valid_texts=len(filtered_texts),
                error=str(e),
            )
            # Return zero vectors as fallback
            return np.zeros((len(texts), self.embedding_dimension), dtype=np.float32)

    def get_embedding_dimension(self) -> int:
        """Get the dimensionality of the embeddings."""
        return self.embedding_dimension

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the loaded model."""
        return {
            "model_name": self.model_name,
            "embedding_dimension": self.embedding_dimension,
            "max_sequence_length": self.max_length,
            "model_path": str(self.model_path),
            "tokenizer_path": str(self.tokenizer_path),
            "onnx_providers": self.ort_session.get_providers(),
        }

    def compute_similarity(
        self, embedding1: np.ndarray, embedding2: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding array
            embedding2: Second embedding array

        Returns:
            float: Cosine similarity score between -1 and 1
        """
        try:
            # Ensure embeddings are normalized
            norm1 = embedding1 / np.linalg.norm(embedding1)
            norm2 = embedding2 / np.linalg.norm(embedding2)

            # Compute cosine similarity
            similarity = np.dot(norm1, norm2)

            return float(similarity)

        except Exception as e:
            logger.error(
                "Failed to compute similarity",
                embedding1_shape=embedding1.shape,
                embedding2_shape=embedding2.shape,
                error=str(e),
            )
            return 0.0

    def compute_batch_similarity(
        self, query_embedding: np.ndarray, candidate_embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Compute similarity between a query embedding and multiple candidates.

        Args:
            query_embedding: Single query embedding array
            candidate_embeddings: Batch of candidate embedding arrays

        Returns:
            np.ndarray: Similarity scores for each candidate
        """
        try:
            # Ensure all embeddings are normalized
            query_norm = query_embedding / np.linalg.norm(query_embedding)
            candidates_norm = candidate_embeddings / np.linalg.norm(
                candidate_embeddings, axis=1, keepdims=True
            )

            # Compute batch cosine similarity
            similarities = np.dot(candidates_norm, query_norm)

            return similarities.astype(np.float32)  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(
                "Failed to compute batch similarity",
                query_shape=query_embedding.shape,
                candidates_shape=candidate_embeddings.shape,
                error=str(e),
            )
            return np.zeros(candidate_embeddings.shape[0], dtype=np.float32)


def create_onnx_provider(
    model_path: str | Path | None = None,
    tokenizer_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> ONNXEmbeddingProvider:
    """
    Factory function to create an ONNX embedding provider.

    Args:
        model_path: Path to the ONNX model file
        tokenizer_path: Path to the tokenizer directory
        config_path: Path to the model configuration JSON

    Returns:
        ONNXEmbeddingProvider: Configured provider instance
    """
    return ONNXEmbeddingProvider(
        model_path=model_path, tokenizer_path=tokenizer_path, config_path=config_path
    )
