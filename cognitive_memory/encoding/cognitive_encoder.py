"""
Cognitive encoder with multi-dimensional fusion layer.

This module implements the core cognitive encoding system that combines
Sentence-BERT semantic embeddings with rule-based cognitive dimensions
through a simple linear transformation to produce rich cognitive memory
representations with configurable dimensions.

Now uses NumPy for reduced dependencies and faster CPU inference.
"""

from typing import Any

import numpy as np
from loguru import logger

from ..core.config import SystemConfig
from .dimensions import CognitiveDimensionExtractor
from .sentence_bert import SentenceBERTProvider


class CognitiveFusionLayer:
    """
    Linear fusion layer that combines semantic and dimensional features.

    Takes concatenated Sentence-BERT embeddings and cognitive dimensions
    and transforms them into a unified cognitive representation
    through a simple linear transformation with configurable output dimensions.
    """

    def __init__(self, semantic_dim: int, cognitive_dim: int, output_dim: int) -> None:
        """
        Initialize the fusion layer.

        Args:
            semantic_dim: Dimensionality of semantic embeddings (Sentence-BERT)
            cognitive_dim: Dimensionality of cognitive dimensions
            output_dim: Dimensionality of final cognitive embeddings
        """
        self.semantic_dim = semantic_dim
        self.cognitive_dim = cognitive_dim
        self.output_dim = output_dim
        self.input_dim = semantic_dim + cognitive_dim

        # Initialize weights and bias for linear transformation
        self.weight = np.random.normal(0, 0.1, (self.input_dim, output_dim)).astype(
            np.float32
        )
        self.bias = np.zeros(output_dim, dtype=np.float32)

        # Layer normalization parameters
        self.layer_norm_weight = np.ones(output_dim, dtype=np.float32)
        self.layer_norm_bias = np.zeros(output_dim, dtype=np.float32)
        self.layer_norm_eps = 1e-5

        # Initialize weights using Xavier uniform-like initialization
        self._initialize_weights()

        logger.debug(
            "Cognitive fusion layer initialized",
            semantic_dim=semantic_dim,
            cognitive_dim=cognitive_dim,
            output_dim=output_dim,
            total_params=self.weight.size
            + self.bias.size
            + self.layer_norm_weight.size
            + self.layer_norm_bias.size,
        )

    def _initialize_weights(self) -> None:
        """Initialize layer weights using Xavier uniform-like initialization."""
        # Xavier uniform initialization approximation
        limit = np.sqrt(6.0 / (self.input_dim + self.output_dim))
        self.weight = np.random.uniform(
            -limit, limit, (self.input_dim, self.output_dim)
        ).astype(np.float32)
        self.bias = np.zeros(self.output_dim, dtype=np.float32)

    def forward(
        self, semantic_embedding: np.ndarray, cognitive_dimensions: np.ndarray
    ) -> np.ndarray:
        """
        Forward pass through the fusion layer.

        Args:
            semantic_embedding: Sentence-BERT embedding array [batch_size, semantic_dim] or [semantic_dim]
            cognitive_dimensions: Cognitive dimensions array [batch_size, cognitive_dim] or [cognitive_dim]

        Returns:
            np.ndarray: Fused cognitive embedding [batch_size, output_dim] or [output_dim]
        """
        # Handle both single and batch inputs
        if semantic_embedding.ndim == 1:
            semantic_embedding = semantic_embedding.reshape(1, -1)
            single_input = True
        else:
            single_input = False

        if cognitive_dimensions.ndim == 1:
            cognitive_dimensions = cognitive_dimensions.reshape(1, -1)

        # Ensure batch dimensions match
        batch_size = semantic_embedding.shape[0]
        if cognitive_dimensions.shape[0] != batch_size:
            cognitive_dimensions = np.tile(cognitive_dimensions, (batch_size, 1))

        # Concatenate semantic and cognitive features
        combined_features = np.concatenate(
            [semantic_embedding, cognitive_dimensions], axis=1
        )

        # Apply linear transformation
        fused_embedding = np.dot(combined_features, self.weight) + self.bias

        # Apply layer normalization
        fused_embedding = self._layer_norm(fused_embedding)

        # Return single array if single input was provided
        result: np.ndarray
        if single_input:
            result = fused_embedding.squeeze(0)
        else:
            result = fused_embedding

        return result

    def _layer_norm(self, x: np.ndarray) -> np.ndarray:
        """Apply layer normalization."""
        mean = np.mean(x, axis=-1, keepdims=True)
        var = np.var(x, axis=-1, keepdims=True)
        normalized = (x - mean) / np.sqrt(var + self.layer_norm_eps)
        result: np.ndarray = normalized * self.layer_norm_weight + self.layer_norm_bias
        return result


