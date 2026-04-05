import os
import json
import time
import re
import random
from datetime import datetime
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Gemini clients from multiple potential environment variables
# Supports: GEMINI_API_KEY, GEMINI_API_KEY_1, GEMINI_API_KEY_2, etc.
def _initialize_clients():
    keys = []
    # Check for the primary key
    primary = os.getenv("GEMINI_API_KEY")
    if primary:
        keys.append(primary)
    
    # Check for numbered keys (up to 10)
    for i in range(1, 11):
        key = os.getenv(f"GEMINI_API_KEY_{i}")
        if key and key not in keys:
            keys.append(key)
    
    if not keys:
        raise EnvironmentError(
            "No Gemini API keys found. Please add GEMINI_API_KEY_1, etc., to your .env file."
        )
    
    print(f"📡 Found {len(keys)} Gemini API keys for rotation.")
    return [genai.Client(api_key=k) for k in keys]

clients = _initialize_clients()

# Model fallback chain
FALLBACK_MODELS = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]

def _call_with_fallback(prompt: str) -> str:
    """
    Attempts to call Gemini using a double-layered fallback:
    1. Tries all models on Client 1
    2. If all fail, switches to Client 2 and tries all models again
    3. Repeats until a success or all (Keys x Models) are exhausted.
    """
    last_error = None

    for i, client_inst in enumerate(clients):
        print(f"   🔑 Using API Key #{i+1}...")
        for model in FALLBACK_MODELS:
            try:
                print(f"      🤖 Trying model: {model}...")
                response = client_inst.models.generate_content(model=model, contents=prompt)
                return response.text.strip()

            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    print(f"      ⚠️ Quota hit on {model} (Key #{i+1})")
                elif "404" in err_str or "not found" in err_str.lower():
                    print(f"      ⚠️ Model {model} unavailable.")
                else:
                    print(f"      ⚠️ Error on {model}: {e}")
                last_error = e

    raise RuntimeError(
        f"❌ All {len(clients)} API keys and all models hit quota limits.\n"
        f"Last error: {last_error}"
    )


