import os
import json
import time
import re
import random
from datetime import datetime
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
    # Broad niche pool — a random one is picked each run to force variety
    NICHES = [
        "space exploration & astronomy", "ocean deep-sea mysteries",
        "ancient civilizations & history", "cutting-edge AI & robotics",
        "extreme weather & natural disasters", "bizarre animal behaviour",
        "unsolved historical mysteries", "human body & medical science",
        "future technology & inventions", "psychology & mind tricks",
        "economics & money secrets", "military history & strategy",
        "geography & hidden places", "food science & nutrition facts",
        "crime & true stories", "record-breaking engineering",
        "viral social experiments", "environmental science",
        "sports science & records", "languages & communication",
    ]

    HISTORY_FILE = "topic_history.json"
    HISTORY_LIMIT = 30  # Remember last N topics to avoid repeats

    def _load_history(self) -> list:
        if os.path.exists(self.HISTORY_FILE):
            try:
                with open(self.HISTORY_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_history(self, history: list):
        try:
            with open(self.HISTORY_FILE, "w") as f:
                json.dump(history[-self.HISTORY_LIMIT:], f, indent=2)
        except Exception:
            pass

    def get_trending_topic(self):
        """
        Picks a unique topic every run by injecting:
          - Today's date + current hour  (breaks Gemini's cache)
          - A randomly chosen niche      (forces category variety)
          - Recent topic history         (explicit avoidance list)
        """
        niche    = random.choice(self.NICHES)
        now      = datetime.utcnow()
        date_str = now.strftime("%Y-%m-%d")
        hour_str = now.strftime("%H:%M UTC")
        history  = self._load_history()

        avoid_block = ""
        if history:
            avoid_list = "\n".join(f"  - {t}" for t in history[-10:])
            avoid_block = (
                f"\n\nIMPORTANT — You MUST pick something NEW. "
                f"Do NOT suggest any of these recently used topics:\n{avoid_list}"
            )

        prompt = (
            f"Today is {date_str} at {hour_str}. "
            f"Give me 1 specific, viral, and highly engaging topic for a YouTube Short documentary "
            f"in the niche: **{niche}**. "
            f"It must be a surprising 'Did You Know' fact, an incredible true story, or a mind-blowing "
            f"recent discovery. Be very specific — not generic. "
            f"Return ONLY the topic name, nothing else."
            f"{avoid_block}"
        )

        topic = _call_with_fallback(prompt)
        print(f"🎯 Topic ({niche}): {topic}")

        # Save to history so next run avoids it
        history.append(topic)
        self._save_history(history)

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