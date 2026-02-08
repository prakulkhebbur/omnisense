from typing import List
from src.models.call import Call
from .severity_scorer import SeverityScorer

class PriorityRanker:
    """Rank calls by priority for queue management"""
    
    def __init__(self):
        self.scorer = SeverityScorer()
    
    def rank_calls(self, calls: List[Call]) -> List[Call]:
        """
        Sort calls by severity (highest first)
        
        Args:
            calls: List of Call objects
            
        Returns:
            Sorted list with highest severity first
        """
        return sorted(calls, key=lambda c: c.severity_score, reverse=True)
    
    def calculate_and_update_call(self, call: Call) -> Call:
        """
        Calculate severity for a call and update its fields
        
        Args:
            call: Call object
            
        Returns:
            Updated call with severity score and level
        """
        # Calculate severity score
        call.severity_score = self.scorer.calculate_severity(call)
        
        # Determine severity level
        call.severity_level = self.scorer.get_severity_level(call.severity_score)
        
        return call