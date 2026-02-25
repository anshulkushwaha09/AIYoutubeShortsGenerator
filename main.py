import asyncio
import argparse
import os
import shutil
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
        topic = brain.get_trending_topic()
        script = brain.generate_script(topic)
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

    # 5. STITCH WITH TRANSITIONS
    final_video_path = None
    if final_scene_paths:
        final_video_path = composer.concatenate_with_transitions(final_scene_paths)
        clean_cache()
    else:
        print("❌ Failed to generate any scenes.")
        return

    if not final_video_path:
        print("❌ Final video creation failed.")
        return

    # 6. UPLOAD TO YOUTUBE (skipped in dry-run mode)
    if dry_run:
        print(f"\n✅ DRY RUN COMPLETE!")
        print(f"   Video saved at: {final_video_path}")
        print("   Upload step SKIPPED (dry-run mode).")
    else:
        try:
            from modules.youtube_uploader import upload_video
            video_title = f"Did You Know? | {topic[:60]} #Shorts"
            video_description = (
                f"🤯 {topic}\n\n"
                f"Did you know that some of the most incredible facts are hiding in plain sight? "
                f"In this Short, we uncover the surprising truth behind one of the world's most "
                f"fascinating stories — you won't believe it's real.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔔 Subscribe for daily mind-blowing facts!\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"#Shorts #DidYouKnow #Facts #Science #MindBlowing "
                f"#Educational #Viral #FunFacts #Amazing #LearnSomethingNew"
            )
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