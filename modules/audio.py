import os
import asyncio
import edge_tts
from mutagen.mp3 import MP3

class AudioEngine:
    def __init__(self, voice="en-US-ChristopherNeural"):
        self.voice = voice
        self.output_dir = os.path.join(os.getcwd(), "assets", "audio_clips")
        os.makedirs(self.output_dir, exist_ok=True)

    async def generate_audio(self, text, output_filename, retries=3):
        """
        Generates MP3 with retry logic to handle connection drops.
        """
        # Remove bold markers for TTS
        clean_text = text.replace("**", "")
        output_path = os.path.join(self.output_dir, output_filename)
        
        for attempt in range(retries):
            try:
                # Rate +30% for hyper-paced elite engagement
                communicate = edge_tts.Communicate(clean_text, self.voice, rate="+22%")
                await communicate.save(output_path)
                return output_path
            
            except Exception as e:
                print(f"      ⚠️ Audio Error (Attempt {attempt+1}/{retries}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2) # Wait 2 seconds before retrying
                else:
                    print("      ❌ Failed to generate audio after max retries.")
                    raise e # Re-raise error if all retries fail

    def get_audio_duration(self, file_path):
        try:
            audio = MP3(file_path)
            return audio.info.length
        except Exception as e:
            print(f"❌ Error reading audio length: {e}")
            return 0.0

    async def process_script(self, script_data):
        """
        Processes segments list and generates audio for each.
        """
        segments = script_data.get("segments", [])
        print(f"🎙️ Starting Audio Generation for {len(segments)} segments...")
        
        for segment in segments:
            segment_id = segment['id']
            # Defensive check for common LLM typos in keys
            text = segment.get('narration_text', segment.get('naration_text', ''))
            if not text:
                print(f"      ⚠️ No narration text found for segment {segment_id}. Skipping.")
                continue
            filename = f"voice_{segment_id}.mp3"
            
            try:
                # Generate Audio
                file_path = await self.generate_audio(text, filename)
                
                # Get Duration
                duration = self.get_audio_duration(file_path)
                
                # Update Segment Data
                segment['audio_path'] = file_path
                segment['duration'] = duration
                
                print(f"   ✅ Segment {segment_id}: {duration:.2f}s generated.")
                
                # CRITICAL: Sleep for 1 second to be polite to the API
                await asyncio.sleep(1) 
                
            except Exception as e:
                print(f"   ❌ Skipping Segment {segment_id} due to audio error.")
                continue
            
        return script_data