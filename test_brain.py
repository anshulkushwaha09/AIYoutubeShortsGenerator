import sys
import os
import json
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.getcwd())

from modules.brain import ContentBrain

load_dotenv()

def test_script_generation():
    brain = ContentBrain()
    
    # Simulate getting a topic
    topic = "The feeling of a quiet library"
    
    print(f"Generating scenario for: {topic}")
    scenario = brain.get_specific_scenario("nostalgic", topic)
    
    print(f"Generating script for: {topic}")
    script = brain.generate_script(topic, scenario)
    
    print("\n--- GENERATED SCRIPT ---")
    print(json.dumps(script, indent=2))
    
    # Check for simple english and satisfied feeling
    # The brain.py prompt shows 'narration_text' within segments.
    text = " ".join([s.get("narration_text", "") for s in script.get("segments", [])])
    print("\n--- FULL TEXT ---")
    print(text)

if __name__ == "__main__":
    test_script_generation()
