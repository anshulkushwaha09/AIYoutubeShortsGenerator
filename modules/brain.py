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
    primary = os.getenv("GEMINI_API_KEY")
    if primary:
        keys.append(primary)

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

# Model fallback chain (Ordered by stability and quota availability)
FALLBACK_MODELS = [
    "gemini-2.0-flash",      # Primary (Fast & Reliable)
    "gemini-1.5-flash",      # Secondary (Standard)
    "gemini-2.0-flash-lite", # Experimental
    "gemini-2.5-flash",      # High-performance preview
    "gemini-2.5-pro",        # Pro fallback
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
        # ── Pacing ──
        # Mandatory sleep BEFORE every key attempt to avoid burst-limiting (15 RPM = 1 req / 4s)
        time.sleep(2.0)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] 🔑 Using API Key #{i+1}...")
        
        for model in FALLBACK_MODELS:
            try:
                print(f"      🤖 Trying model: {model}...")
                response = client_inst.models.generate_content(model=model, contents=prompt)
                return response.text.strip()

            except Exception as e:
                err_str = str(e)
                last_error = e
                
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    print(f"      ⚠️ Quota hit on {model} (Key #{i+1}). Skipping this key for now...")
                    # Delay slightly after a failure before switching keys
                    time.sleep(1.0)
                    break 
                
                elif "503" in err_str or "unavailable" in err_str.lower():
                    print(f"      ⚠️ Service busy on {model}. Retrying next model...")
                    time.sleep(2.0) # Longer wait before model-retry
                
                elif "404" in err_str or "not found" in err_str.lower():
                    print(f"      ⚠️ Model {model} unavailable.")
                else:
                    print(f"      ⚠️ Error on {model}: {e}")
                    time.sleep(2.0)

    raise RuntimeError(
        "🛑 GOOGLE QUOTA ERROR: All Gemini models/keys have exceeded their quotas. "
        "The automation will resume once the rate limits reset."
    )


