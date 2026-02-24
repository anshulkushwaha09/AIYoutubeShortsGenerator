import os
import random
import ffmpeg


# ─────────────────────────────────────────────────────────────────────────────
# Caption helpers
# ─────────────────────────────────────────────────────────────────────────────

# Vibrant color palette for the main text — cycles per caption line
CAPTION_COLORS = [
    "#FFE500",   # Bright yellow
    "#00E5FF",   # Electric cyan
    "#FF6B00",   # Hot orange
    "#FF2D8B",   # Neon pink
]

# Number of 3-D depth layers drawn behind the main text
DEPTH_LAYERS = 5

# Font size (px). At 56px bold, ~30 chars fit within 1080px.
FONT_SIZE = 56

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
    lines, current = [], ""
    for word in words:
        if current and len(current) + 1 + len(word) > max_chars:
            lines.append(current)
            current = word
        else:
            current = (current + " " + word).strip()
    if current:
        lines.append(current)
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
        self.avatar_path = os.path.join(os.getcwd(), "assets", "avatar", "avatars.mp4")
        self.font_path   = os.path.join(os.getcwd(), "assets", "fonts", "Montserrat-Bold.ttf")

        os.makedirs(self.temp_dir,  exist_ok=True)
        os.makedirs(self.final_dir, exist_ok=True)
        self.transitions = ['fade', 'diagbr', 'diagtl']

    # ── internal ──────────────────────────────────────────────────────────────

    def _font_opts(self) -> dict:
        """Base drawtext options shared by every layer."""
        opts = {"fontsize": FONT_SIZE}
        if os.path.exists(self.font_path):
            opts["fontfile"] = self.font_path.replace("\\", "/")
        return opts

    def _add_caption(self, video_stream, text: str):
        """
        Burns styled, 3-D coloured captions into *video_stream*.

        Strategy:
          • Split text into lines (one drawtext call per line → no \\n quoting issues).
          • Per line, draw DEPTH_LAYERS dark-offset copies first (3-D extrusion).
          • Then draw the coloured main text on top.
          • Colour cycles through CAPTION_COLORS per line for a vibrant look.
          • Every layer has a thick black border so text pops on any background.
        """
        lines = _wrap_text(text, max_chars=MAX_CHARS_PER_LINE)
        n = len(lines)
        line_h = FONT_SIZE + LINE_SPACING

        # Block starts at 72 % of frame height, centred vertically within its block
        # y_base_expr returns the top Y for line index i
        def y_expr(i: int) -> str:
            # total block height = n * line_h
            # centre of block at h*0.72
            # top of block = h*0.72 - (n*line_h)/2
            offset = i * line_h - (n * line_h) // 2
            sign   = "+" if offset >= 0 else "-"
            return f"(h*0.72){sign}{abs(offset)}"

        base = self._font_opts()

        for i, line in enumerate(lines):
            safe = _escape_drawtext(line)
            color = CAPTION_COLORS[i % len(CAPTION_COLORS)]
            y     = y_expr(i)

            # ── 3-D depth layers (dark, offset diagonally) ────────────────
            for d in range(DEPTH_LAYERS, 0, -1):
                video_stream = video_stream.filter(
                    "drawtext",
                    **base,
                    text=safe,
                    fontcolor="0x1a0a00@0.85",          # Very dark brown, semi-transparent
                    borderw=3,
                    bordercolor="black",
                    x=f"(w-text_w)/2+{d * 2}",          # Shift right
                    y=f"({y})+{d * 2}",                  # Shift down
                )

            # ── Main coloured text (top layer) ────────────────────────────
            video_stream = video_stream.filter(
                "drawtext",
                **base,
                text=safe,
                fontcolor=color,
                borderw=4,                               # Thick black outline
                bordercolor="black",
                shadowcolor="black@0.6",
                shadowx=2,
                shadowy=2,
                x="(w-text_w)/2",                       # Always centred
                y=y,
            )

        return video_stream

    # ── public ────────────────────────────────────────────────────────────────

    def get_duration(self, filepath):
        try:
            probe = ffmpeg.probe(filepath)
            return float(probe['format']['duration'])
        except:
            return 0.0

    def process_scene(self, scene, video_pair, is_avatar=False):
        """
        Combines Audio + Visuals + Caption for one scene.
        """
        scene_id       = scene['id']
        audio_path     = scene['audio_path']
        total_duration = scene['duration']
        caption_text   = scene.get('text', '')
        output_path    = os.path.join(self.temp_dir, f"scene_{scene_id}.mp4")

        try:
            input_audio = ffmpeg.input(audio_path)

            if is_avatar:
                # ── AVATAR MODE ────────────────────────────────────────────
                print(f"   ⚙️ Processing Scene {scene_id}: 🤖 Avatar Mode (Cropped)")
                video_stream = (
                    ffmpeg.input(video_pair[0], stream_loop=-1)
                    .trim(duration=total_duration + 0.5)
                    .setpts('PTS-STARTPTS')
                    .filter('crop', 'iw', 'ih-150', 0, 0)
                    .filter('scale', 1080, 1920, force_original_aspect_ratio='increase')
                    .filter('crop', 1080, 1920)
                    .filter('fps', fps=30, round='up')
                )
            else:
                # ── DUAL VIDEO MODE (50/50 split) ──────────────────────────
                print(f"   ⚙️ Processing Scene {scene_id}: 🎞️ A/B Split Mode")
                path_a, path_b = video_pair
                duration_a = total_duration / 2
                duration_b = (total_duration / 2) + 0.5

                stream_a = (
                    ffmpeg.input(path_a, stream_loop=-1)
                    .trim(duration=duration_a).setpts('PTS-STARTPTS')
                    .filter('scale', 1080, 1920).filter('crop', 1080, 1920)
                    .filter('fps', fps=30, round='up')
                )
                stream_b = (
                    ffmpeg.input(path_b, stream_loop=-1)
                    .trim(duration=duration_b).setpts('PTS-STARTPTS')
                    .filter('scale', 1080, 1920).filter('crop', 1080, 1920)
                    .filter('fps', fps=30, round='up')
                )
                video_stream = ffmpeg.concat(stream_a, stream_b, v=1, a=0)

            # ── Burn captions ──────────────────────────────────────────────
            if caption_text:
                video_stream = self._add_caption(video_stream, caption_text)

            # ── Encode ────────────────────────────────────────────────────
            runner = ffmpeg.output(
                video_stream, input_audio, output_path,
                vcodec='libx264', acodec='aac', pix_fmt='yuv420p', shortest=None
            )
            runner.run(overwrite_output=True, quiet=True)
            return output_path

        except ffmpeg.Error as e:
            print(f"❌ Render Fail Scene {scene_id}: {e.stderr.decode('utf8') if e.stderr else str(e)}")
            return None

    def render_all_scenes(self, script_data, video_pairs):
        rendered_paths = []
        avatar_indices = []

        if len(script_data) >= 4 and os.path.exists(self.avatar_path):
            valid_range = list(range(1, len(script_data) - 1))
            count_to_pick = 2 if len(valid_range) >= 2 else 1
            avatar_indices = sorted(random.sample(valid_range, count_to_pick))
            print(f"🎲 Avatar set for Scenes: {[i+1 for i in avatar_indices]}")

        for i, scene in enumerate(script_data):
            current_pair = video_pairs[i]
            is_avatar    = False

            if i in avatar_indices:
                current_pair = (self.avatar_path, None)
                is_avatar    = True
            elif current_pair is None:
                continue

            output_path = self.process_scene(scene, current_pair, is_avatar)
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