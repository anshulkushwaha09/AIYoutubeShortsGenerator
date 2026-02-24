"""
test_upload.py  — Uploads the already-generated video to YouTube.

Run this AFTER a dry run to verify the upload works WITHOUT regenerating
a new video. The existing assets\final\final_short.mp4 is used directly.

Usage:
    venv\Scripts\activate
    python test_upload.py                    # uploads as PRIVATE
    python test_upload.py --public           # uploads as PUBLIC
    python test_upload.py --file my.mp4      # uploads a specific file
"""

import argparse
import os
import sys
from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Upload an existing video to YouTube")
    parser.add_argument(
        "--file", "-f",
        default=os.path.join("assets", "final", "final_short.mp4"),
        help="Path to the MP4 to upload (default: assets/final/final_short.mp4)"
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help="Upload as public (default is PRIVATE so you can review first)"
    )
    parser.add_argument(
        "--title", "-t",
        default=None,
        help="Custom title for the video"
    )
    args = parser.parse_args()

    # ── Sanity checks ────────────────────────────────────────────────────────
    if not os.path.exists(args.file):
        print(f"❌ Video file not found: {args.file}")
        print("   Run 'python main.py --dry-run' first to generate a video.")
        sys.exit(1)

    if not os.path.exists("token.pickle"):
        print("❌ token.pickle not found.")
        print("   Run 'python auth_youtube.py' first to authorise YouTube.")
        sys.exit(1)

    # ── Override privacy in the uploader ─────────────────────────────────────
    import modules.youtube_uploader as uploader

    # Monkey-patch the privacy status for this test run
    _orig_upload = uploader.upload_video

    def _patched_upload(video_path, title=None, description=None):
        import pickle
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        youtube  = uploader.get_authenticated_service()
        _title   = title or os.path.splitext(os.path.basename(video_path))[0]
        _desc    = description or "🤖 Test upload — AI YouTube Shorts Generator.\n#Shorts"
        privacy  = "public" if args.public else "private"

        print(f"📤 Uploading  : {video_path}")
        print(f"   Title      : {_title}")
        print(f"   Privacy    : {privacy.upper()}")

        body = {
            "snippet": {
                "title":           _title,
                "description":     _desc,
                "tags":            ["Shorts", "AI", "Test"],
                "categoryId":      "22",
                "defaultLanguage": "en",
            },
            "status": {
                "privacyStatus":          privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            video_path, mimetype="video/mp4",
            resumable=True, chunksize=4 * 1024 * 1024
        )
        req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            status, response = req.next_chunk()
            if status:
                print(f"   ⬆️  {int(status.progress() * 100)}%")

        vid_id  = response["id"]
        vid_url = f"https://www.youtube.com/shorts/{vid_id}"
        print(f"\n✅ Upload successful!")
        print(f"   URL   : {vid_url}")
        print(f"   Studio: https://studio.youtube.com/video/{vid_id}/edit")
        if privacy == "private":
            print("\n   ℹ️  Video is PRIVATE — only you can see it.")
            print("      Go to YouTube Studio to make it public when ready.")
        return vid_url

    # Run the upload
    try:
        _patched_upload(args.file, title=args.title)
    except Exception as e:
        print(f"\n❌ Upload failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
