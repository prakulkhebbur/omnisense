from typing import Dict
from src.models.call import Call
from src.models.enums import EmergencyType, SeverityLevel

class SeverityScorer:
    """Calculate severity scores for emergency calls"""
    
    # Base scores for each emergency type
    EMERGENCY_WEIGHTS: Dict[EmergencyType, int] = {
        EmergencyType.CARDIAC_ARREST: 100,
        EmergencyType.STROKE: 95,
        EmergencyType.SEVERE_TRAUMA: 85,
        EmergencyType.FIRE: 80,
        EmergencyType.MEDICAL_EMERGENCY: 60,
        EmergencyType.ACCIDENT: 50,
        EmergencyType.MINOR_INJURY: 20,
        EmergencyType.NON_EMERGENCY: 10,
        EmergencyType.UNKNOWN: 40
    }
    
    # Severity indicator modifiers
    SEVERITY_MODIFIERS = {
        "unconscious": 20,
        "not_breathing": 25,
        "bleeding": 15,
        "chest_pain": 15,
        "severe_pain": 10,
        "child": 10,
        "elderly": 5,
        "pregnant": 10,
        "seizure": 15,
        "fall": 8,
        "head_injury": 12,
        "difficulty_breathing": 18,
        "choking": 20,
        "overdose": 18,
        "burn": 12,
        "broken_bone": 8,
        "public_location": 5,
        "multiple_victims": 15
    }
    
    def calculate_severity(self, call: Call) -> int:
        """
        Calculate severity score (0-100)
        
        Args:
            call: Call object with emergency details
            
        Returns:
            Severity score from 0-100
        """
        # Start with base score from emergency type
        base_score = self.EMERGENCY_WEIGHTS.get(call.emergency_type, 40)
        
        # Add modifiers from severity indicators
        modifier_score = 0
        if call.extracted_info and call.extracted_info.severity_indicators:
            for indicator in call.extracted_info.severity_indicators:
                indicator_lower = indicator.lower().replace(" ", "_")
                modifier_score += self.SEVERITY_MODIFIERS.get(indicator_lower, 0)
        
        # Check victim status
        if call.victim_info:
            if call.victim_info.conscious is False:
                modifier_score += 20
            if call.victim_info.breathing is False:
                modifier_score += 25
            if call.victim_info.age and call.victim_info.age < 12:
                modifier_score += 10
            if call.victim_info.age and call.victim_info.age > 65:
                modifier_score += 5
        
        # Calculate final score (capped at 100)
        final_score = min(base_score + modifier_score, 100)
        
        return final_score
    
    def get_severity_level(self, score: int) -> SeverityLevel:
        """Convert numeric score to severity level"""
        if score >= 80:
            return SeverityLevel.CRITICAL
        elif score >= 60:
            return SeverityLevel.HIGH
        elif score >= 40:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW