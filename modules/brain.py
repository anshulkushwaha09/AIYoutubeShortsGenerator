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
    # Vast niche pool — 52 categories to ensure topics never repeat for years
    NICHES = [
        # Science & Nature
        "space exploration & astronomy",
        "ocean deep-sea mysteries",
        "quantum physics & weird science",
        "human body & medical science",
        "bizarre animal behaviour",
        "plant biology & nature secrets",
        "genetics & DNA discoveries",
        "climate & environmental science",
        "chemistry & chemical reactions",
        "extreme weather & natural disasters",
        "geology & earth mysteries",
        "microbiology & invisible worlds",

        # History & Civilizations
        "ancient civilizations & history",
        "unsolved historical mysteries",
        "military history & strategy",
        "lost cities & archaeological finds",
        "the history of money & economics",
        "secret societies & hidden history",
        "the history of medicine",
        "world war facts & untold stories",
        "empires that vanished",

        # Technology & Future
        "cutting-edge AI & robotics",
        "future technology & inventions",
        "cybersecurity & hacking stories",
        "space technology & Mars missions",
        "biotechnology & genetic engineering",
        "the history & evolution of the internet",
        "electric vehicles & energy revolution",
        "surveillance technology & privacy",

        # Human Mind & Society
        "psychology & mind tricks",
        "viral social experiments",
        "languages & communication",
        "philosophy & thought experiments",
        "cults, propaganda & mass manipulation",
        "neuroscience & the brain",
        "sociology & human behaviour",
        "sleep, dreams & consciousness",

        # Business, Money & Power
        "economics & money secrets",
        "corporate scandals & frauds",
        "record-breaking entrepreneurs",
        "the dark side of big companies",
        "cryptocurrency & blockchain",
        "the world's most powerful families",

        # Culture & Miscellaneous
        "food science & nutrition facts",
        "geography & hidden places",
        "record-breaking engineering feats",
        "crime & true heist stories",
        "sports science & athletic records",
        "art heists & cultural crimes",
        "the science of music & sound",
        "mythology & ancient legends",
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
    - **Structure:** 9-10 Scenes total.
    - **Flow:** Hook -> Context -> Mechanism (How it works) -> Twist -> Outro -> Call to Action.
    - **MANDATORY FINAL SCENE:** The very last scene MUST be "Like and subscribe for more fun facts!" or similar.

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

    def generate_description(self, topic: str, script_data: list) -> str:
        """
        Generates a unique, dynamic YouTube description for each Short.

        Uses the actual script scenes so the description references real facts
        from the video — not a generic template.
        Falls back to a safe default if the API call fails.
        """
        print("✍️  Generating video description...")

        # Extract scene text to give Gemini real content to work with
        scene_texts = " | ".join(
            scene.get("text", "") for scene in (script_data or [])[:5]
        )

        prompt = (
            f"You are writing a YouTube Short description for a video about: \"{topic}\"\n\n"
            f"The video covers these key points:\n{scene_texts}\n\n"
            f"Write a YouTube description following this EXACT format (no extra text):\n\n"
            f"Line 1: A single hook emoji + the topic as a punchy 1-line opener\n"
            f"Line 2: (blank)\n"
            f"Lines 3-4: A 2-sentence teaser that references a specific surprising fact "
            f"from the video WITHOUT giving away the ending. Make it curiosity-driven.\n"
            f"Line 5: (blank)\n"
            f"Line 6: ━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Line 7: 🔔 Subscribe for daily mind-blowing facts!\n"
            f"Line 8: (blank)\n"
            f"Line 9: ━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Line 10: 10 relevant hashtags starting with #Shorts\n"
            f"Line 11: (blank)\n"
            f"Line 12: 🔔 Like and Subscribe for daily amazing facts! 🚀"
        )

        try:
            description = _call_with_fallback(prompt)
            return description.strip()
        except Exception as e:
            print(f"   ⚠️ Description generation failed ({e}), using default.")
            # Safe fallback — still better than nothing
            return (
                f"🤯 {topic}\n\n"
                f"What if everything you thought you knew was wrong? "
                f"This Short uncovers a surprising truth that most people never learn.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔔 Subscribe for daily mind-blowing facts!\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"#Shorts #DidYouKnow #Facts #Science #MindBlowing "
                f"#Educational #Viral #FunFacts #Amazing #LearnSomethingNew"
            )


# --- TESTING THE MODULE ---
if __name__ == "__main__":
    brain = ContentBrain()
    topic = brain.get_trending_topic()
    script = brain.generate_script(topic)
    desc   = brain.generate_description(topic, script)
    print("\n📋 Description preview:\n")
    print(desc)

    with open("script.json", "w") as f:
        json.dump(script, f, indent=4)
        print("\n✅ Script saved to script.json")