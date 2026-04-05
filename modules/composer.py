import os
import random
import ffmpeg
import re


# ─────────────────────────────────────────────────────────────────────────────
# Caption helpers
# ─────────────────────────────────────────────────────────────────────────────

# Color palette for captions
CAPTION_COLORS = ["#FFFFFF"] # Pure white
HIGHLIGHT_COLOR = "#FFD700" # Golden (Target hex)

# ASS Color: BGR format (BGR: 00 D7 FF -> Gold)
ASS_GOLD = "&H00D7FF&"
ASS_WHITE = "&H00FFFFFF&"

# Number of 3-D depth layers drawn behind the main text (Used only for drawtext fallback)
DEPTH_LAYERS = 5

# Font size (px). At 56px bold, ~30 chars fit within 1080px.
FONT_SIZE = 64

# Maximum characters per wrapped line. Keep enough margin so long words fit.
MAX_CHARS_PER_LINE = 24

# Vertical gap between caption lines (pixels)
LINE_SPACING = 14


def _wrap_text(text: str, max_chars: int = MAX_CHARS_PER_LINE) -> list[str]:
    """
    Returns a list of strings, each no longer than max_chars.
    Uses word-boundary wrapping so words are never cut mid-character.
    """
    words = text.split()
    lines = []
    current_line = []
    current_len = 0

    for word in words:
        # Check length WITHOUT ** markers to be accurate
        clean_word = word.replace("**", "")
        if current_len + len(clean_word) + 1 > max_chars:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_len = len(clean_word)
            else:
                lines.append(word)
                current_line = []
                current_len = 0
        else:
            current_line.append(word)
            current_len += len(clean_word) + 1

    if current_line:
        lines.append(" ".join(current_line))

    return lines


def _escape_drawtext(text: str) -> str:
    """
    Escapes all characters that FFmpeg drawtext treats specially.
    NOTE: we do NOT join lines with '\\n' here — each line is a separate
    drawtext call to avoid ffmpeg-python double-escaping the backslash.
    """
    text = text.replace("\\", "\\\\")   # Must be first
    text = text.replace("'",  "\u2019") # Curly apostrophe — avoids shell quoting issues
    text = text.replace(":",  "\\:")
    text = text.replace("%",  "%%")
    return text


