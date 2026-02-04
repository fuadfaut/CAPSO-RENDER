import json
import subprocess
import os
import sys
import math
import shutil

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
        self.whisper_model = "base" 
        self.use_faster_whisper = False
        
        # Hardware Detection
        self.has_cuda = self._check_cuda()
        self.has_nvenc = self._check_nvenc()

    def _check_cuda(self):
        """Check if NVIDIA GPU is available AND PyTorch can access it"""
        try:
            import torch
            # Primary check: Can Torch actually see the GPU?
            if torch.cuda.is_available():
                return True
            else:
                return False
        except ImportError:
            # If torch isn't installed yet (rare here), fallback to system check
            # But this is risky if torch is CPU-only. Better to assume False.
            return False

    def _check_nvenc(self):
        """Check if FFmpeg supports NVIDIA Hardware Encoding"""
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
        
        # Determine Device
        device = "cuda" if self.has_cuda else "cpu"
        compute_type = "float16" if self.has_cuda else "int8"
        log(f"[AI] Hardware Acceleration: {'ENABLED (GPU)' if self.has_cuda else 'DISABLED (CPU)'}")
        
        if self.use_faster_whisper:
            try:
                from faster_whisper import WhisperModel
                log(f"[AI] Loading Faster-Whisper ({self.whisper_model}) on {device}...")
                model = WhisperModel(self.whisper_model, device=device, compute_type=compute_type)
                
                log("[AI] Transcribing audio...")
                segments, info = model.transcribe(audio_path, language="id", beam_size=5)
                
                count = 0
                for s in segments:
                    count += 1
                    if count % 10 == 0: log(f"[AI] Processed {count} lines...")
                    segments_data.append({'start': s.start, 'end': s.end, 'text': s.text})
                    
            except ImportError:
                log("faster-whisper not installed, falling back to standard whisper...")
                self.use_faster_whisper = False

        if not self.use_faster_whisper:
            try:
                import whisper
                log(f"[AI] Loading Standard Whisper ({self.whisper_model}) on {device}...")
                model = whisper.load_model(self.whisper_model, device=device)
                
                log("[AI] Transcribing audio (standard model)...")
                # Whisper standard handles FP16 warning automatically if on CPU
                result = model.transcribe(audio_path, language="id", verbose=False)
                segments_data = result['segments']
                log(f"[AI] Transcription complete. Found {len(segments_data)} segments.")
                
            except ImportError:
                log("\nError: Whisper libraries not found. Run: pip install openai-whisper")
                return None

        # Saving Files
        ass_path = "captions.ass"
        srt_path = "captions.srt"
        
        with open(ass_path, "w", encoding="utf-8") as f_ass, open(srt_path, "w", encoding="utf-8") as f_srt:
            f_ass.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n")
            f_ass.write("[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
            f_ass.write(f"Style: Default,{self.caption_font},{self.caption_size},{self.caption_color},{self.caption_outline_color},1,2,0,2,10,10,{self.caption_pos},1\n\n")
            f_ass.write("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            
            count = 1
            for segment in segments_data:
                text = segment['text'].strip()
                # ASS
                start_ass = self._format_ass_time(segment['start'])
                end_ass = self._format_ass_time(segment['end'])
                f_ass.write(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{text}\n")
                # SRT
                start_srt = self._format_srt_time(segment['start'])
                end_srt = self._format_srt_time(segment['end'])
                f_srt.write(f"{count}\n{start_srt} --> {end_srt}\n{text}\n\n")
                count += 1
        
        log(f"[AI] Saved: {ass_path} & {srt_path}")
        return ass_path

    def _format_ass_time(self, seconds):
        td = float(seconds)
        h, m, s = int(td // 3600), int((td % 3600) // 60), td % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    def _format_srt_time(self, seconds):
        td = float(seconds)
        h = int(td // 3600)
        m = int((td % 3600) // 60)
        s = int(td % 60)
        ms = int((td - int(td)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def generate_script(self, output_file="output_rendered.mp4", duration_limit=None, callback=None):
        def log(msg):
            if callback: callback(msg)
            else: print(msg.strip())

        caption_filter = ""
        if self.enable_caption:
            ass_file = self.generate_captions(callback=log)
            if ass_file:
                escaped_ass = ass_file.replace(":", "\\:").replace("\\", "/")
                caption_filter = f", subtitles='{escaped_ass}'"

        cursor_json_path = os.path.join(self.segment_dir, 'cursor.json')
        log(f"Loading cursor data...")
        with open(cursor_json_path, 'r') as f:
            data = json.load(f)

        moves = data.get('moves', [])
        if duration_limit:
            moves = [m for m in moves if m['time_ms']/1000.0 <= duration_limit + 1.0]
        if not moves: 
            log("Error: No cursor movements found!")
            return False
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
        # Camera
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
        
        # Cursor
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

        # Determine Video Encoder
        v_codec = "libx264"
        if self.has_nvenc:
            v_codec = "h264_nvenc"
            log("[Render] NVIDIA NVENC Detected: Using GPU Acceleration for Video Encoding.")
        else:
            log("[Render] No GPU Encoder detected. Using CPU (libx264).")

        cmd = [
            'ffmpeg', '-y',
            *inputs,
            '-/filter_complex', filter_file,
            '-map', '[outv]',
            '-map', '2:a',
            '-c:v', v_codec,
            '-preset', 'p4' if v_codec == "h264_nvenc" else 'veryfast', # NVENC uses p1-p7
            '-crf', '23' if v_codec == "libx264" else '0', # NVENC doesn't assume CRF the same way, but let's assume default q control
            '-cq', '23' if v_codec == "h264_nvenc" else '0', # NVENC constant quality
            '-c:a', 'aac', '-b:a', '128k'
        ]
        
        if v_codec == "h264_nvenc":
            # Remove CRF for NVENC as it uses -cq usually with -rc vbr
            cmd = [x for x in cmd if x != '-crf' and x != '0']
        else:
            # Remove NVENC specific flags if using CPU
            cmd = [x for x in cmd if x != '-cq' and x != 'p4']

        if duration_limit: cmd.extend(['-t', str(duration_limit)])
        cmd.append(output_file)
        
        log(f"Starting FFmpeg...")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)
        
        output_log = []
        for line in process.stdout:
            output_log.append(line)
            if "frame=" in line: print(line.strip(), end='\r')
        process.wait()
        
        if process.returncode != 0:
            print("\nError Output:")
            print("".join(output_log[-20:]))
            return False
        return True

if __name__ == "__main__":
    renderer = VideoRenderer(os.getcwd())
    renderer.generate_script("output_smooth_test.mp4", duration_limit=60)