class ContentBrain:
    # Expanded niches for long-term variety (Viral Storyteller)
    NICHES = [
        "that feeling you can't explain",
        "small moments that change everything",
        "why we do the things we do",
        "the secret thoughts we all share",
        "finding peace in small things",
        "the beauty of being misunderstood",
        "why some memories never fade",
        "the strange magic of daily life",
        "overcoming the things that scare us",
        "what it means to really be home",
        "the struggle of being human",
        "moments that make you feel alive",
        "the comfort of a rainy afternoon",
        "why we stare at the ocean",
        "the feeling of a handwritten note",
        "the quiet before the city wakes up",
        "the strange sadness of finishing a book",
        "why we love the sound of a crackling fire",
        "the feeling of being understood without a word",
        "why we look back at old photos",
        "the relief of a long-awaited 'I'm home' text",
        "the magic of a sudden, deep conversation",
        "the beauty of a worn-out object",
        "why we find peace in a messy desk",
        "the feeling of a first cool breeze in autumn",
        "the comfort of a familiar, old song",
        "the strange joy of being lost in a new city",
        "why we crave the smell of old books",
        "the feeling of a shared internal joke",
        "the quiet strength of a long silence",
        "the beauty of a spontaneous road trip",
        "why we love the sound of silence at night",
        "the feeling of a deep, restful sleep",
        "the relief of finally letting something go",
        "the magic of a perfect cup of coffee",
        "the beauty of a small, unexpected kindness",
        "the feeling of a fresh start on a Monday",
        "why we love the smell of earth after rain",
        "the comfort of a warm sweater in winter",
        "the strange peace of a late-night drive",
        "the feeling of a childhood home revisited",
        "the quiet pride of a small achievement",
        "the relief of a warm bowl of soup",
        "the magic of a shared look in a crowd",
        "the beauty of a sunset seen alone",
        "why we love the sound of falling snow",
        "the feeling of a new plant's first leaf",
        "the comfort of a soft, old blanket",
    ]

    HISTORY_FILE = "topic_history.json"
    HISTORY_LIMIT = 100  # Remember last 100 topics to avoid repeats

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
        Picks a unique topic.
        """
        niche    = random.choice(self.NICHES)
        now      = datetime.utcnow()
        date_str = now.strftime("%Y-%m-%d")
        hour_str = now.strftime("%H:%M UTC")
        history  = self._load_history()

        avoid_block = ""
        if history:
            avoid_list = "\n".join(f"  - {t}" for t in history[-20:])
            avoid_block = (
                f"\n\nIMPORTANT — You MUST pick something NEW. "
                f"Do NOT suggest any of these recently used topics:\n{avoid_list}"
            )

        prompt = (
            f"Today is {date_str} at {hour_str}. "
            f"Give me 1 specific, deeply relatable, and emotional human situation for: **{niche}**. "
            f"It must be something everyone has felt and makes them think 'This is literally me'. "
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
        Generates a 30-40 second Viral YouTube Shorts Storyteller script.
        """
        print(f"📝 Writing Viral Storyteller Script for: {topic}...")
        prompt = f"""
    You are a Viral YouTube Shorts Storyteller.

    GOAL:
    Create a 30–40 second highly engaging, emotional, and relatable story about: {topic}
    The story must feel like a real human experience, not facts or teaching.

    🌍 LANGUAGE RULE:
    - Use VERY SIMPLE ENGLISH (easy for a 10–12 year old)
    - Use short sentences
    - Avoid difficult words
    - Keep it clear and easy to understand globally

    🎯 CORE STYLE:
    - Talk directly to the viewer using "YOU"
    - Make it feel like: "This is exactly me"
    - Focus on emotions and real-life situations
    - Do NOT sound like a teacher or documentary

    🔥 HIGH RETENTION STRUCTURE:
    1. HOOK (0–3 sec): Start with a strong relatable line using scroll-stopping words like "wait," "suddenly," "but then," or "and you realize."
    2. RELATABLE MOMENT (3–10 sec): Show a real-life situation the viewer has experienced.
    3. BUILD-UP (10–18 sec): Add emotional depth or a small mystery.
    4. PATTERN INTERRUPT (18–20 sec): Inject ONE unexpected line that re-captures attention and breaks the rhythm.
    5. MAIN REALIZATION (20–30 sec): Reveal the deeper meaning clearly. Do NOT hide the meaning until the end. Provide clarity, not confusion.
    6. FINAL LINE / LOOP (30–40 sec): End with a powerful truth that CONNECTS BACK to the hook for a perfect playback loop.

    💥 VIRAL OPTIMIZATION RULES:
    - Viewer must understand the main idea clearly before the last 5 seconds.
    - Use "YOU" to connect emotionally.
    - Middle Pattern Interrupt: Include exactly ONE unexpected line in the middle of the story.
    - Reveal: No long secrets. Make it meaningful and relatable early on.
    - Loop Effect: The last line must feel like it flows back into the first line seamlessly.

    🚫 DO NOT USE:
    - "Did you know", "Scientists say", "Fact", "Actually"
    - Facts, numbers, history
    - Hard or complex words
    - Long sentences

    🎙️ VOICE STYLE: Natural, human, emotional, slightly slow and thoughtful.

    🎬 VISUAL RULES:
    - Each sentence = new visual scene
    - Use realistic, cinematic, emotional visuals
    - Avoid generic or random visuals
    - Scenes should feel like real-life moments

    📝 CAPTION RULES (NETFLIX STYLE):
    - Caption text MUST be 5–8 words.
    - Normal words = WHITE.
    - Important emotional words = GOLD (mark using **bold**).
    - Highlight only 1–2 key emotional words per caption.
    - Captions must match the voiceover moment exactly.

    🧠 VIRAL PSYCHOLOGY RULE:
    - Include at least ONE line that makes the viewer think: "This is literally me".

    📦 OUTPUT FORMAT (STRICT JSON - ENSURE CORRECT SPELLING OF KEYS):
    {{
      "voiceover_text": "ONE continuous paragraph (110–130 words, simple English, emotional story)",
      "segments": [
        {{
          "id": 1,
          "narration_text": "One full sentence of the story being read aloud.",
          "caption_text": "5–8 word caption with 1-2 **bold** words",
          "visual_search_1": "realistic emotional human moment",
          "visual_search_2": "cinematic relatable scene"
        }}
      ]
    }}
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

    def generate_description(self, topic: str, script_data: dict) -> str:
        """
        Generates a unique Viral description.
        """
        print("✍️ Generating viral video description...")
        
        # Extract segments to give Gemini real content to work with
        segments = script_data.get("segments", [])
        scene_texts = " | ".join(
            s.get("caption_text", "").replace("**", "") for s in segments[:5]
        )

        prompt = (
            f"You are writing a YouTube Short description for a deeply personal story about: \"{topic}\"\n\n"
            f"Write a YouTube description following this EXACT format (no extra text):\n\n"
            f"Line 1: A single emotional emoji + a 1-sentence poetic teaser about the story\n"
            f"Line 2: (blank)\n"
            f"Lines 3-4: A short, relatable message that makes the viewer want to watch until the end. "
            f"Reference the 'feeling' of the video, NOT the facts.\n"
            f"Line 5: (blank)\n"
            f"Line 6: ━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Line 7: 🔔 Subscribe for more stories that touch the soul.\n"
            f"Line 8: (blank)\n"
            f"Line 9: ━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Line 10: 10 relevant emotional hashtags starting with #Shorts #Storytelling #Emotional\n"
            f"Line 11: (blank)\n"
            f"Line 12: 🔔 Follow for your daily dose of human connection. ✨"
        )

        try:
            description = _call_with_fallback(prompt)
            return description.strip()
        except Exception as e:
            print(f"   ⚠️ Description generation failed ({e}), using default.")
            return (
                f"✨ {topic}\n\n"
                f"Have you ever felt like the world was trying to tell you something? "
                f"This story is for anyone who needs a moment of peace today.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔔 Subscribe for more stories that touch the soul.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"#Shorts #Storytelling #Emotional #Connection #Peace #Soul "
                f"#Life #Wisdom #Reflection #HumanExperience"
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