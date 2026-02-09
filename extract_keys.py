import spacy
from spacy.matcher import PhraseMatcher
import requests
import json
from pydantic import BaseModel, Field
from typing import List, Optional

# --- 1. Define the Data Schema (The Contract) ---
class EmergencyIncident(BaseModel):
    summary: str = Field(..., description="Concise 1-sentence summary of the event.")
    category: str = Field(..., description="Category: Medical, Fire, Police, Traffic, or Other.")
    location: Optional[str] = Field(None, description="Extracted address or landmark.")
    casualty_count: int = Field(0, description="Estimated number of injured persons.")
    keywords: List[str] = Field(..., description="List of critical terms (e.g., 'gun', 'fire').")
    esi_score: int = Field(..., description="Emergency Severity Index from 1 (Most Urgent) to 5 (Least Urgent).")
    reasoning: str = Field(..., description="Why this ESI score was assigned.")

# --- 2. The Hybrid Analyzer Class ---
class TriageAnalyzer:
    def __init__(self):
        # Load Spacy for Fast Path
        self.nlp = spacy.load("en_core_web_sm")
        self.matcher = PhraseMatcher(self.nlp.vocab)
        
        # Seed Fast Path Keywords (Weighted)
        self.critical_terms = {
            "cardiac arrest": 1, "not breathing": 1, "unconscious": 1, 
            "gun": 2, "shooter": 2, "stabbing": 2,
            "fire": 2, "trapped": 2,
            "chest pain": 2, "stroke": 2,
            "broken": 3, "fracture": 3,
            "cut": 4, "bleeding": 3
        }
        patterns = [self.nlp.make_doc(text) for text in self.critical_terms.keys()]
        self.matcher.add("CRITICAL_TERMS", patterns)

    def analyze_fast(self, text: str):
        """
        Tier 1: Millisecond latency.
        Returns extracted keywords and a provisional priority based on a lookup.
        """
        doc = self.nlp(text.lower())
        matches = self.matcher(doc)
        
        detected_keywords =
        lowest_esi = 5 # Start with lowest priority
        
        for match_id, start, end in matches:
            span = doc[start:end]
            kw = span.text
            detected_keywords.append(kw)
            
            # Simple heuristic: Look up ESI map
            # In a real system, this map would be more complex
            if kw in self.critical_terms:
                implied_esi = self.critical_terms[kw]
                if implied_esi < lowest_esi:
                    lowest_esi = implied_esi
                    
        return {
            "keywords": list(set(detected_keywords)),
            "provisional_esi": lowest_esi
        }

    def analyze_deep(self, text: str):
        """
        Tier 2: Semantic Analysis using Local LLM (Ollama).
        Returns a structured Pydantic object.
        """
        # Construct a prompt that enforces the schema and ESI definitions
        prompt = f"""
        You are an expert 911 Dispatch Triage AI. Analyze this transcript:
        "{text}"
        
        Extract data into the requested JSON format.
        
        USE THESE DEFINITIONS FOR ESI SCORE:
        1: Resuscitation (Cardiac arrest, severe respiratory distress). Immediate.
        2: Emergent (Chest pain, stroke, high risk of deterioration). <10 mins.
        3: Urgent (Abdominal pain, fractures, stable vitals). <1 hour.
        4: Less Urgent (Laceration, minor burn).
        5: Non-Urgent (Prescription refill, toothache).
        
        Return ONLY valid JSON.
        """
        
        payload = {
            "model": "llama3", # "mistral" is also a good, faster option
            "prompt": prompt,
            "format": "json", # Forces valid JSON output
            "stream": False,
            "options": {
                "temperature": 0.0 # Deterministic output
            }
        }
        
        try:
            # Call Ollama API (No internet required)
            response = requests.post("http://localhost:11434/api/generate", json=payload)
            data = response.json()
            
            # Parse the JSON string from the LLM
            incident_data = EmergencyIncident.parse_raw(data['response'])
            return incident_data
            
        except Exception as e:
            print(f"LLM Error: {e}")
            return None

# --- Usage Example ---
# analyzer = TriageAnalyzer()
# text = "My father collapsed in the kitchen, he is not breathing! We are at 42 Maple Ave."
# 
# # 1. Fast Path (Instant feedback for UI)
# fast_result = analyzer.analyze_fast(text)
# print(f"Fast Flag: {fast_result}") 
# # Output: {'keywords': ['not breathing'], 'provisional_esi': 1}
# 
# # 2. Slow Path (Detailed record)
# deep_result = analyzer.analyze_deep(text)
# print(f"Deep Analysis: {deep_result.json()}")