import os
from typing import Optional
from src.models.call import Call, EmergencyType, Location, ExtractedInfo, VictimInfo
from src.agents.prompts import DISPATCHER_SYSTEM_PROMPT

# Try importing Groq
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

class AICallAgent:
    """
    AI Agent powered by Groq (Llama 3)
    """
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        
        if GROQ_AVAILABLE and self.api_key:
            self.client = Groq(api_key=self.api_key)
            # "llama3-8b-8192" is the fastest model on Groq
            self.model = "llama3-8b-8192" 
            print(f"🤖 AI Agent connected to Groq ({self.model})")
        else:
            self.client = None
            print("⚠️ Groq Client not initialized (Check Key or Install)")

    def has_sufficient_info(self, call: Call) -> bool:
        """Check if we have type and location"""
        return (call.emergency_type != EmergencyType.UNKNOWN and 
                call.location is not None and 
                call.location.address is not None)

    async def handle_caller_message(self, call: Call, caller_text: str) -> str:
        # 1. Add User Message
        call.add_transcript_message("caller", caller_text)
        
        # 2. Fast Regex Extraction (Updates Dashboard instantly)
        self._extract_info_regex(caller_text, call)

        # 3. Generate AI Response via Groq
        if self.client:
            response_text = await self._generate_groq_response(call)
        else:
            response_text = "I am operating in fallback mode. Please state your emergency."
        
        call.add_transcript_message("ai", response_text)
        return response_text

    async def _generate_groq_response(self, call: Call) -> str:
        messages = [{"role": "system", "content": DISPATCHER_SYSTEM_PROMPT}]
        
        # Add limited history
        for msg in call.transcript[-6:]:
            role = "user" if msg.sender == "caller" else "assistant"
            messages.append({"role": role, "content": msg.content})

        try:
            # We use synchronous client wrapped in async function if needed,
            # but Groq client is fast enough to run direct or ideally in thread.
            # For simplicity in this structure:
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.model,
                temperature=0.3,
                max_tokens=80, # Keep short for voice
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"Groq LLM Error: {e}")
            return "Help is on the way. Stay on the line."

    def _extract_info_regex(self, text: str, call: Call):
        """
        Backup extraction ensures the Dashboard lights up 
        even if the LLM is taking a moment (though Groq is instant).
        """
        text_lower = text.lower()
        
        if any(w in text_lower for w in ["fire", "smoke"]):
            call.emergency_type = EmergencyType.FIRE
        elif any(w in text_lower for w in ["heart", "chest", "pain"]):
            call.emergency_type = EmergencyType.CARDIAC_ARREST
        elif any(w in text_lower for w in ["gun", "robber", "kill"]):
            call.emergency_type = EmergencyType.CRIME
            
        # Demo Locations
        known_zones = ["newtown", "salt lake", "park street"]
        for zone in known_zones:
            if zone in text_lower:
                if not call.location: call.location = Location()
                call.location.address = zone.title()