"""Memory Metabolism logic for the Cortex Memory Engine.
Implements the Ebbinghaus forgetting curve and status transitions.
"""

import math
from datetime import datetime, timezone
from typing import List
from src.models import MemoryNode, MemoryStatus

class MemoryMetabolism:
    """Handles the decay and lifecycle of memory nodes."""

    def __init__(self, stability_factor: float = 24.0):
        """Initialize the metabolism engine.
        
        Args:
            stability_factor: The 'half-life' constant in hours. 
                             Higher means memory lasts longer.
        """
        self.stability_factor = stability_factor

    def calculate_current_importance(self, memory: MemoryNode) -> float:
        """Calculate the decayed importance based on time and access history.
        
        Formula: CurrentImportance = BaseImportance * e^(-delta_t / S)
        Where delta_t is hours since last accessed.
        """
        now = datetime.now(timezone.utc)
        last_time = memory.last_accessed or memory.created_at
        
        # Calculate hours since last interaction
        delta_t = (now - last_time).total_seconds() / 3600.0
        
        # Decay formula (Ebbinghaus-inspired)
        # We also factor in importance_boost from reinforcement
        base = memory.importance + memory.importance_boost
        decay = math.exp(-delta_t / self.stability_factor)
        
        return max(0.0, min(1.0, base * decay))

    def determine_status(self, memory: MemoryNode, current_imp: float) -> MemoryStatus:
        """Determine the next lifecycle status based on current importance."""
        if current_imp < 0.05:
            return MemoryStatus.FORGOTTEN
        elif current_imp < 0.2:
            return MemoryStatus.ARCHIVED
        elif current_imp < 0.4:
            return MemoryStatus.COMPRESSED
        return MemoryStatus.ACTIVE

    async def process_batch(self, memories: List[MemoryNode]) -> List[MemoryNode]:
        """Process a batch of memories and update their importance/status."""
        updated = []
        for m in memories:
            new_imp = self.calculate_current_importance(m)
            new_status = self.determine_status(m, new_imp)
            
            # If status changed or importance significantly dropped, mark for update
            if new_status != m.status or abs(m.importance - new_imp) > 0.1:
                m.importance = new_imp
                m.status = new_status
                m.updated_at = datetime.now(timezone.utc)
                updated.append(m)
        return updated
