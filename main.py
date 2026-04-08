import asyncio
import argparse
import os
import shutil
import sys

# Ensure UTF-8 output for Windows Console
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
from modules.brain import ContentBrain
from modules.asset_manager import AssetManager
from modules.audio import AudioEngine
from modules.composer import Composer

# Load .env on startup
load_dotenv()


def clean_cache():
    """
    Safely deletes temporary files.
    Includes a Safety Lock to prevent deleting anything outside the project.
    """
    print("🧹 Cleaning up temporary files...")
    
    folders_to_clean = [
        os.path.join(os.getcwd(), "assets", "audio_clips"),
        os.path.join(os.getcwd(), "assets", "video_clips"),
        os.path.join(os.getcwd(), "assets", "temp")
    ]

    for folder in folders_to_clean:
        if not os.path.exists(folder):
            continue
        if "assets" not in folder:
            print(f"   🚨 SECURITY ALERT: Skipping {folder} because it looks unsafe!")
            continue

        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"   ❌ Failed to delete {file_path}. Reason: {e}")
    
    print("✨ Workspace clean!")


async def main(dry_run: bool = False):
    print("🚀 STARTING AUTOMATION...")
    if dry_run:
        print("🧪 DRY-RUN MODE — video will be saved locally, not uploaded.")

    # 1. BRAIN: Get Script
    brain = ContentBrain()
    try:
        niche, topic = brain.get_trending_topic()
        scenario = brain.get_specific_scenario(niche, topic)
        script = brain.generate_script(topic, scenario)
    except Exception as e:
        print(f"❌ Brain Error: {e}")
        return

    if not script:
        print("❌ Script generation failed.")
        return

    # 2. AUDIO: Generate Voice
    audio_engine = AudioEngine()
    try:
        script = await audio_engine.process_script(script)
    except Exception as e:
        print(f"❌ Audio Error: {e}")
        return

    # 3. ASSETS: Get Stock Video
    asset_manager = AssetManager()
    assets_map = asset_manager.get_videos(script)

    # 4. COMPOSER: Merge Video + Audio
    composer = Composer()
    final_scene_paths = composer.render_all_scenes(script, assets_map)

    print(f"🎬 Generated {len(final_scene_paths)} / {len(script['segments'])} scenes.")
    if not final_scene_paths:
        print("❌ No scenes were successfully rendered. Check ffmpeg output above.")
        return

    # 5. STITCH WITH TRANSITIONS
    final_video_path = composer.concatenate_with_transitions(final_scene_paths)

    if not final_video_path:
        print("❌ Final video creation failed.")
        # We don't clean cache here so user can inspect scene_*.mp4 files
        return

    # 6. Success: Clean up and finish
    clean_cache()

    # 6. UPLOAD TO YOUTUBE (skipped in dry-run mode)
    if dry_run:
        print(f"\n✅ DRY RUN COMPLETE!")
        print(f"   Video saved at: {final_video_path}")
        print("   Upload step SKIPPED (dry-run mode).")
    else:
        try:
            from modules.youtube_uploader import upload_video
            video_title       = f"Have you ever felt this? | {topic[:35]} 🕊️ #Shorts"
            video_description = brain.generate_description(topic, script)
            upload_video(final_video_path, title=video_title, description=video_description)
        except Exception as e:
            print(f"❌ YouTube Upload Error: {e}")
            print(f"   The video was still saved at: {final_video_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI YouTube Shorts Generator")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate the video locally without uploading to YouTube."
    )
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run))