import json
import subprocess
import os
import sys
import math

# Increase recursion depth for deep expression trees
sys.setrecursionlimit(200000)

class VideoRenderer:
    def __init__(self, project_dir):
        self.project_dir = project_dir
        self.segment_dir = os.path.join(project_dir, 'segments', 'segment-0')
        self.cursor_dir = os.path.join(project_dir, 'cursors')
        
        # Default Settings
        self.cam_scale_w = 280
        self.cam_scale_h = 158
        self.cursor_scale = 48
        self.cam_shape = "rounded"
        self.cam_margin_x = 20
        self.cam_margin_y = 20
        
        # Caption Settings
        self.enable_caption = False
        self.caption_font = "Arial"
        self.caption_size = 24
        self.caption_color = "&H00FFFFFF"
        self.caption_outline_color = "&H00000000"
        self.caption_pos = 50
        self.whisper_model = "base" # tiny, base, small
        self.use_faster_whisper = False

    def build_lerp_tree(self, times, values, start, end):
        if end - start == 1:
            t1, t2 = times[start], times[end]
            v1, v2 = values[start], values[end]
            if t2 == t1: return f"{v1:.2f}"
            slope = (v2 - v1) / (t2 - t1)
            return f"({v1:.2f}+{slope:.4f}*(t-{t1:.4f}))"
        mid = (start + end) // 2
        return f"if(lt(t,{times[mid]:.4f}),{self.build_lerp_tree(times, values, start, mid)},{self.build_lerp_tree(times, values, mid, end)})"

    def generate_captions(self):
        audio_path = os.path.join(self.segment_dir, 'audio-input.ogg')
        if not os.path.exists(audio_path): return None

        segments_data = []
        
        if self.use_faster_whisper:
            try:
                from faster_whisper import WhisperModel
                print(f"\n[AI] Using Faster-Whisper ({self.whisper_model})...")
                model = WhisperModel(self.whisper_model, device="cpu", compute_type="int8")
                segments, _ = model.transcribe(audio_path, language="id", beam_size=5)
                for s in segments:
                    segments_data.append({'start': s.start, 'end': s.end, 'text': s.text})
            except ImportError:
                print("faster-whisper not installed, falling back to standard whisper...")
                self.use_faster_whisper = False

        if not self.use_faster_whisper:
            try:
                import whisper
                print(f"\n[AI] Using Standard Whisper ({self.whisper_model})...")
                model = whisper.load_model(self.whisper_model)
                result = model.transcribe(audio_path, language="id")
                segments_data = result['segments']
            except ImportError:
                print("\nError: Whisper libraries not found. Run: pip install openai-whisper")
                return None

        ass_path = "captions.ass"
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n")
            f.write("[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
            f.write(f"Style: Default,{self.caption_font},{self.caption_size},{self.caption_color},{self.caption_outline_color},1,2,0,2,10,10,{self.caption_pos},1\n\n")
            f.write("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            for segment in segments_data:
                start = self._format_ass_time(segment['start'])
                end = self._format_ass_time(segment['end'])
                text = segment['text'].strip()
                f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")
        return ass_path

    def _format_ass_time(self, seconds):
        td = float(seconds)
        h, m, s = int(td // 3600), int((td % 3600) // 60), td % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    def generate_script(self, output_file="output_rendered.mp4", duration_limit=None):
        caption_filter = ""
        if self.enable_caption:
            ass_file = self.generate_captions()
            if ass_file:
                escaped_ass = ass_file.replace(":", "\\:").replace("\\", "/")
                caption_filter = f", subtitles='{escaped_ass}'"

        cursor_json_path = os.path.join(self.segment_dir, 'cursor.json')
        with open(cursor_json_path, 'r') as f:
            data = json.load(f)

        moves = data.get('moves', [])
        if duration_limit:
            moves = [m for m in moves if m['time_ms']/1000.0 <= duration_limit + 1.0]
        if not moves: return False
        moves.sort(key=lambda x: x['time_ms'])

        times = [m['time_ms'] / 1000.0 for m in moves]
        xs = [m['x'] * 1920 for m in moves]
        ys = [m['y'] * 1080 for m in moves]
        ids = [int(m['cursor_id']) for m in moves]

        x_expr = self.build_lerp_tree(times, xs, 0, len(moves) - 1)
        y_expr = self.build_lerp_tree(times, ys, 0, len(moves) - 1)
        
        def build_step_tree(vals, s, e):
            if s == e: return str(vals[s])
            m = (s + e) // 2
            return f"if(lt(t,{times[m]:.4f}),{build_step_tree(vals, s, m)},{build_step_tree(vals, m+1, e)})"
        id_expr = build_step_tree(ids, 0, len(moves) - 1)

        inputs = ['-i', os.path.join(self.segment_dir, 'display.mp4'), '-i', os.path.join(self.segment_dir, 'camera.mp4'), '-i', os.path.join(self.segment_dir, 'audio-input.ogg')]
        for i in range(11): inputs.extend(['-i', os.path.join(self.cursor_dir, f'cursor_{i}.png')])

        filters = []
        filters.append(f"[1:v] scale={self.cam_scale_w}:{self.cam_scale_h}, format=rgba [cam_scaled];")
        if self.cam_shape == "circle":
            r = min(self.cam_scale_w, self.cam_scale_h) / 2
            filters.append(f"[cam_scaled] geq=lum='p(X,Y)':a='if(lte(pow(X-{self.cam_scale_w/2},2)+pow(Y-{self.cam_scale_h/2},2),{r*r}),255,0)' [cam];")
        elif self.cam_shape == "rounded":
            rad = 20
            filters.append(f"[cam_scaled] geq=lum='p(X,Y)':a='if(lte(pow(max(0,abs(X-{self.cam_scale_w/2})-{self.cam_scale_w/2-rad}),2)+pow(max(0,abs(Y-{self.cam_scale_h/2})-{self.cam_scale_h/2-rad}),2),{rad*rad}),255,0)' [cam];")
        else:
            filters.append("[cam_scaled] null [cam];")

        filters.append(f"[0:v][cam] overlay=W-w-{self.cam_margin_x}:{self.cam_margin_y} [bg];")
        
        c_size = self.cursor_scale
        cursor_pads = []
        for i in range(11):
            filters.append(f"[{i+3}:v] scale={c_size}:{c_size}:force_original_aspect_ratio=decrease, pad={c_size}:{c_size}:(ow-iw)/2:(oh-ih)/2:color=black@0 [c{i}];")
            cursor_pads.append(f"[c{i}]")
        
        filters.append(f"{''.join(cursor_pads)} vstack=inputs=11 [atlas];")
        filters.append(f"[atlas] crop={c_size}:{c_size}:0:'({id_expr})*{c_size}' [cursor];")
        filters.append(f"[bg][cursor] overlay=x='{x_expr}':y='{y_expr}':eval=frame{caption_filter} [outv];")
        
        filter_file = "filter_script_v2.txt"
        with open(filter_file, 'w', encoding="utf-8") as f: f.write("\n".join(filters))

        cmd = ['ffmpeg', '-y', *inputs, '-/filter_complex', filter_file, '-map', '[outv]', '-map', '2:a', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-c:a', 'aac', '-b:a', '128k']
        if duration_limit: cmd.extend(['-t', str(duration_limit)])
        cmd.append(output_file)
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)
        output_log = []
        for line in process.stdout:
            output_log.append(line)
            if "frame=" in line: print(line.strip(), end='\r')
        process.wait()
        return process.returncode == 0