class ContentBrain:
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

    VALID_TONES = ["nostalgic", "hopeful", "bittersweet", "aching", "joyful"]

    HISTORY_FILE = "topic_history.json"
    HISTORY_LIMIT = 100

    # ─── History Helpers ───────────────────────────────────────────────────────

    def _load_history(self) -> list:
        if os.path.exists(self.HISTORY_FILE):
            try:
                with open(self.HISTORY_FILE, "r") as f:
                    data = json.load(f)
                # Migrate old flat-string entries to dict format
                migrated = []
                for entry in data:
                    if isinstance(entry, str):
                        migrated.append({"topic": entry, "tone": "nostalgic"})
                    else:
                        migrated.append(entry)
                return migrated
            except Exception:
                pass
        return []

    def _save_history(self, history: list):
        try:
            with open(self.HISTORY_FILE, "w") as f:
                json.dump(history[-self.HISTORY_LIMIT:], f, indent=2)
        except Exception:
            pass

    def _get_tone_balance_instruction(self, history: list) -> str:
        """Returns a prompt instruction to avoid repeating tones too many times."""
        recent = history[-10:]
        tone_counts = {t: 0 for t in self.VALID_TONES}
        for entry in recent:
            tone = entry.get("tone", "")
            if tone in tone_counts:
                tone_counts[tone] += 1

        overused = [t for t, c in tone_counts.items() if c >= 3]
        if overused:
            return (
                f"\n\nTONE BALANCE RULE: The following tones have been used too recently. "
                f"Do NOT use a '{', '.join(overused)}' tone. "
                f"Choose a different emotional tone so the same tone isn't repeated more than 3 times in a row."
            )
        return ""

    # ─── Step 1: Topic ─────────────────────────────────────────────────────────

    def get_trending_topic(self):
        """Picks a unique, emotionally specific topic and returns (niche, topic)."""
        niche    = random.choice(self.NICHES)
        now      = datetime.utcnow()
        date_str = now.strftime("%Y-%m-%d")
        hour_str = now.strftime("%H:%M UTC")
        history  = self._load_history()

        avoid_block = ""
        if history:
            recent_topics = [e["topic"] for e in history[-20:]]
            avoid_list = "\n".join(f"  - {t}" for t in recent_topics)
            avoid_block = (
                f"\n\nIMPORTANT — You MUST pick something NEW. "
                f"Do NOT suggest any of these recently used topics:\n{avoid_list}"
            )

        tone_instruction = self._get_tone_balance_instruction(history)

        prompt = (
            f"Today is {date_str} at {hour_str}. "
            f"Give me 1 specific, deeply relatable, and emotional human situation for: **{niche}**. "
            f"It must be something everyone has felt and makes them think 'This is literally me'. "
            f"Return ONLY the topic name, nothing else."
            f"{avoid_block}"
            f"{tone_instruction}"
        )

        topic = _call_with_fallback(prompt)
        print(f"🎯 Topic ({niche}): {topic}")
        return niche, topic

    # ─── Step 2: Scenario Pre-Processor ────────────────────────────────────────

    def get_specific_scenario(self, niche: str, topic: str) -> str:
        """
        Converts the abstract niche + topic into a hyper-specific triggering
        micro-moment — a single sentence describing the exact situation.
        """
        print(f"🔍 Converting topic into hyper-specific scenario...")
        prompt = (
            f"You are a viral content writer.\n\n"
            f"Niche: {niche}\n"
            f"Topic: {topic}\n\n"
            f"Convert this into ONE hyper-specific triggering micro-moment — "
            f"a single vivid sentence describing the exact real-life situation a viewer is in "
            f"when they feel this emotion. It must be so specific that the viewer thinks "
            f"'how did you know this happened to me?'\n\n"
            f"Example format: 'You're cleaning your room at midnight and you find an old photo "
            f"of yourself from 5 years ago — and you don't recognise that person anymore.'\n\n"
            f"Return ONLY the one sentence scenario. No labels, no extra text."
        )
        scenario = _call_with_fallback(prompt)
        print(f"🎬 Scenario: {scenario}")
        return scenario.strip()

    # ─── Step 3: Script Generator ───────────────────────────────────────────────

    def generate_script(self, topic: str, scenario: str) -> dict | None:
        """
        Generates a 30–35 second Viral YouTube Shorts Storyteller script
        using the hyper-specific scenario as the anchor.
        """
        print(f"📝 Writing Viral Storyteller Script...")
        prompt = f"""
You are a Viral YouTube Shorts Storyteller.

STORY ANCHOR (use this as your specific, concrete starting point):
{scenario}

TOPIC (the broader emotional theme):
{topic}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔥 VIRAL STORY STRUCTURE — FOLLOW THIS EXACTLY:

STEP A — WRITE THE FINAL LINE FIRST (internally):
  Before writing anything else, decide on the final closing line of the story.
  This line must be a powerful universal truth.
  Then write the HOOK so it feeds back into this final line — same rhythm, same feeling.
  The last word or phrase of the story should echo the first word or phrase of the hook.
  This creates a perfect LOOP for repeat viewing.

1. HOOK (0–3 sec):
   - Write as if you are FINISHING the viewer's own mid-thought sentence.
   - The viewer must feel called out within 2 seconds.
   - Use words like "wait," "suddenly," "but then," "and you realize," or start mid-sentence.
   - Do NOT introduce yourself. Drop the viewer into the middle of the feeling.
   - The first caption must end on an INCOMPLETE THOUGHT so the eye is forced to keep reading.

2. RELATABLE MOMENT (3–10 sec):
   - Show the exact real-life situation from the STORY ANCHOR above.
   - Use "you" — put the viewer inside the scene.

3. BUILD-UP (10–18 sec):
   - Add emotional depth. A small mystery or a quiet realization building.
   - The viewer should feel a slight discomfort — like being understood too well.

4. PATTERN INTERRUPT (18–20 sec):
   - ONE completely unexpected line that snaps attention back.
   - It should feel like a sudden zoom-out or a plot twist of emotion.
   - Break the rhythm of the story here.

5. MAIN REALIZATION (20–30 sec):
   - Reveal the deeper meaning CLEARLY. Do not hide it.
   - The viewer must fully understand the core idea before the last 5 seconds.
   - This is the RELEASE — after the discomfort of the build-up, give the viewer relief.
   - Include at least ONE line that makes the viewer think: "This is literally me."

6. FINAL LINE / LOOP (30–35 sec):
   - End with the powerful truth you decided in STEP A.
   - It must connect back to the hook — same rhythm or same phrase — for a seamless loop.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💥 EMOTIONAL ARC RULE:
- Seconds 0–5: Slight discomfort (viewer feels called out / exposed)
- Seconds 5–20: Recognition (viewer sees themselves in the story)
- Seconds 20–35: Release (viewer feels understood, not alone, at peace)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚫 DO NOT USE:
- "Did you know", "Scientists say", "Fact", "Actually"
- Facts, numbers, history
- Hard or complex words
- Long sentences

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
- The FIRST caption must end mid-thought (incomplete) to force the viewer to keep watching.

⏱️ PACING:
Each segment must include a "pace" field:
  - "slow"   → for emotional peaks and the main realization
  - "medium" → for transitions and build-up
  - "punch"  → for the hook, pattern interrupt, and final line

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 COMMENT BAIT:
Generate ONE "comment_bait_line" — a line NOT spoken in the video, but designed to be
pinned as a comment or shown as a sticker. It must be:
  - A fill-in-the-blank ("The last time I felt this was ___")
  - OR a "tag someone" line ("Tag someone who needs this right now 💙")
  - OR a statement SO specific it demands a reply

🖼️ THUMBNAIL MOMENT:
Identify ONE "thumbnail_moment" — describe the single most emotionally charged visual
frame in the entire video. This will be used as the freeze-frame thumbnail.
It must be visually striking, emotionally readable at a glance, and make someone stop scrolling.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📦 OUTPUT FORMAT — STRICT JSON ONLY. NO MARKDOWN. NO PREAMBLE:
{{
  "voiceover_text": "ONE continuous paragraph (85–100 words, simple English, emotional story)",
  "comment_bait_line": "One pinnable comment or sticker line that demands engagement",
  "thumbnail_moment": "One sentence describing the most emotionally charged visual frame",
  "segments": [
    {{
      "id": 1,
      "narration_text": "One full sentence of the story being read aloud.",
      "caption_text": "5–8 word caption with 1-2 **bold** words",
      "pace": "slow | medium | punch",
      "visual_search_1": "realistic emotional human moment",
      "visual_search_2": "cinematic relatable scene"
    }}
  ]
}}
"""
        raw_text = _call_with_fallback(prompt)
        clean_text = raw_text.replace('```json', '').replace('```', '').strip()

        try:
            script_data = json.loads(clean_text)
            return script_data
        except json.JSONDecodeError:
            print("❌ Error parsing JSON. Raw output:")
            print(clean_text)
            return None

    # ─── Step 4: Title Generator ────────────────────────────────────────────────

    def generate_title(self, topic: str, scenario: str) -> dict:
        """
        Generates 3 title variants optimised for YouTube Shorts.
        Returns a dict with keys: curiosity, emotion, you_statement.
        """
        print("🏷️  Generating 3 title variants...")
        prompt = (
            f"You are a YouTube Shorts title expert.\n\n"
            f"Topic: {topic}\n"
            f"Scenario: {scenario}\n\n"
            f"Write exactly 3 YouTube Shorts titles. Each must be under 60 characters.\n"
            f"Return ONLY valid JSON — no markdown, no preamble:\n\n"
            f"{{\n"
            f'  "curiosity": "A curiosity-gap title that makes viewer need to watch",\n'
            f'  "emotion": "A pure emotion-driven title that hits the heart",\n'
            f'  "you_statement": "A second-person title starting with You or Your"\n'
            f"}}\n\n"
            f"Rules:\n"
            f"- Under 60 characters each\n"
            f"- No clickbait lies — must match the actual story\n"
            f"- Simple words only\n"
            f"- No hashtags in the title"
        )

        raw = _call_with_fallback(prompt)
        clean = raw.replace('```json', '').replace('```', '').strip()
        try:
            titles = json.loads(clean)
            return titles
        except json.JSONDecodeError:
            print("⚠️ Title JSON parse failed. Using defaults.")
            return {
                "curiosity": f"This will make you stop and think...",
                "emotion":   f"The feeling you never talk about",
                "you_statement": f"You've felt this and never knew why"
            }

    # ─── Step 5: Tone Detector ──────────────────────────────────────────────────

    def _detect_tone(self, script_data: dict) -> str:
        """Asks Gemini to classify the tone of the generated script."""
        voiceover = script_data.get("voiceover_text", "")
        if not voiceover:
            return random.choice(self.VALID_TONES)

        prompt = (
            f"Read this short story and classify its overall emotional tone.\n\n"
            f"\"{voiceover}\"\n\n"
            f"Choose EXACTLY ONE word from this list: nostalgic, hopeful, bittersweet, aching, joyful\n"
            f"Return ONLY the one word, nothing else."
        )
        try:
            tone = _call_with_fallback(prompt).strip().lower()
            if tone not in self.VALID_TONES:
                tone = random.choice(self.VALID_TONES)
        except Exception:
            tone = random.choice(self.VALID_TONES)
        print(f"🎭 Detected tone: {tone}")
        return tone

    # ─── Step 6: Description Generator ─────────────────────────────────────────

    def generate_description(self, topic: str, script_data: dict) -> str:
        """Generates a unique viral YouTube Shorts description."""
        print("✍️  Generating viral video description...")

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


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    brain = ContentBrain()

    # Step 1: Get topic
    niche, topic = brain.get_trending_topic()

    # Step 2: Convert to hyper-specific scenario
    scenario = brain.get_specific_scenario(niche, topic)

    # Step 3: Generate script using the scenario
    script = brain.generate_script(topic, scenario)

    if script is None:
        print("❌ Script generation failed. Exiting.")
        exit(1)

    # Step 4: Generate 3 title variants
    titles = brain.generate_title(topic, scenario)
    print("\n🏷️  Title Variants:")
    print(f"   Curiosity    : {titles.get('curiosity')}")
    print(f"   Emotion      : {titles.get('emotion')}")
    print(f"   You Statement: {titles.get('you_statement')}")

    # Step 5: Detect tone and save to history
    tone = brain._detect_tone(script)
    history = brain._load_history()
    history.append({"topic": topic, "tone": tone})
    brain._save_history(history)

    # Step 6: Generate description
    desc = brain.generate_description(topic, script)
    print("\n📋 Description preview:\n")
    print(desc)

    # Step 7: Save everything into a single output.json
    full_output = {
        "meta": {
            "niche":    niche,
            "topic":    topic,
            "scenario": scenario,
            "tone":     tone,
            "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        },
        "titles":      titles,
        "script":      script,
        "description": desc,
    }

    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=4, ensure_ascii=False)
        print("\n✅ Full output saved to output.json")