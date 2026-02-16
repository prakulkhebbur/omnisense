import os
import json
import asyncio
from backboard import BackboardClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Client
client = BackboardClient(api_key=os.getenv("BACKBOARD_API_KEY"))

# In-Memory Database for Hackathon (Phone -> ThreadID)
PHONE_TO_THREAD = {}
ASSISTANT_ID = None

async def get_triage_assistant():
    """
    Creates the AI Assistant.
    """
    global ASSISTANT_ID
    if ASSISTANT_ID:
        return ASSISTANT_ID

    print("🚑 Creating Omni-Sense Assistant...")
    
    # Create the Assistant
    # Note: We do NOT pass model here. We pass it in add_message.
    assistant = await client.create_assistant(
        name="Omni-Sense Triage",
        system_prompt="""
        You are an Emergency Triage AI.
        1. Analyze the transcript for: Emergency Type, Severity, and Location.
        2. Assign an ESI Level (1=Critical/Dying, 5=Non-Urgent).
        3. MEMORY CHECK: If this caller has called before with worsening symptoms, UPGRADE the priority.
        4. CRITICAL INSTRUCTION: Output ONLY valid JSON. Do not use Markdown (```). Do not write intro text.
        5. Format: {"esi": int, "summary": "str", "location": "str", "risk_factors": [str]}
        """
    )
    
    ASSISTANT_ID = assistant.assistant_id
    print(f"✅ Assistant Created: {ASSISTANT_ID}")
    return ASSISTANT_ID

async def get_thread(phone_number, assistant_id):
    """
    Gets or creates a conversation thread for a specific phone number.
    """
    if phone_number in PHONE_TO_THREAD:
        return PHONE_TO_THREAD[phone_number]
    
    # Create new thread
    thread = await client.create_thread(assistant_id)
    PHONE_TO_THREAD[phone_number] = thread.thread_id
    return thread.thread_id

async def analyze_call(phone_number, transcript_text):
    """
    Main function to analyze the call.
    """
    try:
        aid = await get_triage_assistant()
        tid = await get_thread(phone_number, aid)
        
        # DEBUG: Print what we are sending
        # print(f"Sending to Thread {tid}: {transcript_text}")

        # Send Message with Explicit Model Parameters
        response = await client.add_message(
            thread_id=tid,
            content=transcript_text,
            llm_provider="openai",  # <--- FIXED: Explicitly set provider
            model_name="gpt-4o",    # <--- FIXED: Explicitly set model
            memory="Auto",          # Enables the Long-Term Memory
            stream=False
        )
        
        # DEBUG: Print the raw response to catch errors
        raw_content = response.content
        # print(f"DEBUG RAW AI RESPONSE: {raw_content}") 

        if not raw_content:
            return {"esi": 3, "summary": "Error: Empty Response from AI", "location": "Unknown"}

        # Clean Markdown if present
        clean_json = raw_content.replace("```json", "").replace("```", "").strip()
        
        return json.loads(clean_json)

    except json.JSONDecodeError:
        print(f"❌ JSON Parse Error. Raw Output was: {raw_content}")
        return {"esi": 3, "summary": "Parse Error", "location": "Unknown"}
    except Exception as e:
        print(f"❌ System Error: {e}")
        return {"esi": 3, "summary": "System Error", "location": "Unknown"}