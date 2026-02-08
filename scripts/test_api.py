import requests
import time

BASE_URL = "http://localhost:8000"

def test_create_call():
    """Test creating a call"""
    print("\n🔹 Creating Call 1 (should go to operator)...")
    response = requests.post(
        f"{BASE_URL}/api/calls/create",
        json={"caller_phone": "+1-555-0001"}
    )
    call1 = response.json()
    print(f"✅ Call created: {call1}")
    
    time.sleep(2)
    
    print("\n🔹 Creating Call 2 (should go to AI)...")
    response = requests.post(
        f"{BASE_URL}/api/calls/create",
        json={"caller_phone": "+1-555-0002"}
    )
    call2 = response.json()
    print(f"✅ Call created: {call2}")
    
    # Simulate conversation for Call 2
    print(f"\n🔹 Simulating conversation for Call {call2['call_id']}...")
    
    # Message 1
    response = requests.post(
        f"{BASE_URL}/api/calls/{call2['call_id']}/message",
        json={"text": "Someone collapsed! Not breathing!"}
    )
    print(f"👤 Caller: Someone collapsed! Not breathing!")
    print(f"🤖 AI: {response.json()['ai_response']}")
    
    time.sleep(1)
    
    # Message 2
    response = requests.post(
        f"{BASE_URL}/api/calls/{call2['call_id']}/message",
        json={"text": "789 Elm Street, near the CVS"}
    )
    print(f"👤 Caller: 789 Elm Street, near the CVS")
    print(f"🤖 AI: {response.json()['ai_response']}")
    
    time.sleep(1)
    
    # Message 3
    response = requests.post(
        f"{BASE_URL}/api/calls/{call2['call_id']}/message",
        json={"text": "No, he's not breathing at all!"}
    )
    print(f"👤 Caller: No, he's not breathing at all!")
    print(f"🤖 AI: {response.json()['ai_response']}")
    print(f"📊 Call Status: {response.json()['call_status']}")
    
    # Get system state
    print("\n🔹 Getting system state...")
    response = requests.get(f"{BASE_URL}/api/state")
    state = response.json()
    
    print(f"\n📊 System State:")
    print(f"  Active Calls: {state['stats']['total_active']}")
    print(f"  AI Handled: {state['stats']['ai_handled']}")
    print(f"  Queued: {state['stats']['queued']}")
    
    print("\n📋 Queue:")
    for call in state['queue']:
        print(f"  - Call #{call['call_number']}: {call['emergency_type']} (Score: {call['severity_score']})")

if __name__ == "__main__":
    test_create_call()