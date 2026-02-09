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
        
        # --- 1. Extract Emergency Type ---
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
        
        # Fire (Expanded keywords)
        elif any(word in text_lower for word in ["fire", "smoke", "burning", "flames", "explosion", "gas leak"]):
            call.emergency_type = EmergencyType.FIRE
            call.extracted_info.severity_indicators.append("fire")
        
        # Minor injury
        elif any(word in text_lower for word in ["cut finger", "sprained", "twisted ankle", "minor burn", "small cut"]):
            call.emergency_type = EmergencyType.MINOR_INJURY
        
        # Medical emergency (general)
        elif any(word in text_lower for word in ["sick", "pain", "hurts", "emergency", "help"]):
            call.emergency_type = EmergencyType.MEDICAL_EMERGENCY
        
        # --- 2. Extract Location ---
        # A. Look for formal addresses (Numbers + Street names)
        address_pattern = r'\d+\s+[A-Za-z\s]+(street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|way|court|ct)'
        address_match = re.search(address_pattern, text, re.IGNORECASE)
        
        found_address = None
        if address_match:
            found_address = address_match.group(0)
        
        # B. Fallback: Look for known zones/areas (Crucial for Pattern Detection Demo)
        if not found_address:
            # Add any locations you use in your simulation scripts here
            known_zones = ["newtown", "salt lake", "park street", "sector 5", "lake gardens", "ballygunge"]
            for zone in known_zones:
                if zone in text_lower:
                    found_address = zone.title() # Capitalize it (e.g. "Newtown")
                    break
        
        # Update Call Object if location found
        if found_address:
            if not call.location:
                call.location = Location()
            # Only update if we found something longer/more specific or if currently empty
            if not call.location.address or len(found_address) > len(call.location.address):
                call.location.address = found_address

        # --- 3. Extract Victim Status ---
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
        
        # Lower threshold for demo: if we have loc + type, we queue it
        return has_location and has_emergency_type
    
    async def handle_caller_message(self, call: Call, caller_text: str) -> str:
        """
        Process caller's message and generate AI response
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