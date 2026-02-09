import requests
import time
import threading
import json

BASE_URL = "http://localhost:8000"

# Color codes for terminal output
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RESET = '\033[0m'

def print_banner():
    print(f"{RED}================================================={RESET}")
    print(f"{RED}   🔥 OMNISENSE DISASTER SIMULATION STARTED 🔥   {RESET}")
    print(f"{RED}================================================={RESET}")

def simulate_caller(phone, messages, delay=0):
    """Simulates a single caller interaction"""
    time.sleep(delay)
    
    # 1. Create Call
    try:
        res = requests.post(f"{BASE_URL}/api/calls/create", json={"caller_phone": phone})
        call_data = res.json()
        call_id = call_data['call_id']
        print(f"📞 {CYAN}Incoming Call{RESET} from {phone} (ID: {call_data['call_number']})")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return

    # 2. Simulate Conversation
    for msg in messages:
        time.sleep(1.5) # Simulate typing/speaking time
        requests.post(f"{BASE_URL}/api/calls/{call_id}/message", json={"text": msg})

def run_simulation():
    print_banner()
    
    # SCENARIO: 
    # 1. Routine calls (Low Priority)
    # 2. MASS FIRE INCIDENT in Newtown (High Priority + Pattern)
    # 3. CARDIAC ARREST (Critical Priority - Should jump to #1)

    threads = []

    # --- GROUP 1: Routine Noise (Starts at T=0s) ---
    threads.append(threading.Thread(target=simulate_caller, args=("+1-555-0100", [
        "Hello, is the police station open?", 
        "I need to file a report for a lost wallet."
    ], 0)))
    
    threads.append(threading.Thread(target=simulate_caller, args=("+1-555-0101", [
        "My cat is stuck in a tree at Park Street.", 
        "It's been there for an hour."
    ], 1)))

    # --- GROUP 2: The Disaster (Mass Fire in Newtown) (Starts at T=3s) ---
    fire_msgs = ["HELP! Massive fire in Newtown!", "The apartment complex is burning!", "Sector 5 Newtown, send fire engines!"]
    
    for i in range(5):
        threads.append(threading.Thread(target=simulate_caller, args=(f"+1-555-020{i}", fire_msgs, 3 + (i*0.5))))

    # --- GROUP 3: The Critical Victim (Starts at T=6s) ---
    # This call comes in LATE but should jump to the TOP of the queue
    threads.append(threading.Thread(target=simulate_caller, args=("+1-555-0999", [
        "My father collapsed!", 
        "He is not breathing, I think it's a heart attack!", 
        "We are at 123 Lake Gardens."
    ], 6)))

    # Start all calls
    for t in threads:
        t.start()
    
    for t in threads:
        t.join()
    
    print(f"\n{YELLOW}⚡ All calls placed. Analyzing System State...{RESET}\n")
    time.sleep(2) # Wait for AI processing
    
    # Fetch Dashboard State
    state = requests.get(f"{BASE_URL}/api/state").json()
    
    # DISPLAY RESULTS
    print(f"{RED}--- 🚨 ACTIVE ALERTS ---{RESET}")
    for alert in state.get('alerts', []):
        print(f"⚠️  {alert}")
        
    print(f"\n{GREEN}--- 📋 PRIORITY QUEUE (Top 5) ---{RESET}")
    print(f"{'RANK':<5} | {'SEVERITY':<10} | {'TYPE':<20} | {'DETAILS'}")
    print("-" * 70)
    
    for i, call in enumerate(state['queue'][:5]):
        prio = call.get('priority_rank', i+1)
        score = call.get('severity_score', 0)
        etype = call.get('emergency_type', 'Unknown')
        loc = call.get('location', {}).get('address', 'Unknown')
        
        # Color code the output
        row_color = RED if score > 80 else (YELLOW if score > 50 else RESET)
        print(f"{row_color}#{prio:<4} | {score:<10} | {etype:<20} | {loc}{RESET}")

if __name__ == "__main__":
    run_simulation()