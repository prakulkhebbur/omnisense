import asyncio
from triage_brain import analyze_call

async def run_test():
    print("--- TEST 1: First Call ---")
    # Simulate a caller with mild symptoms
    result1 = await analyze_call("555-0199", "I have a mild headache and I feel dizzy.")
    print(f"Result: {result1}") 
    # Likely ESI 4 or 3

    print("\n--- TEST 2: Same Caller, 2 Minutes Later ---")
    # Simulate the SAME caller calling back. 
    # Notice we don't say "headache" again, but the AI should remember it.
    result2 = await analyze_call("555-0199", "It's getting much worse, I can't see straight!")
    print(f"Result: {result2}")
    # Should be ESI 2 or 1 because 'dizzy' + 'vision loss' = Stroke Risk.

if __name__ == "__main__":
    asyncio.run(run_test())