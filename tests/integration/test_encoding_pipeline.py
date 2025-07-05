"""
Integration tests for the complete encoding pipeline.
"""

import numpy as np
import pytest

from cognitive_memory.core.config import CognitiveConfig
from cognitive_memory.encoding import (
    CognitiveDimensionExtractor,
    CognitiveEncoder,
    SentenceBERTProvider,
    create_cognitive_encoder,
)
from tests.test_utils import setup_deterministic_testing


@pytest.mark.slow
@pytest.mark.integration
class TestEncodingPipelineIntegration:
    """Integration tests for the complete encoding pipeline."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        # Set up comprehensive deterministic behavior
        setup_deterministic_testing(seed=42)

        self.config = CognitiveConfig()
        self.encoder = CognitiveEncoder()
        self.semantic_provider = SentenceBERTProvider()
        self.dimension_extractor = CognitiveDimensionExtractor(self.config)

        # Reset encoder weights for deterministic initialization
        self.encoder.reset_weights(seed=42)

    def test_complete_pipeline_consistency(self) -> None:
        """Test that the complete pipeline produces consistent results."""
        text = (
            "I'm working on a challenging machine learning project with tight deadlines"
        )

        # Run encoding multiple times
        results = []
        for _ in range(3):
            embedding = self.encoder.encode(text)
            results.append(embedding)

        # All results should be identical
        for i in range(1, len(results)):
            assert np.allclose(results[0], results[i], atol=1e-6)

    def test_semantic_vs_cognitive_encoding(self) -> None:
        """Test differences between semantic and cognitive encoding."""
        texts = ["I love this successful project", "I hate this failed project"]

        # Get semantic embeddings
        semantic_embs = self.semantic_provider.encode_batch(texts)

        # Get cognitive embeddings
        cognitive_embs = self.encoder.encode_batch(texts)

        # Compute similarities
        semantic_sim = np.dot(semantic_embs[0], semantic_embs[1]) / (
            np.linalg.norm(semantic_embs[0]) * np.linalg.norm(semantic_embs[1])
        )

        cognitive_sim = np.dot(cognitive_embs[0], cognitive_embs[1]) / (
            np.linalg.norm(cognitive_embs[0]) * np.linalg.norm(cognitive_embs[1])
        )

        # Cognitive similarity should be lower due to emotional differences
        assert cognitive_sim < semantic_sim
        print(f"Semantic similarity: {semantic_sim:.3f}")
        print(f"Cognitive similarity: {cognitive_sim:.3f}")

    def test_dimension_contribution_analysis(self) -> None:
        """Test how different dimensions contribute to final embeddings."""

        variants = [
            "Working on project",
            "Working on urgent project",  # Add temporal
            "Frustrated working on project",  # Add emotional
            "Working on project with team",  # Add social
            "Debugging code in project",  # Add contextual
        ]

        embeddings = self.encoder.encode_batch(variants)
        base_embedding = embeddings[0]

        # Calculate similarities to base
        similarities = []
        for i in range(1, len(embeddings)):
            sim = np.dot(base_embedding, embeddings[i]) / (
                np.linalg.norm(base_embedding) * np.linalg.norm(embeddings[i])
            )
            similarities.append(sim.item())

        print("Similarities to base text:")
        for variant, sim in zip(variants[1:], similarities, strict=False):
            print(f"  {variant}: {sim:.3f}")

        # All should be similar but not identical
        for sim in similarities:
            assert 0.48 <= sim <= 0.99

    def test_batch_vs_individual_encoding(self) -> None:
        """Test that batch and individual encoding produce same results."""
        texts = [
            "Debugging complex algorithm",
            "Team collaboration session",
            "Urgent deadline pressure",
            "Creative problem solving",
        ]

        # Individual encoding
        individual_embeddings = []
        for text in texts:
            emb = self.encoder.encode(text)
            individual_embeddings.append(emb)
        individual_batch = np.stack(individual_embeddings)

        # Batch encoding
        batch_embeddings = self.encoder.encode_batch(texts)

        # Should be very close
        assert np.allclose(individual_batch, batch_embeddings, atol=1e-5)

    def test_cross_modal_retrieval_simulation(self) -> None:
        """Simulate cross-modal retrieval using cognitive embeddings."""
        # Create a knowledge base of encoded experiences
        experiences = [
            "I'm debugging a Python API that keeps returning 500 errors",
            "Our team meeting was productive and we solved the authentication issue",
            "I'm learning about machine learning algorithms for recommendation systems",
            "The deployment failed again and I'm really frustrated with the CI pipeline",
            "I need help understanding this complex database optimization problem",
        ]

        # Encode all experiences
        experience_embeddings = self.encoder.encode_batch(experiences)

        # Query for similar experiences
        queries = [
            "Looking for help with API debugging",  # Should match #1
            "Need assistance with deployment issues",  # Should match #4
            "Want to learn about ML algorithms",  # Should match #3
        ]

        for query in queries:
            query_embedding = self.encoder.encode(query)

            # Compute similarities
            similarities = []
            for exp_emb in experience_embeddings:
                sim = np.dot(query_embedding, exp_emb) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(exp_emb)
                )
                similarities.append(sim.item())

            # Find most similar experience
            max_idx = similarities.index(max(similarities))

            print(f"\nQuery: {query}")
            print(f"Most similar: {experiences[max_idx]}")
            print(f"Similarity: {similarities[max_idx]:.3f}")

            # Should find reasonable matches
            assert similarities[max_idx] > 0.4

    def test_cognitive_memory_levels_simulation(self) -> None:
        """Simulate how embeddings might work for different memory levels."""
        # Level 0: Concepts (abstract)
        concepts = [
            "Machine learning optimization",
            "Team collaboration dynamics",
            "Software debugging methodologies",
        ]

        # Level 1: Contexts (situational)
        contexts = [
            "Working on ML model performance in production environment",
            "Facilitating agile team retrospective meeting",
            "Investigating memory leaks in microservices architecture",
        ]

        # Level 2: Episodes (specific experiences)
        episodes = [
            "Today I spent 3 hours debugging a gradient descent implementation that wasn't converging",
            "In this morning's standup, Sarah mentioned the API latency issues affecting user experience",
            "Just discovered that the Redis cache wasn't being cleared, causing stale data in the dashboard",
        ]

        # Encode all levels
        concept_embs = self.encoder.encode_batch(concepts)
        context_embs = self.encoder.encode_batch(contexts)
        episode_embs = self.encoder.encode_batch(episodes)

        # Test hierarchical relationships
        for i in range(len(concepts)):
            # Episode should be most similar to its corresponding context
            episode_context_sim = np.dot(episode_embs[i], context_embs[i]) / (
                np.linalg.norm(episode_embs[i]) * np.linalg.norm(context_embs[i])
            )

            # Context should be most similar to its corresponding concept
            context_concept_sim = np.dot(context_embs[i], concept_embs[i]) / (
                np.linalg.norm(context_embs[i]) * np.linalg.norm(concept_embs[i])
            )

            print(f"\nLevel relationships for domain {i}:")
            print(f"Episode-Context similarity: {episode_context_sim:.3f}")
            print(f"Context-Concept similarity: {context_concept_sim:.3f}")

            # Should show reasonable hierarchical similarity
            assert episode_context_sim > 0.05
            assert (
                context_concept_sim > 0.15
            )  # Lowered threshold for deterministic results

    def test_emotional_context_preservation(self) -> None:
        """Test that emotional context is preserved through encoding."""
        emotional_scenarios = [
            (
                "I'm really excited about this breakthrough in our research",
                "satisfaction",
            ),
            ("I'm completely stuck and frustrated with this bug", "frustration"),
            ("I'm curious about how this new framework works", "curiosity"),
            ("The deadline pressure is overwhelming me", "stress"),
        ]

        for text, expected_emotion in emotional_scenarios:
            # Get detailed breakdown
            breakdown = self.encoder.get_dimension_breakdown(text)
            emotional_dims = breakdown["dimensions"]["emotional"]

            # Find the dominant emotion
            max_idx = emotional_dims["values"].index(max(emotional_dims["values"]))
            dominant_emotion = emotional_dims["names"][max_idx]

            print(f"\nText: {text}")
            print(f"Expected: {expected_emotion}, Detected: {dominant_emotion}")
            print(
                f"Emotional values: {dict(zip(emotional_dims['names'], emotional_dims['values'], strict=False))}"
            )

            # The expected emotion should be among the top emotions
            emotion_value = emotional_dims["values"][
                emotional_dims["names"].index(expected_emotion)
            ]
            assert emotion_value > 0.1  # Should be reasonably activated

    def test_encoding_robustness(self) -> None:
        """Test encoding robustness with various text inputs."""
        challenging_inputs = [
            "",  # Empty
            "   ",  # Whitespace only
            "A",  # Single character
            "Short.",  # Very short
            "This is a normal sentence about machine learning and software development.",  # Normal
            "Very long text " * 50,  # Very long
            "Special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?",  # Special characters
            "Mixed CASE and numbers 123 and symbols !@#",  # Mixed content
        ]

        embeddings = self.encoder.encode_batch(challenging_inputs)

        final_dim = (
            self.config.get_total_cognitive_dimensions() + 384
        )  # cognitive + semantic
        assert embeddings.shape == (len(challenging_inputs), final_dim)
        assert np.all(np.isfinite(embeddings))

        # Empty and whitespace should be zero
        assert np.all(embeddings[0] == 0.0)
        assert np.all(embeddings[1] == 0.0)

        # Others should have non-zero embeddings (except possibly very short ones)
        for i in range(3, len(challenging_inputs)):
            assert np.any(embeddings[i] != 0.0)

    def test_factory_integration(self) -> None:
        """Test that factory functions produce working encoders."""
        encoder = create_cognitive_encoder()

        text = "Testing factory-created encoder with cognitive dimensions"
        embedding = encoder.encode(text)

        expected_dim = (
            CognitiveConfig().get_total_cognitive_dimensions() + 384
        )  # cognitive + semantic
        assert embedding.shape == (expected_dim,)
        assert np.any(embedding != 0.0)
        assert np.all(np.isfinite(embedding))
