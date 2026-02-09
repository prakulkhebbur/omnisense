from typing import List
from src.models.call import Call
from .severity_scorer import SeverityScorer

class PriorityRanker:
    """Rank calls by priority for queue management"""
    
    def __init__(self):
        self.scorer = SeverityScorer()
    
    def rank_calls(self, calls: List[Call]) -> List[Call]:
        """Sort calls by severity (highest first)"""
        return sorted(calls, key=lambda c: c.severity_score, reverse=True)
    
    def calculate_and_update_call(self, call: Call) -> Call:
        """Calculate severity for a call and update its fields"""
        call.severity_score = self.scorer.calculate_severity(call)
        call.severity_level = self.scorer.get_severity_level(call.severity_score)
        return call

    def calculate_score(self, call: Call) -> int:
        """
        Calculate severity score (0-100).
        This method is required by the Orchestrator.
        """
        # Reuse existing logic
        self.calculate_and_update_call(call)
        return call.severity_score