class Composer:
    def __init__(self):
        self.temp_dir    = os.path.join(os.getcwd(), "assets", "temp")
        self.final_dir   = os.path.join(os.getcwd(), "assets", "final")
        self.font_path   = os.path.join(os.getcwd(), "assets", "fonts", "Montserrat-Bold.ttf")

        os.makedirs(self.temp_dir,  exist_ok=True)
        os.makedirs(self.final_dir, exist_ok=True)
        # Elite cinematic transitions
        self.transitions = ['fade', 'diagbr', 'diagtl', 'wipeleft', 'wiperight', 'circleopen', 'horzopen']

    # ── internal ──────────────────────────────────────────────────────────────

    def _apply_motion(self, stream):
        """
        Applies a random cinematic motion effect (Zoom-In or Subtle Pan).
        Utilizes FFmpeg's zoompan filter for vertical 1080x1920 videos.
        """
        motion_type = random.choice(['zoom_in', 'zoom_out', 'pan_center'])
        
        if motion_type == 'zoom_in':
            # Subtly zoom into center: Starts at 1.0, ends around 1.15
            return stream.filter(
                'zoompan', 
                z='min(pzoom+0.001,1.5)', 
                d=1, 
                x='iw/2-(iw/zoom/2)', 
                y='ih/2-(ih/zoom/2)', 
                s='1080x1920', 
                fps=30
            )
        elif motion_type == 'zoom_out':
            # Start slightly zoomed (1.2) and zoom out to 1.0
            return stream.filter(
                'zoompan',
                z='max(1.3-0.001*on,1.0)',
                d=1,
                x='iw/2-(iw/zoom/2)',
                y='ih/2-(ih/zoom/2)',
                s='1080x1920',
                fps=30
            )
        else:
            # Subtle vertical drift (Pan)
            return stream.filter(
                'zoompan',
                z='1.1', # Fixed zoom to enable panning
                d=1,
                x='iw/2-(iw/zoom/2)',
                y='(ih/2-(ih/zoom/2)) + (ih*0.05*sin(on/10))', # Slight vertical wave
                s='1080x1920',
                fps=30
            )

    def _add_caption(self, video_stream, text: str, scene_id: int):
        """
        Generates a temporary .ass file with word-level highlighting
        and burns it into the video stream using the subtitles filter.
        """
        # 1. Wrap and Parse
        lines = _wrap_text(text, max_chars=MAX_CHARS_PER_LINE)
        
        # Replace **word** with {\c&H00D7FF&}word{\c&HFFFFFF&}
        ass_lines = []
        for line in lines:
            # Replaces **text** with colored text using ASS tags.
            # BGR format: Gold #FFD700 -> &H00D7FF&
            # Fixed escaping: ASS tags use single {}, f-strings need {{ to produce literal {
            colored_line = re.sub(r'\*\*(.*?)\*\*', rf'{{\\c{ASS_GOLD}}}\1{{\\c{ASS_WHITE}}}', line)
            ass_lines.append(colored_line)
        
        display_text = "\\N".join(ass_lines)
        
        # 2. Write .ass File
        ass_path = os.path.join(self.temp_dir, f"sub_{scene_id}.ass")
        
        # Style definition for Netflix-style captions
        # Alignment 2 (Bottom Center), MarginV 340 (Typical for mobile shorts)
        try:
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nScaledBorderAndShadow: yes\n\n")
                f.write("[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
                f.write(f"Style: Default,Arial,{FONT_SIZE},&H00FFFFFF&,&H000000FF&,&H00000000&,&H00000000&,1,0,0,0,100,100,0,0,1,4,2,2,10,10,340,1\n\n")
                f.write("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
                f.write(f"Dialogue: 0,0:00:00.00,0:10:00.00,Default,,0,0,0,,{display_text}\n")
        except Exception as e:
            print(f"⚠️ Failed to write ASS file: {e}")
            return video_stream

        # 3. Apply Subtitles Filter
        # Use relative path + forward slashes for the subtitles filter.
        # This keeps the filename simple and avoids Windows drive colons (:) 
        # which FFmpeg treats as a filter separator.
        try:
            rel_path = os.path.relpath(ass_path, os.getcwd())
            clean_path = rel_path.replace("\\", "/")
            return video_stream.filter("subtitles", filename=clean_path)
        except Exception:
            # Fallback for complex path scenarios
            clean_path_abs = ass_path.replace("\\", "/").replace(":", "\\:")
            return video_stream.filter("subtitles", filename=clean_path_abs)

    # ── public ────────────────────────────────────────────────────────────────

    def get_duration(self, filepath):
        try:
            probe = ffmpeg.probe(filepath)
            return float(probe['format']['duration'])
        except:
            return 0.0

    def process_scene(self, scene, video_pair):
        """
        Combines Audio + Visuals + Caption for one scene/segment.
        """
        scene_id       = scene['id']
        audio_path     = scene['audio_path']
        total_duration = scene['duration']
        caption_text   = scene.get('caption_text', '')
        output_path    = os.path.join(self.temp_dir, f"scene_{scene_id}.mp4")

        try:
            input_audio = ffmpeg.input(audio_path)

            # ── DUAL VIDEO MODE (50/50 split) ──────────────────────────
            print(f"   ⚙️ Processing Segment {scene_id}: 🎞️ Dual-Stock Mode")
            path_a, path_b = video_pair
            duration_a = total_duration / 2
            duration_b = (total_duration / 2) + 0.1 # Small overlap for continuity

            stream_a = (
                ffmpeg.input(path_a, stream_loop=-1)
                .trim(duration=duration_a).setpts('PTS-STARTPTS')
                .filter('scale', 1080, 1920, force_original_aspect_ratio='increase')
                .filter('crop', 1080, 1920)
                .filter('fps', fps=30, round='up')
            )
            stream_a = self._apply_motion(stream_a)

            stream_b = (
                ffmpeg.input(path_b, stream_loop=-1)
                .trim(duration=duration_b).setpts('PTS-STARTPTS')
                .filter('scale', 1080, 1920, force_original_aspect_ratio='increase')
                .filter('crop', 1080, 1920)
                .filter('fps', fps=30, round='up')
            )
            stream_b = self._apply_motion(stream_b)

            video_stream = ffmpeg.concat(stream_a, stream_b, v=1, a=0)

            # ── Burn captions ──────────────────────────────────────────────
            if caption_text:
                video_stream = self._add_caption(video_stream, caption_text, scene_id)

            # ── Encode ────────────────────────────────────────────────────
            runner = ffmpeg.output(
                video_stream, input_audio, output_path,
                vcodec='libx264', acodec='aac', pix_fmt='yuv420p', shortest=None
            )
            runner.run(overwrite_output=True, quiet=True)
            return output_path

        except ffmpeg.Error as e:
            print(f"❌ Render Fail Segment {scene_id}: {e.stderr.decode('utf8') if e.stderr else str(e)}")
            return None

    def render_all_scenes(self, script_data, video_pairs):
        rendered_paths = []
        segments = script_data.get("segments", [])

        for i, segment in enumerate(segments):
            current_pair = video_pairs[i]
            if current_pair is None:
                continue

            output_path = self.process_scene(segment, current_pair)
            if output_path:
                rendered_paths.append(output_path)

        return rendered_paths

    def concatenate_with_transitions(self, video_paths, output_filename="final_short.mp4"):
        print("🎬 Stitching final video...")
        output_path = os.path.join(self.final_dir, output_filename)

        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                print("⚠️ Could not delete old file — it may be open in a player.")

        if not video_paths:
            return None

        input1      = ffmpeg.input(video_paths[0])
        v_stream    = input1.video
        a_stream    = input1.audio
        current_dur = self.get_duration(video_paths[0])

        for i in range(1, len(video_paths)):
            next_clip = ffmpeg.input(video_paths[i])
            next_dur  = self.get_duration(video_paths[i])
            trans_dur = 0.5
            offset    = current_dur - trans_dur
            effect    = random.choice(self.transitions)
            print(f"   ✨ Transition {i}: '{effect}' at {offset:.2f}s")

            v_stream = ffmpeg.filter(
                [v_stream, next_clip.video], 'xfade',
                transition=effect, duration=trans_dur, offset=offset
            )
            a_stream = ffmpeg.filter(
                [a_stream, next_clip.audio], 'acrossfade', d=trans_dur
            )
            current_dur = (current_dur + next_dur) - trans_dur

        try:
            runner = ffmpeg.output(
                v_stream, a_stream, output_path,
                vcodec='libx264', acodec='aac',
                pix_fmt='yuv420p', movflags='faststart', preset='medium'
            )
            runner.run(overwrite_output=True, quiet=False)
            print(f"✅ FINAL VIDEO SAVED: {output_path}")
            return output_path

        except ffmpeg.Error as e:
            print(f"❌ Stitching Error: {e.stderr.decode('utf8') if e.stderr else str(e)}")
            return None