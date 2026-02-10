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
            self.model = "llama-3.3-70b-versatile" 
            print(f"🤖 AI Agent connected to Groq Async ({self.model})")
        else:
            self.client = None
            print("⚠️ Groq Client not initialized (Check Key or Install)")

    def has_sufficient_info(self, call: Call) -> bool:
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

        # Attempt LLM-based classification of emergency type if model client available
        try:
            classified = await self.classify_emergency(call)
            if classified:
                call.emergency_type = classified
                # refresh summary if classification improved
                call.summary = self._generate_concise_summary(call)
        except Exception:
            pass

        return speech_text

    async def classify_emergency(self, call: Call):
        """Ask the LLM to choose the best EmergencyType token for this call.
        Returns an EmergencyType on success or None on failure.
        """
        if not self.client:
            return None

        # Build options from EmergencyType enum members
        try:
            options = ", ".join([k for k in EmergencyType.__members__.keys()])
        except Exception:
            options = "CARDIAC_ARREST, STROKE, SEVERE_TRAUMA, FIRE, RESCUE, MEDICAL_EMERGENCY, ACCIDENT, MINOR_INJURY, NON_EMERGENCY, UNKNOWN"

        # Compose prompt with brief context
        transcript_block = "\n".join([f"{m.role}: {m.text}" for m in call.transcript[-12:]])
        user_prompt = f"Given the following call transcript and summary, choose the single best emergency type from the list: {options}.\nRespond with exactly one of the tokens (no extra text).\n\nSUMMARY: {call.summary}\nTRANSCRIPT:\n{transcript_block}\n\nEMERGENCY_TYPE:"

        messages = [
            {"role": "system", "content": "You are a concise classifier that must reply with exactly one token from the provided list."},
            {"role": "user", "content": user_prompt}
        ]

        try:
            resp = await self.client.chat.completions.create(
                messages=messages,
                model=self.model,
                temperature=0.0,
                max_tokens=6,
            )
            text = resp.choices[0].message.content.strip()
            token = text.split()[0].strip().upper()

            # Map token to EmergencyType if valid
            if token in EmergencyType.__members__:
                return EmergencyType[token]

            # Try to match by value name
            token_low = token.lower()
            for name, member in EmergencyType.__members__.items():
                if member.value == token_low or member.value.replace('_', ' ') in token_low:
                    return EmergencyType[name]
        except Exception as e:
            print(f"LLM classification failed: {e}")

        return None

    async def _generate_groq_response(self, call: Call) -> str:
        memory_block = f"""
        CURRENT KNOWN STATUS (DO NOT ASK THESE AGAIN):
        - Emergency Type: {call.emergency_type.value if call.emergency_type else "Unknown"}
        - Location: {call.location.address if call.location else "Unknown"}
        - Caller ID: {call.caller.phone_number}
        """
        
        system_content = DISPATCHER_SYSTEM_PROMPT + "\n" + memory_block
        
        messages = [{"role": "system", "content": system_content}]
        
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
        """Generates a smart summary for the dashboard card."""
        loc = call.location.address if call.location and call.location.address else "Locating..."
        
        # Use a more descriptive string if we have specific details
        if call.emergency_type == EmergencyType.MEDICAL_EMERGENCY:
            return f"Medical emergency reported at {loc}."
        elif call.emergency_type == EmergencyType.FIRE:
            return f"Fire reported at {loc}."
        elif call.emergency_type == EmergencyType.RESCUE:
            return f"Rescue needed at {loc}."
        elif call.emergency_type == EmergencyType.CARDIAC_ARREST:
            return f"Critical cardiac event at {loc}."
        
        emer = call.emergency_type.value.replace("_", " ").title() if call.emergency_type else "Emergency"
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
        
        # --- FIX: Expanded Keyword Mapping ---
        if "cardiac" in data_lower or "arrest" in data_lower:
            call.emergency_type = EmergencyType.CARDIAC_ARREST
        elif "fire" in data_lower or "smoke" in data_lower:
            call.emergency_type = EmergencyType.FIRE
        elif any(w in data_lower for w in ["rescue", "stuck", "trapped", "stranded", "cat", "dog", "animal", "tree"]):
            # Animal/rescue scenarios mapped to RESCUE
            call.emergency_type = EmergencyType.RESCUE
        elif "accident" in data_lower or "crash" in data_lower:
            call.emergency_type = EmergencyType.ACCIDENT
        elif "trauma" in data_lower or "bleeding" in data_lower:
            call.emergency_type = EmergencyType.SEVERE_TRAUMA
        elif any(w in data_lower for w in ["medical", "injury", "broken", "fracture", "pain", "hurt"]):
            call.emergency_type = EmergencyType.MEDICAL_EMERGENCY
            
        # Extract Location
        loc_match = re.search(r"location:\s*(.+)", data_block, re.IGNORECASE)
        if loc_match:
            address = loc_match.group(1).strip()
            # Don't overwrite a good location with "Unknown"
            if address and "unknown" not in address.lower():
                if not call.location: call.location = Location()
                call.location.address = address

    def _extract_info_regex(self, text: str, call: Call):
        text_lower = text.lower()
        
        # --- FIX: Expanded Regex Keywords ---
        if any(w in text_lower for w in ["fire", "smoke", "flame"]):
            call.emergency_type = EmergencyType.FIRE
        elif any(w in text_lower for w in ["heart", "chest", "arrest", "stroke"]):
            call.emergency_type = EmergencyType.CARDIAC_ARREST
        elif any(w in text_lower for w in ["gun", "robber", "kill", "shoot"]):
            call.emergency_type = EmergencyType.CRIME
        elif any(w in text_lower for w in ["broken", "fracture", "bone", "leg", "arm", "ankle", "bleed", "injury", "hurt"]):
            call.emergency_type = EmergencyType.MEDICAL_EMERGENCY
        elif any(w in text_lower for w in ["cat", "dog", "animal", "stuck", "trapped", "rescue", "tree"]):
            # Animal rescue and stuck-in-tree scenarios
            call.emergency_type = EmergencyType.RESCUE
            
        known_zones = ["vit", "vellore", "newtown", "salt lake", "katpadi", "chittoor"]
        for zone in known_zones:
            if zone in text_lower:
                if not call.location: call.location = Location()
                # Basic extraction: take the string starting from the zone name
                try:
                    start_index = text_lower.find(zone)
                    # Extract up to the next punctuation or end of line
                    extract = text[start_index:].split('.')[0].strip()
                    call.location.address = extract.title()
                except:
                    call.location.address = zone.title()