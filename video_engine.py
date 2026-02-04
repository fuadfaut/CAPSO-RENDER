import json
import subprocess
import os
import sys
import math
import shutil

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
        self.cam_position = "Top-Right" # New setting
        
        # Caption Settings
        self.enable_caption = False
        self.caption_font = "Arial"
        self.caption_size = 24
        self.caption_color = "&H00FFFFFF"
        self.caption_outline_color = "&H00000000"
        self.caption_pos = 50
        self.whisper_model = "base" 
        self.use_faster_whisper = False
        
        self.has_cuda = self._check_cuda()
        self.has_nvenc = self._check_nvenc()

    def _check_cuda(self):
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def _check_nvenc(self):
        try:
            res = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], capture_output=True, text=True)
            return "h264_nvenc" in res.stdout
        except:
            return False

    def build_lerp_tree(self, times, values, start, end):
        if end - start == 1:
            t1, t2 = times[start], times[end]
            v1, v2 = values[start], values[end]
            if t2 == t1: return f"{v1:.2f}"
            slope = (v2 - v1) / (t2 - t1)
            return f"({v1:.2f}+{slope:.4f}*(t-{t1:.4f}))"
        mid = (start + end) // 2
        return f"if(lt(t,{times[mid]:.4f}),{self.build_lerp_tree(times, values, start, mid)},{self.build_lerp_tree(times, values, mid, end)})"

    def generate_captions(self, callback=None):
        def log(msg):
            if callback: callback(msg)
            else: print(msg)

        audio_path = os.path.join(self.segment_dir, 'audio-input.ogg')
        if not os.path.exists(audio_path): return None

        segments_data = []
        device = "cuda" if self.has_cuda else "cpu"
        compute_type = "float16" if self.has_cuda else "int8"
        log(f"[AI] Hardware Acceleration: {'ENABLED (GPU)' if self.has_cuda else 'DISABLED (CPU)'}")
        
        if self.use_faster_whisper:
            try:
                from faster_whisper import WhisperModel
                log(f"[AI] Loading Faster-Whisper ({self.whisper_model}) on {device}...")
                model = WhisperModel(self.whisper_model, device=device, compute_type=compute_type)
                segments, info = model.transcribe(audio_path, language="id", beam_size=5)
                count = 0
                for s in segments:
                    count += 1
                    if count % 10 == 0: log(f"[AI] Processed {count} lines...")
                    segments_data.append({'start': s.start, 'end': s.end, 'text': s.text})
            except ImportError:
                log("faster-whisper not installed...")
                self.use_faster_whisper = False

        if not self.use_faster_whisper:
            try:
                import whisper
                log(f"[AI] Loading Standard Whisper ({self.whisper_model}) on {device}...")
                model = whisper.load_model(self.whisper_model, device=device)
                result = model.transcribe(audio_path, language="id", verbose=False)
                segments_data = result['segments']
            except ImportError:
                return None

        ass_path = "captions.ass"
        srt_path = "captions.srt"
        with open(ass_path, "w", encoding="utf-8") as f_ass, open(srt_path, "w", encoding="utf-8") as f_srt:
            f_ass.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
            f_ass.write(f"Style: Default,{self.caption_font},{self.caption_size},{self.caption_color},{self.caption_outline_color},1,2,0,2,10,10,{self.caption_pos},1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            count = 1
            for segment in segments_data:
                text = segment['text'].strip()
                start_ass = self._format_ass_time(segment['start'])
                end_ass = self._format_ass_time(segment['end'])
                f_ass.write(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{text}\n")
                start_srt = self._format_srt_time(segment['start'])
                end_srt = self._format_srt_time(segment['end'])
                f_srt.write(f"{count}\n{start_srt} --> {end_srt}\n{text}\n\n")
                count += 1
        log(f"[AI] Saved captions to {ass_path}")
        return ass_path

    def _format_ass_time(self, seconds):
        td = float(seconds)
        h, m, s = int(td // 3600), int((td % 3600) // 60), td % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    def _format_srt_time(self, seconds):
        td = float(seconds)
        h, m, s = int(td // 3600), int((td % 3600) // 60), int(td % 60)
        ms = int((td - int(td)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def generate_script(self, output_file="output_rendered.mp4", duration_limit=None, callback=None, use_hevc=False):
        def log(msg):
            if callback: callback(msg)
            else: print(msg.strip())

        caption_filter = ""
        if self.enable_caption:
            log("[AI] Generating captions...")
            ass_file = self.generate_captions(callback=log)
            if ass_file:
                escaped_ass = ass_file.replace(":", "\\:").replace("\\", "/")
                caption_filter = f", subtitles='{escaped_ass}'"

        cursor_json_path = os.path.join(self.segment_dir, 'cursor.json')
        log(f"Loading data...")
        with open(cursor_json_path, 'r') as f: data = json.load(f)

        moves = data.get('moves', [])
        if duration_limit: moves = [m for m in moves if m['time_ms']/1000.0 <= duration_limit + 1.0]
        if not moves: return False
        moves.sort(key=lambda x: x['time_ms'])

        times = [m['time_ms'] / 1000.0 for m in moves]
        xs = [m['x'] * 1920 for m in moves]
        ys = [m['y'] * 1080 for m in moves]
        ids = [int(m['cursor_id']) for m in moves]

        log(f"Processing {len(moves)} cursor points...")
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
        
        # --- 1. Camera Processing (Shadow & Shape) ---
        # Scale & Shape
        filters.append(f"[1:v] scale={self.cam_scale_w}:{self.cam_scale_h}, format=rgba [cam_scaled];")
        if self.cam_shape == "circle":
            r = min(self.cam_scale_w, self.cam_scale_h) / 2
            filters.append(f"[cam_scaled] geq=lum='p(X,Y)':a='if(lte(pow(X-{self.cam_scale_w/2},2)+pow(Y-{self.cam_scale_h/2},2),{r*r}),255,0)' [cam_shape];")
        elif self.cam_shape == "rounded":
            rad = 20
            filters.append(f"[cam_scaled] geq=lum='p(X,Y)':a='if(lte(pow(max(0,abs(X-{self.cam_scale_w/2})-{self.cam_scale_w/2-rad}),2)+pow(max(0,abs(Y-{self.cam_scale_h/2})-{self.cam_scale_h/2-rad}),2),{rad*rad}),255,0)' [cam_shape];")
        else:
            filters.append("[cam_scaled] copy [cam_shape];")

        # Add Shadow to Camera
        # Create a black box of same size, blur it, then overlay camera on top of it (with offset)
        # To simplify, we'll extract alpha, color it black, blur, then offset.
        # But for efficiency, we can assume a box shadow.
        # Efficient Shadow: extract alpha, make it black, blur.
        filters.append(f"[cam_shape] split [cam_fg][cam_bg];")
        filters.append(f"[cam_bg] drawbox=c=black@0.4:t=fill, boxblur=10 [cam_shadow];")
        # Shift shadow slightly (+4, +4) relative to camera.
        # We'll handle this in the final overlay stage by overlaying shadow first.

        # --- 2. Camera Overlay (Positioning) ---
        margin_x, margin_y = self.cam_margin_x, self.cam_margin_y
        
        # Calculate coordinates string
        if "Top-Left" in self.cam_position:
            cam_x, cam_y = f"{margin_x}", f"{margin_y}"
        elif "Top-Right" in self.cam_position:
            cam_x, cam_y = f"W-w-{margin_x}", f"{margin_y}"
        elif "Bottom-Left" in self.cam_position:
            cam_x, cam_y = f"{margin_x}", f"H-h-{margin_y}"
        elif "Bottom-Right" in self.cam_position:
            cam_x, cam_y = f"W-w-{margin_x}", f"H-h-{margin_y}"
        elif "Top-Center" in self.cam_position:
            cam_x, cam_y = f"(W-w)/2", f"{margin_y}"
        elif "Bottom-Center" in self.cam_position:
            cam_x, cam_y = f"(W-w)/2", f"H-h-{margin_y}"
        else: # Default Top-Right
            cam_x, cam_y = f"W-w-{margin_x}", f"{margin_y}"

        # Overlay Shadow then Camera
        # Shadow offset 5px
        filters.append(f"[0:v][cam_shadow] overlay={cam_x}+5:{cam_y}+5 [bg_shadow];")
        filters.append(f"[bg_shadow][cam_fg] overlay={cam_x}:{cam_y} [bg];")
        
        # --- 3. Cursor Processing (HD & Shadow) ---
        c_size = self.cursor_scale
        cursor_pads = []
        for i in range(11):
            # Use 'flags=lanczos' for better upscaling quality
            # Add padding to hold the cursor + its shadow
            pad_size = c_size + 10 # Extra space for shadow
            filters.append(f"[{i+3}:v] scale={c_size}:{c_size}:force_original_aspect_ratio=decrease:flags=lanczos, split [c_fg{i}][c_bg{i}];")
            
            # Create shadow for cursor: fill black semi-transparent, blur
            filters.append(f"[c_bg{i}] drawbox=c=black@0.3:t=fill, boxblur=3 [c_shadow{i}];")
            
            # Merge shadow and cursor into one layer (shadow offset +2,+2)
            filters.append(f"[c_shadow{i}][c_fg{i}] overlay=x=2:y=2, pad={pad_size}:{pad_size}:0:0:color=black@0 [c_final{i}];")
            
            cursor_pads.append(f"[c_final{i}]")
        
        filters.append(f"{''.join(cursor_pads)} vstack=inputs=11 [atlas];")
        # Crop must now account for pad_size
        filters.append(f"[atlas] crop={c_size+10}:{c_size+10}:0:'({id_expr})*({c_size+10})' [cursor];")
        
        filters.append(f"[bg][cursor] overlay=x='{x_expr}':y='{y_expr}':eval=frame{caption_filter} [outv];")
        
        filter_file = "filter_script_v2.txt"
        with open(filter_file, 'w', encoding="utf-8") as f: f.write("\n".join(filters))

        if use_hevc: v_codec, desc = ("hevc_nvenc" if self.has_nvenc else "libx265"), "H.265"
        else: v_codec, desc = ("h264_nvenc" if self.has_nvenc else "libx264"), "H.264"
        log(f"[Render] Encoder: {v_codec} ({desc}) [{'GPU' if 'nvenc' in v_codec else 'CPU'}]")

        cmd = ['ffmpeg', '-y', *inputs, '-/filter_complex', filter_file, '-map', '[outv]', '-map', '2:a', '-c:v', v_codec, '-c:a', 'aac', '-b:a', '128k']
        if "nvenc" in v_codec: cmd.extend(['-preset', 'p4', '-cq', '23'])
        else: cmd.extend(['-preset', 'veryfast', '-crf', '23'])
        if duration_limit: cmd.extend(['-t', str(duration_limit)])
        cmd.append(output_file)
        
        log(f"Starting Render...")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)
        output_log = []
        for line in process.stdout:
            output_log.append(line)
            if "frame=" in line: print(line.strip(), end='\r')
        process.wait()
        
        if process.returncode != 0:
            if "nvenc" in v_codec:
                log(f"\n[WARN] GPU failed. Fallback to CPU...")
                fallback_codec = "libx265" if use_hevc else "libx264"
                cmd = ['ffmpeg', '-y', *inputs, '-/filter_complex', filter_file, '-map', '[outv]', '-map', '2:a', '-c:v', fallback_codec, '-preset', 'veryfast', '-crf', '23', '-c:a', 'aac', '-b:a', '128k']
                if duration_limit: cmd.extend(['-t', str(duration_limit)])
                cmd.append(output_file)
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)
                for line in process.stdout:
                    if "frame=" in line: print(line.strip(), end='\r')
                process.wait()
                if process.returncode == 0: return True
            print("\nError Output:"); print("".join(output_log[-20:]))
            return False
        return True

if __name__ == "__main__":
    renderer = VideoRenderer(os.getcwd())
    renderer.generate_script("output_smooth_test.mp4", duration_limit=60)