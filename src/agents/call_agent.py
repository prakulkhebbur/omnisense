import re
from typing import Optional, Dict, List
from src.models.call import Call, ExtractedInfo, Location, VictimInfo
from src.models.enums import EmergencyType
from .prompts import DISPATCHER_SYSTEM_PROMPT, FOLLOW_UP_PROMPTS

class AICallAgent:
    """
    AI agent for handling emergency calls
    FREE VERSION: Uses simple rule-based extraction
    Can be upgraded to use local Ollama or free GPT-4o-mini API
    """
    
    def __init__(self):
        self.conversation_state = {}
        self.required_info = ["location", "emergency_type", "victim_status"]
    
    def get_next_question(self, call: Call) -> str:
        """
        Determine next question based on conversation state
        Simple rule-based system (FREE)
        """
        # First message
        if len(call.transcript) == 0:
            return "911, what's your emergency?"
        
        # Check what info we have
        has_location = call.location is not None and call.location.address
        has_emergency_type = call.emergency_type != EmergencyType.UNKNOWN
        has_victim_status = call.victim_info is not None
        
        # Ask for missing critical info
        if not has_emergency_type:
            return "What is the emergency? What happened?"
        
        if not has_location:
            return "What is your exact location?"
        
        if not has_victim_status:
            return "Is the person conscious and breathing?"
        
        # We have enough info
        return "Help is on the way. Stay calm and stay on the line."
    
    def extract_info_from_text(self, text: str, call: Call) -> None:
        """
        Extract emergency info from caller's text using simple patterns
        FREE VERSION: Rule-based extraction
        """
        text_lower = text.lower()
        
        # Extract emergency type
        if not call.extracted_info:
            call.extracted_info = ExtractedInfo()
        
        # Cardiac/Heart issues
        if any(word in text_lower for word in ["heart attack", "chest pain", "cardiac", "collapsed", "not breathing"]):
            call.emergency_type = EmergencyType.CARDIAC_ARREST
            if "not breathing" in text_lower or "stopped breathing" in text_lower:
                call.extracted_info.severity_indicators.append("not_breathing")
            if "unconscious" in text_lower or "not moving" in text_lower or "collapsed" in text_lower:
                call.extracted_info.severity_indicators.append("unconscious")
        
        # Stroke
        elif any(word in text_lower for word in ["stroke", "can't move", "face drooping", "slurred speech"]):
            call.emergency_type = EmergencyType.STROKE
            call.extracted_info.severity_indicators.append("stroke_symptoms")
        
        # Severe trauma
        elif any(word in text_lower for word in ["bleeding heavily", "severe bleeding", "head injury", "car accident", "fell from"]):
            call.emergency_type = EmergencyType.SEVERE_TRAUMA
            if "bleeding" in text_lower:
                call.extracted_info.severity_indicators.append("bleeding")
            if "head" in text_lower:
                call.extracted_info.severity_indicators.append("head_injury")
        
        # Fire
        elif any(word in text_lower for word in ["fire", "smoke", "burning", "flames"]):
            call.emergency_type = EmergencyType.FIRE
            call.extracted_info.severity_indicators.append("fire")
        
        # Minor injury
        elif any(word in text_lower for word in ["cut finger", "sprained", "twisted ankle", "minor burn", "small cut"]):
            call.emergency_type = EmergencyType.MINOR_INJURY
        
        # Medical emergency (general)
        elif any(word in text_lower for word in ["sick", "pain", "hurts", "emergency", "help"]):
            call.emergency_type = EmergencyType.MEDICAL_EMERGENCY
        
        # Extract location using patterns
        # Look for address patterns (numbers + street names)
        address_pattern = r'\d+\s+[A-Za-z\s]+(street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|way|court|ct)'
        address_match = re.search(address_pattern, text, re.IGNORECASE)
        if address_match:
            if not call.location:
                call.location = Location()
            call.location.address = address_match.group(0)
        
        # Extract victim status
        if "conscious" in text_lower:
            if not call.victim_info:
                call.victim_info = VictimInfo()
            call.victim_info.conscious = "not conscious" not in text_lower and "unconscious" not in text_lower
        
        if "breathing" in text_lower:
            if not call.victim_info:
                call.victim_info = VictimInfo()
            call.victim_info.breathing = "not breathing" not in text_lower and "stopped breathing" not in text_lower
    
    def has_sufficient_info(self, call: Call) -> bool:
        """Check if we have enough info to queue the call"""
        has_location = call.location is not None and call.location.address
        has_emergency_type = call.emergency_type != EmergencyType.UNKNOWN
        has_basic_status = len(call.transcript) >= 4  # At least 2 exchanges
        
        return has_location and has_emergency_type and has_basic_status
    
    async def handle_caller_message(self, call: Call, caller_text: str) -> str:
        """
        Process caller's message and generate AI response
        
        Args:
            call: Current call object
            caller_text: What the caller said
            
        Returns:
            AI's response text
        """
        # Add caller message to transcript
        call.add_transcript_message("caller", caller_text)
        
        # Extract info from caller's text
        self.extract_info_from_text(caller_text, call)
        
        # Generate next question
        ai_response = self.get_next_question(call)
        
        # Add AI response to transcript
        call.add_transcript_message("ai", ai_response)
        
        return ai_response