class CognitiveEncoder:
    """
    Complete cognitive encoding system combining semantic and dimensional analysis.

    This encoder integrates Sentence-BERT semantic embeddings with rule-based
    cognitive dimensions through a learned fusion layer to create rich
    cognitive memory representations suitable for the multi-layered memory system.

    Now uses NumPy for all operations instead of PyTorch.
    """

    def __init__(
        self,
        sentence_bert_model: str | None = None,
        model_path: str | None = None,
        tokenizer_path: str | None = None,
        config_path: str | None = None,
        fusion_weights_path: str | None = None,
        config: SystemConfig | None = None,
    ) -> None:
        """
        Initialize the cognitive encoder.

        Args:
            sentence_bert_model: Name of Sentence-BERT model to use (for compatibility)
            model_path: Path to ONNX model file
            tokenizer_path: Path to tokenizer directory
            config_path: Path to model config JSON
            fusion_weights_path: Path to pre-trained fusion layer weights (no longer supported)
            config: System configuration containing embedding dimensions
        """
        # Load configuration
        if config is None:
            config = SystemConfig.from_env()
        self.config = config

        # Initialize components
        logger.info("Initializing cognitive encoder components")

        # Initialize Sentence-BERT provider (now using ONNX)
        self.semantic_provider = SentenceBERTProvider(
            model_name=sentence_bert_model,
            model_path=model_path,
            tokenizer_path=tokenizer_path,
            config_path=config_path,
        )

        # Initialize cognitive dimension extractor
        self.dimension_extractor = CognitiveDimensionExtractor(self.config.cognitive)

        # Get dimensions for fusion layer
        self.semantic_dim = self.semantic_provider.get_embedding_dimension()
        self.cognitive_dim = self.dimension_extractor.get_total_dimensions()
        self.output_dim = self.semantic_dim + self.cognitive_dim  # Concatenation

        # Initialize fusion layer
        self.fusion_layer = CognitiveFusionLayer(
            semantic_dim=self.semantic_dim,
            cognitive_dim=self.cognitive_dim,
            output_dim=self.output_dim,
        )

        # Note: Pre-trained weight loading is no longer supported in NumPy version
        if fusion_weights_path:
            logger.warning(
                "Pre-trained fusion weights are not supported in NumPy version",
                path=fusion_weights_path,
            )

        logger.info(
            "Cognitive encoder initialized successfully",
            semantic_dim=self.semantic_dim,
            cognitive_dim=self.cognitive_dim,
            output_dim=self.output_dim,
            provider_type="ONNX Runtime + NumPy",
        )

    def reset_weights(self, seed: int = 42) -> None:
        """
        Reset fusion layer weights deterministically for testing.

        Args:
            seed: Random seed for deterministic weight initialization
        """
        np.random.seed(seed)
        self.fusion_layer._initialize_weights()
        logger.debug("Fusion layer weights reset", seed=seed)

    def encode(self, text: str, context: dict[str, Any] | None = None) -> np.ndarray:
        """
        Encode text into a cognitive memory representation.

        Args:
            text: Input text to encode
            context: Optional context information (currently unused)

        Returns:
            np.ndarray: Cognitive embedding with configured dimensions
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for cognitive encoding")
            return np.zeros(self.output_dim, dtype=np.float32)

        try:
            # Extract semantic embedding
            semantic_embedding = self.semantic_provider.encode(text)

            # Extract cognitive dimensions
            dimension_dict = self.dimension_extractor.extract_dimensions(text)

            # Concatenate all cognitive dimensions
            cognitive_dims = np.concatenate(
                [
                    dimension_dict["emotional"],
                    dimension_dict["temporal"],
                    dimension_dict["contextual"],
                    dimension_dict["social"],
                ],
                axis=0,
            )

            # Fuse through linear layer
            cognitive_embedding = self.fusion_layer.forward(
                semantic_embedding, cognitive_dims
            )

            logger.debug(
                "Text encoded into cognitive representation",
                text_length=len(text),
                semantic_shape=semantic_embedding.shape,
                cognitive_dims_shape=cognitive_dims.shape,
                output_shape=cognitive_embedding.shape,
            )

            return cognitive_embedding

        except Exception as e:
            logger.error(
                "Failed to encode text cognitively",
                text_preview=text[:100] + "..." if len(text) > 100 else text,
                error=str(e),
            )
            return np.zeros(self.output_dim, dtype=np.float32)

    def encode_batch(
        self, texts: list[str], contexts: list[dict[str, Any]] | None = None
    ) -> np.ndarray:
        """
        Encode multiple texts into cognitive memory representations.

        Args:
            texts: List of input texts to encode
            contexts: Optional list of context information (currently unused)

        Returns:
            np.ndarray: Batch of cognitive embeddings with configured dimensions
        """
        if not texts:
            logger.warning("Empty text list provided for batch encoding")
            return np.zeros((0, self.output_dim), dtype=np.float32)

        try:
            # Extract semantic embeddings for all texts
            semantic_embeddings = self.semantic_provider.encode_batch(texts)

            # Extract cognitive dimensions for all texts
            batch_cognitive_dims = []
            for text in texts:
                dimension_dict = self.dimension_extractor.extract_dimensions(text)
                cognitive_dims = np.concatenate(
                    [
                        dimension_dict["emotional"],
                        dimension_dict["temporal"],
                        dimension_dict["contextual"],
                        dimension_dict["social"],
                    ],
                    axis=0,
                )
                batch_cognitive_dims.append(cognitive_dims)

            # Stack cognitive dimensions into batch array
            cognitive_dims_batch = np.stack(batch_cognitive_dims, axis=0)

            # Fuse through linear layer
            cognitive_embeddings = self.fusion_layer.forward(
                semantic_embeddings, cognitive_dims_batch
            )

            logger.debug(
                "Batch encoded into cognitive representations",
                batch_size=len(texts),
                semantic_shape=semantic_embeddings.shape,
                cognitive_dims_shape=cognitive_dims_batch.shape,
                output_shape=cognitive_embeddings.shape,
            )

            return cognitive_embeddings

        except Exception as e:
            logger.error(
                "Failed to encode text batch cognitively",
                batch_size=len(texts),
                error=str(e),
            )
            return np.zeros((len(texts), self.output_dim), dtype=np.float32)

    def get_dimension_breakdown(self, text: str) -> dict[str, Any]:
        """
        Get detailed breakdown of dimensions extracted from text.

        Args:
            text: Input text to analyze

        Returns:
            dict: Detailed dimension analysis including scores and explanations
        """
        try:
            # Get semantic embedding
            semantic_embedding = self.semantic_provider.encode(text)

            # Get cognitive dimensions
            dimension_dict = self.dimension_extractor.extract_dimensions(text)
            dimension_names = self.dimension_extractor.get_all_dimension_names()

            breakdown: dict[str, Any] = {
                "semantic_embedding_norm": float(np.linalg.norm(semantic_embedding)),
                "dimensions": {},
            }

            # Add detailed dimension breakdowns
            for category, array in dimension_dict.items():
                names = dimension_names[category]
                values = array.tolist()

                breakdown["dimensions"][category] = {
                    "values": values,
                    "names": names,
                    "total_activation": float(sum(values)),
                    "max_dimension": names[values.index(max(values))]
                    if values
                    else None,
                    "max_value": float(max(values)) if values else 0.0,
                }

            return breakdown

        except Exception as e:
            logger.error(
                "Failed to generate dimension breakdown",
                text_preview=text[:100] + "..." if len(text) > 100 else text,
                error=str(e),
            )
            return {"error": str(e)}

    def save_fusion_weights(self, weights_path: str) -> bool:
        """Save current fusion layer weights (NumPy format)."""
        try:
            weights_data = {
                "weight": self.fusion_layer.weight,
                "bias": self.fusion_layer.bias,
                "layer_norm_weight": self.fusion_layer.layer_norm_weight,
                "layer_norm_bias": self.fusion_layer.layer_norm_bias,
            }
            np.savez(
                weights_path,
                weight=weights_data["weight"],
                bias=weights_data["bias"],
                layer_norm_weight=weights_data["layer_norm_weight"],
                layer_norm_bias=weights_data["layer_norm_bias"],
            )
            logger.info("Fusion layer weights saved successfully", path=weights_path)
            return True
        except Exception as e:
            logger.error(
                "Failed to save fusion weights", path=weights_path, error=str(e)
            )
            return False

    def load_fusion_weights(self, weights_path: str) -> bool:
        """Load fusion layer weights (NumPy format)."""
        try:
            weights_data = np.load(weights_path)
            self.fusion_layer.weight = weights_data["weight"]
            self.fusion_layer.bias = weights_data["bias"]
            self.fusion_layer.layer_norm_weight = weights_data["layer_norm_weight"]
            self.fusion_layer.layer_norm_bias = weights_data["layer_norm_bias"]
            logger.info("Fusion layer weights loaded successfully", path=weights_path)
            return True
        except Exception as e:
            logger.warning(
                "Failed to load fusion weights, using random initialization",
                path=weights_path,
                error=str(e),
            )
            return False

    def get_encoder_info(self) -> dict[str, Any]:
        """Get information about the encoder configuration."""
        return {
            "semantic_provider": self.semantic_provider.get_model_info(),
            "dimension_extractor": {
                "total_dimensions": self.cognitive_dim,
                "dimension_breakdown": self.dimension_extractor.get_all_dimension_names(),
            },
            "fusion_layer": {
                "input_dim": self.semantic_dim + self.cognitive_dim,
                "output_dim": self.output_dim,
                "parameters": self.fusion_layer.weight.size
                + self.fusion_layer.bias.size,
                "implementation": "NumPy linear layer",
            },
        }


def create_cognitive_encoder(
    sentence_bert_model: str | None = None,
    model_path: str | None = None,
    tokenizer_path: str | None = None,
    config_path: str | None = None,
    fusion_weights_path: str | None = None,
    config: SystemConfig | None = None,
) -> CognitiveEncoder:
    """
    Factory function to create a cognitive encoder.

    Args:
        sentence_bert_model: Name of Sentence-BERT model to use (for compatibility)
        model_path: Path to ONNX model file
        tokenizer_path: Path to tokenizer directory
        config_path: Path to model config JSON
        fusion_weights_path: Path to pre-trained fusion weights (NumPy format)
        config: System configuration

    Returns:
        CognitiveEncoder: Configured encoder instance
    """
    return CognitiveEncoder(
        sentence_bert_model=sentence_bert_model,
        model_path=model_path,
        tokenizer_path=tokenizer_path,
        config_path=config_path,
        fusion_weights_path=fusion_weights_path,
        config=config,
    )
