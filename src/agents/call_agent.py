import os
import re
from typing import Optional
from src.models.call import Call, EmergencyType, Location, ExtractedInfo, VictimInfo
from src.agents.prompts import DISPATCHER_SYSTEM_PROMPT

try:
    from groq import AsyncGroq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

class AICallAgent:
    """
    AI Agent with Long-Term Context Injection & Summarization
    """
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        
        if GROQ_AVAILABLE and self.api_key:
            self.client = AsyncGroq(api_key=self.api_key)
            # Use the latest versatile model supported by Groq
            self.model = "llama-3.3-70b-versatile" 
            print(f"🤖 AI Agent connected to Groq Async ({self.model})")
        else:
            self.client = None
            print("⚠️ Groq Client not initialized (Check Key or Install)")

    def has_sufficient_info(self, call: Call) -> bool:
        """
        Checks if we have enough info to potentially queue the call
        or consider the triage phase 'complete'.
        """
        return (call.emergency_type != EmergencyType.UNKNOWN and 
                call.location is not None and 
                call.location.address is not None)

    async def handle_caller_message(self, call: Call, caller_text: str) -> str:
        # 1. Update Transcript
        call.add_transcript_message("caller", caller_text)
        
        # 2. Extract Info (Regex Backup)
        self._extract_info_regex(caller_text, call)

        # 3. Generate AI Response
        if self.client:
            full_response = await self._generate_groq_response(call)
        else:
            full_response = "I am operating in fallback mode. Please state your emergency."
        
        # 4. Parse Output (Separate Speech from Data)
        speech_text, extracted_data = self._parse_llm_output(full_response)
        
        # 5. Update Call with LLM Data
        if extracted_data:
            self._update_call_from_llm(call, extracted_data)
            
        # 6. Update Concise Summary (For Dashboard)
        call.summary = self._generate_concise_summary(call)

        call.add_transcript_message("ai", speech_text)
        return speech_text

    async def _generate_groq_response(self, call: Call) -> str:
        # Inject Memory into System Prompt
        memory_block = f"""
        CURRENT KNOWN STATUS (DO NOT ASK THESE AGAIN):
        - Emergency Type: {call.emergency_type.value if call.emergency_type else "Unknown"}
        - Location: {call.location.address if call.location else "Unknown"}
        - Caller ID: {call.caller.phone_number}
        """
        
        system_content = DISPATCHER_SYSTEM_PROMPT + "\n" + memory_block
        
        messages = [{"role": "system", "content": system_content}]
        
        # Add last 10 messages for context
        for msg in call.transcript[-10:]:
            role = "user" if msg.role == "caller" else "assistant"
            content = msg.text 
            messages.append({"role": role, "content": content})

        try:
            chat_completion = await self.client.chat.completions.create(
                messages=messages,
                model=self.model,
                temperature=0.3,
                max_tokens=200, 
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"❌ Groq AI Error: {e}")
            return "Help is on the way. Stay on the line."

    def _generate_concise_summary(self, call: Call) -> str:
        """Generates a 1-line summary for the dashboard card."""
        loc = call.location.address if call.location and call.location.address else "Unknown Loc"
        emer = call.emergency_type.value if call.emergency_type else "Emergency"
        return f"{emer} at {loc}. Active call."

    def _parse_llm_output(self, full_text: str):
        if "EXTRACTED_INFO:" in full_text:
            parts = full_text.split("EXTRACTED_INFO:")
            speech = parts[0].strip()
            data_block = parts[1].strip()
            return speech, data_block
        return full_text.strip(), None

    def _update_call_from_llm(self, call: Call, data_block: str):
        data_lower = data_block.lower()
        if "cardiac" in data_lower or "arrest" in data_lower:
            call.emergency_type = EmergencyType.CARDIAC_ARREST
        elif "fire" in data_lower:
            call.emergency_type = EmergencyType.FIRE
        elif "accident" in data_lower or "trauma" in data_lower:
            call.emergency_type = EmergencyType.SEVERE_TRAUMA
        
        loc_match = re.search(r"location:\s*(.+)", data_block, re.IGNORECASE)
        if loc_match:
            address = loc_match.group(1).strip()
            if address and address.lower() != "unknown":
                if not call.location: call.location = Location()
                call.location.address = address

    def _extract_info_regex(self, text: str, call: Call):
        text_lower = text.lower()
        if any(w in text_lower for w in ["fire", "smoke"]):
            call.emergency_type = EmergencyType.FIRE
        elif any(w in text_lower for w in ["heart", "chest", "pain", "arrest"]):
            call.emergency_type = EmergencyType.CARDIAC_ARREST
        elif any(w in text_lower for w in ["gun", "robber", "kill"]):
            call.emergency_type = EmergencyType.CRIME
            
        known_zones = ["vit", "vellore", "newtown", "salt lake"]
        for zone in known_zones:
            if zone in text_lower:
                if not call.location: call.location = Location()
                try:
                    call.location.address = text[text_lower.find(zone):].split('.')[0].title()
                except:
                    call.location.address = zone.title()