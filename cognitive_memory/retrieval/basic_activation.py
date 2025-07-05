"""
Basic activation engine implementation using BFS traversal.

This module implements the foundational activation spreading mechanism
that activates memories through breadth-first search traversal of the
memory connection graph.
"""

import time
from collections import deque

import numpy as np
from loguru import logger

from ..core.interfaces import ActivationEngine, ConnectionGraph, MemoryStorage
from ..core.memory import ActivationResult, CognitiveMemory


class BasicActivationEngine(ActivationEngine):
    """
    Basic activation engine using BFS traversal for memory activation.

    Implements context-driven activation spreading that starts with high-similarity
    memories at L0 (concepts) and spreads activation through the connection graph
    using breadth-first search with threshold-based filtering.
    """

    def __init__(
        self,
        memory_storage: MemoryStorage,
        connection_graph: ConnectionGraph,
        core_threshold: float = 0.7,
        peripheral_threshold: float = 0.5,
    ):
        """
        Initialize basic activation engine.

        Args:
            memory_storage: Storage interface for memory access
            connection_graph: Connection graph for traversal
            core_threshold: Threshold for core memory activation
            peripheral_threshold: Threshold for peripheral memory activation
        """
        self.memory_storage = memory_storage
        self.connection_graph = connection_graph
        self.core_threshold = core_threshold
        self.peripheral_threshold = peripheral_threshold

    def activate_memories(
        self, context: np.ndarray, threshold: float, max_activations: int = 50
    ) -> ActivationResult:
        """
        Activate memories based on context with spreading activation.

        Implementation follows the algorithm specification:
        1. Find high-similarity L0 concepts as starting points
        2. Use BFS to spread activation through connection graph
        3. Apply threshold-based filtering to limit computational overhead
        4. Track activation strength for result ranking

        Args:
            context: Context vector for similarity computation
            threshold: Minimum activation threshold
            max_activations: Maximum number of memories to activate

        Returns:
            ActivationResult with core and peripheral memories
        """
        start_time = time.time()

        try:
            # Phase 1: Find high-similarity L0 concepts as starting points
            l0_memories = self.memory_storage.get_memories_by_level(0)
            starting_memories = self._find_starting_memories(
                context, l0_memories, threshold
            )

            if not starting_memories:
                logger.debug("No starting memories found for activation")
                return ActivationResult(
                    activation_time_ms=(time.time() - start_time) * 1000
                )

            # Phase 2: BFS traversal through connection graph
            activation_result = self._bfs_activation(
                context, starting_memories, threshold, max_activations
            )

            # Calculate timing
            activation_result.activation_time_ms = (time.time() - start_time) * 1000

            logger.debug(
                "Memory activation completed",
                core_count=len(activation_result.core_memories),
                peripheral_count=len(activation_result.peripheral_memories),
                total_activated=activation_result.total_activated,
                time_ms=activation_result.activation_time_ms,
            )

            return activation_result

        except Exception as e:
            logger.error("Memory activation failed", error=str(e))
            return ActivationResult(
                activation_time_ms=(time.time() - start_time) * 1000
            )

    def _find_starting_memories(
        self,
        context: np.ndarray,
        l0_memories: list[CognitiveMemory],
        threshold: float,
    ) -> list[CognitiveMemory]:
        """
        Find L0 memories with high similarity to context as starting points.

        Args:
            context: Context vector for similarity computation
            l0_memories: List of L0 (concept) memories
            threshold: Minimum similarity threshold

        Returns:
            List of starting memories for activation
        """
        starting_memories = []

        for memory in l0_memories:
            if memory.cognitive_embedding is not None:
                similarity = self._compute_cosine_similarity(
                    context, memory.cognitive_embedding
                )
                logger.debug(
                    f"L0 memory similarity: {similarity:.3f} vs threshold {threshold:.3f} for: {memory.content[:50]}"
                )
                if similarity >= threshold:
                    starting_memories.append(memory)

        # Sort by similarity (highest first)
        starting_memories.sort(
            key=lambda m: self._compute_cosine_similarity(
                context, m.cognitive_embedding
            )
            if m.cognitive_embedding is not None
            else 0.0,
            reverse=True,
        )

        logger.debug(
            f"Found {len(starting_memories)} starting memories from {len(l0_memories)} L0 concepts"
        )
        return starting_memories

    def _bfs_activation(
        self,
        context: np.ndarray,
        starting_memories: list[CognitiveMemory],
        threshold: float,
        max_activations: int,
    ) -> ActivationResult:
        """
        Perform BFS traversal to activate connected memories.

        Args:
            context: Context vector for similarity computation
            starting_memories: Starting memories for BFS
            threshold: Minimum activation threshold
            max_activations: Maximum number of memories to activate

        Returns:
            ActivationResult with activated memories
        """
        # Initialize BFS structures
        queue = deque(starting_memories)
        activated_ids: set[str] = set()
        core_memories: list[CognitiveMemory] = []
        peripheral_memories: list[CognitiveMemory] = []
        activation_strengths: dict[str, float] = {}

        # Process starting memories
        for memory in starting_memories:
            if memory.cognitive_embedding is not None:
                similarity = self._compute_cosine_similarity(
                    context, memory.cognitive_embedding
                )
                strength = memory.calculate_activation_strength(similarity)
                activation_strengths[memory.id] = strength

                if strength >= self.core_threshold:
                    core_memories.append(memory)
                elif strength >= self.peripheral_threshold:
                    peripheral_memories.append(memory)

                activated_ids.add(memory.id)

        # BFS traversal through connection graph
        while queue and len(activated_ids) < max_activations:
            current_memory = queue.popleft()

            # Get connected memories
            try:
                connected_memories = self.connection_graph.get_connections(
                    current_memory.id, min_strength=self.peripheral_threshold
                )

                for connected_memory in connected_memories:
                    if connected_memory.id not in activated_ids:
                        # Calculate activation strength
                        if connected_memory.cognitive_embedding is not None:
                            similarity = self._compute_cosine_similarity(
                                context, connected_memory.cognitive_embedding
                            )
                            strength = connected_memory.calculate_activation_strength(
                                similarity
                            )

                            # Apply threshold filtering
                            if strength >= threshold:
                                activation_strengths[connected_memory.id] = strength
                                activated_ids.add(connected_memory.id)

                                # Categorize as core or peripheral
                                if strength >= self.core_threshold:
                                    core_memories.append(connected_memory)
                                elif strength >= self.peripheral_threshold:
                                    peripheral_memories.append(connected_memory)

                                # Add to queue for further traversal
                                queue.append(connected_memory)

                                # Check activation limit
                                if len(activated_ids) >= max_activations:
                                    break

            except Exception as e:
                logger.warning(
                    "Failed to get connections for memory",
                    memory_id=current_memory.id,
                    error=str(e),
                )
                continue

        # Sort memories by activation strength
        core_memories.sort(
            key=lambda m: activation_strengths.get(m.id, 0.0), reverse=True
        )
        peripheral_memories.sort(
            key=lambda m: activation_strengths.get(m.id, 0.0), reverse=True
        )

        return ActivationResult(
            core_memories=core_memories,
            peripheral_memories=peripheral_memories,
            activation_strengths=activation_strengths,
        )

    def _compute_cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        try:
            # Ensure arrays have compatible dtypes
            if vec1.dtype != vec2.dtype:
                vec2 = vec2.astype(vec1.dtype)

            # Compute cosine similarity
            dot_product = np.dot(vec1.flatten(), vec2.flatten())
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)

            # Clamp to [0, 1] range and handle numerical issues
            similarity = np.clip(similarity, 0.0, 1.0)

            return float(similarity)

        except Exception as e:
            logger.warning("Cosine similarity computation failed", error=str(e))
            return 0.0

    def get_activation_config(self) -> dict[str, float]:
        """
        Get current activation configuration.

        Returns:
            Dictionary with activation thresholds
        """
        return {
            "core_threshold": self.core_threshold,
            "peripheral_threshold": self.peripheral_threshold,
        }

    def update_thresholds(
        self, core_threshold: float, peripheral_threshold: float
    ) -> None:
        """
        Update activation thresholds.

        Args:
            core_threshold: New core threshold
            peripheral_threshold: New peripheral threshold
        """
        self.core_threshold = max(0.0, min(1.0, core_threshold))
        self.peripheral_threshold = max(0.0, min(1.0, peripheral_threshold))

        logger.debug(
            "Activation thresholds updated",
            core_threshold=self.core_threshold,
            peripheral_threshold=self.peripheral_threshold,
        )
