from typing import List, Dict, Optional
from src.models.call import Call
from src.ranking.priority_ranker import PriorityRanker

class QueueManager:
    """Manage the priority queue of calls"""
    
    def __init__(self):
        self.queue: List[str] = []  # List of call IDs
        self.ranker = PriorityRanker()
    
    def add_to_queue(self, call_id: str):
        """Add call to queue"""
        if call_id not in self.queue:
            self.queue.append(call_id)
    
    def remove_from_queue(self, call_id: str):
        """Remove call from queue"""
        if call_id in self.queue:
            self.queue.remove(call_id)
    
    def rerank_queue(self, active_calls: Dict[str, Call]):
        """
        Re-rank all calls in queue by severity
        
        Args:
            active_calls: Dictionary of all active calls {call_id: Call}
        """
        # Get all queued calls
        queued_calls = [active_calls[cid] for cid in self.queue if cid in active_calls]
        
        # Sort by severity
        ranked_calls = self.ranker.rank_calls(queued_calls)
        
        # Update queue order
        self.queue = [c.id for c in ranked_calls]
        
        # Update priority_rank field on each call
        for idx, call_id in enumerate(self.queue):
            if call_id in active_calls:
                active_calls[call_id].priority_rank = idx + 1
    
    def get_next_call(self) -> Optional[str]:
        """Get highest priority call from queue"""
        if self.queue:
            return self.queue[0]
        return None
    
    def get_queue_size(self) -> int:
        """Get number of calls in queue"""
        return len(self.queue)