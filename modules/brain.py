import os
import json
import time
import re
from google import genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Gemini client from environment variable
_api_key = os.getenv("GEMINI_API_KEY")
if not _api_key:
    raise EnvironmentError("GEMINI_API_KEY not set. Please add it to your .env file.")
client = genai.Client(api_key=_api_key)

# Model fallback chain — tries each in order if quota is hit or model unavailable.
# These are the models confirmed available via the google-genai SDK (v1beta).
# gemini-2.5-flash and gemini-2.0-flash-lite have separate quota buckets,
# so rotating between them often bypasses a single-model 429.
FALLBACK_MODELS = [
    "gemini-2.0-flash-lite",        # Lowest cost, try first
    "gemini-2.0-flash",             # Standard quota bucket
    "gemini-2.0-flash-001",         # Pinned version, separate bucket
    "gemini-2.5-flash",             # Newer generation, different quota pool
    "gemini-2.5-pro",               # Pro tier — highest chance of success
]


def _call_with_fallback(prompt: str) -> str:
    """
    Attempts to call the Gemini API using the FALLBACK_MODELS list.
    On a 429 (quota exhausted) or model error, waits accordingly and tries the next model.
    Raises a RuntimeError if every model fails.
    """
    last_error = None

    for model in FALLBACK_MODELS:
        try:
            print(f"   🤖 Trying model: {model}...")
            response = client.models.generate_content(model=model, contents=prompt)
            print(f"   ✅ Success with: {model}")
            return response.text.strip()

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                # Try to extract retryDelay from the error message (e.g. 'retryDelay': '23s')
                match = re.search(r"retryDelay\W{0,3}(\d+)", err_str)
                wait_sec = int(match.group(1)) if match else 5
                print(f"   ⚠️ Quota hit on {model} — waiting {wait_sec}s then trying next model...")
                time.sleep(wait_sec)
            elif "404" in err_str or "not found" in err_str.lower():
                print(f"   ⚠️ Model {model} not available — trying next...")
            else:
                print(f"   ⚠️ Error on {model}: {e} — trying next...")
            last_error = e

    raise RuntimeError(
        "\n❌ All Gemini models hit quota limits.\n"
        "This is a daily free-tier limit on your Google Cloud project.\n\n"
        "Fix options:\n"
        "  1. Wait until tomorrow (free quota resets daily at midnight Pacific)\n"
        "  2. Enable billing on your project for higher quotas:\n"
        "     https://console.cloud.google.com/billing\n"
        "  3. Create a new Google Cloud project and generate a fresh API key:\n"
        "     https://aistudio.google.com/app/apikey\n"
        f"  Last error: {last_error}"
    )


class ContentBrain:
    def get_trending_topic(self):
        """
        In a full build, this would scrape Google Trends or Twitter.
        For now, we ask Gemini to pick a viral niche topic.
        """
        prompt = (
            "Give me 1 specific, viral, and engaging topic for a Short Documentary. "
            "It should be an 'Engaging Did you know' fact or a 'Fun/intriguing Engaging News'. "
            "Return ONLY the topic name, nothing else."
        )
        topic = _call_with_fallback(prompt)
        print(f"🎯 Selected Topic: {topic}")
        return topic

    def generate_script(self, topic):
        """
        Generates a structured JSON script with visual cues.
        """
        print(f"📝 Writing script for: {topic}...")
        prompt = f"""
    You are the lead scriptwriter for a high-retention "Edutainment" YouTube Shorts channel.
    Topic: {topic}

    ### GOAL:
    Create a script where every sentence has a "Visual Switch". 
    To keep retention high, we need TWO different stock videos for every single scene.

    ### 1. SCRIPT REQUIREMENTS (The Voiceover):
    - **Perspective:** Strictly **3rd Person** ("Scientists found...", "The ocean hides...").
    - **Tone:** Engaging, fast-paced, logical. No fluff.
    - **Structure:** 8-9 Scenes total.
    - **Flow:** Hook -> Context -> Mechanism (How it works) -> Twist -> Outro.

    ### 2. VISUAL REQUIREMENTS (Dual Visuals):
    - For EVERY scene, provide TWO distinct search terms:
      - **visual_1:** Matches the *start* of the sentence.
      - **visual_2:** Matches the *end* of the sentence or provides a reaction/context.
    - **Strictly Literal:** If the text is "The economy crashed," do NOT search "sad man". Search "Stock market red chart".

    ### OUTPUT FORMAT (Strict JSON, no markdown, no extra text):
    [
        {{
            "id": 1,
            "text": "In 1995, fourteen wolves were released into Yellowstone Park, and they changed the rivers.",
            "visual_1": "wolves running snow aerial",
            "visual_2": "river flowing forest drone",
            "mood": "intriguing" 
        }},
        {{
            "id": 2,
            "text": "It sounds impossible, but the biology is actually simple math.",
            "visual_1": "person shocked looking at camera",
            "visual_2": "blackboard math equations chalk",
            "mood": "educational"
        }}
    ]
    """

        raw_text = _call_with_fallback(prompt)

        # Strip markdown code fences if the model wrapped the JSON
        clean_text = raw_text.replace('```json', '').replace('```', '').strip()

        try:
            script_data = json.loads(clean_text)
            return script_data
        except json.JSONDecodeError:
            print("❌ Error parsing JSON. Raw output:")
            print(clean_text)
            return None


# --- TESTING THE MODULE ---
if __name__ == "__main__":
    brain = ContentBrain()
    topic = brain.get_trending_topic()
    script = brain.generate_script(topic)

    with open("script.json", "w") as f:
        json.dump(script, f, indent=4)
        print("✅ Script saved to script.json")