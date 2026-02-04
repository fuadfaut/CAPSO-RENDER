import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font
import os
import threading
import datetime
from video_engine import VideoRenderer

class RenderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gemini Video Renderer Ultimate")
        self.root.geometry("700x700")
        
        # Variables
        self.project_dir = tk.StringVar()
        self.cam_scale = tk.IntVar(value=280)
        self.cursor_scale = tk.IntVar(value=48)
        self.cam_shape = tk.StringVar(value="rounded")
        
        self.enable_caption = tk.BooleanVar(value=False)
        self.use_faster = tk.BooleanVar(value=False)
        self.whisper_model = tk.StringVar(value="base")
        self.font_name = tk.StringVar(value="Arial")
        self.font_size = tk.IntVar(value=24)
        self.cap_pos = tk.IntVar(value=50)
        
        self.is_rendering = False
        self._create_widgets()

    def _create_widgets(self):
        # 1. Project Selection
        frame_dir = ttk.LabelFrame(self.root, text="Project Directory", padding=10)
        frame_dir.pack(fill="x", padx=10, pady=5)
        ttk.Entry(frame_dir, textvariable=self.project_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(frame_dir, text="Browse", command=self._browse_dir).pack(side="right", padx=5)

        # 2. Settings Visual
        frame_settings = ttk.LabelFrame(self.root, text="Visual Settings", padding=10)
        frame_settings.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(frame_settings, text="Camera Width:").grid(row=0, column=0, sticky="w")
        ttk.Scale(frame_settings, from_=100, to=600, variable=self.cam_scale, orient="horizontal", command=lambda v: self.cam_scale.set(int(float(v)))).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Label(frame_settings, textvariable=self.cam_scale).grid(row=0, column=2, sticky="w")

        ttk.Label(frame_settings, text="Cursor Size:").grid(row=1, column=0, sticky="w")
        ttk.Scale(frame_settings, from_=16, to=128, variable=self.cursor_scale, orient="horizontal", command=lambda v: self.cursor_scale.set(int(float(v)))).grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Label(frame_settings, textvariable=self.cursor_scale).grid(row=1, column=2, sticky="w")

        ttk.Label(frame_settings, text="Camera Shape:").grid(row=2, column=0, sticky="w")
        fs = ttk.Frame(frame_settings); fs.grid(row=2, column=1, columnspan=2, sticky="w")
        for s in ["rounded", "circle", "rect"]: ttk.Radiobutton(fs, text=s.capitalize(), variable=self.cam_shape, value=s).pack(side="left", padx=5)

        # 3. AI Caption Settings
        frame_cap = ttk.LabelFrame(self.root, text="AI Auto Caption", padding=10)
        frame_cap.pack(fill="x", padx=10, pady=5)

        ttk.Checkbutton(frame_cap, text="Enable Auto Caption", variable=self.enable_caption).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(frame_cap, text="Use Faster-Whisper (Requires install)", variable=self.use_faster).grid(row=0, column=1, sticky="w")
        
        ttk.Label(frame_cap, text="Model Size:").grid(row=1, column=0, sticky="w")
        ttk.Combobox(frame_cap, textvariable=self.whisper_model, values=["tiny", "base", "small", "medium"], width=10).grid(row=1, column=1, sticky="w", padx=5)
        
        # Get System Fonts
        system_fonts = list(font.families())
        system_fonts.sort()
        
        ttk.Label(frame_cap, text="Font:").grid(row=2, column=0, sticky="w")
        # Combobox for Font
        font_cb = ttk.Combobox(frame_cap, textvariable=self.font_name, values=system_fonts, width=25, state="readonly")
        font_cb.grid(row=2, column=1, sticky="w", padx=5)
        # Set default if exists, else first available
        if "Arial" in system_fonts:
            font_cb.set("Arial")
        elif system_fonts:
            font_cb.current(0)
        
        ttk.Label(frame_cap, text="Size:").grid(row=2, column=2, sticky="w")
        ttk.Spinbox(frame_cap, from_=10, to=100, textvariable=self.font_size, width=5).grid(row=2, column=3, sticky="w")

        ttk.Label(frame_cap, text="Bottom Margin:").grid(row=3, column=0, sticky="w")
        ttk.Scale(frame_cap, from_=10, to=500, variable=self.cap_pos, orient="horizontal", command=lambda v: self.cap_pos.set(int(float(v)))).grid(row=3, column=1, sticky="ew", padx=5)
        ttk.Label(frame_cap, textvariable=self.cap_pos).grid(row=3, column=2, sticky="w")

        # 4. Actions
        frame_actions = ttk.Frame(self.root, padding=10)
        frame_actions.pack(fill="x", padx=10)
        self.btn_render = ttk.Button(frame_actions, text="Render Full Video", command=self._start_render)
        self.btn_render.pack(fill="x", pady=2)
        self.btn_test = ttk.Button(frame_actions, text="Test Render (1 min)", command=lambda: self._start_render(limit=60))
        self.btn_test.pack(fill="x")

        # 5. Log
        self.log_area = tk.Text(self.root, height=10, state="disabled")
        self.log_area.pack(fill="both", expand=True, padx=10, pady=5)

    def _log(self, msg):
        self.log_area.config(state="normal")
        self.log_area.insert("end", msg + "\n")
        self.log_area.see("end")
        self.log_area.config(state="disabled")

    def _browse_dir(self):
        d = filedialog.askdirectory()
        if d: self.project_dir.set(d)

    def _start_render(self, limit=None):
        if self.is_rendering: return
        p_dir = self.project_dir.get()
        if not p_dir or not os.path.exists(p_dir):
            messagebox.showerror("Error", "Select a valid project directory.")
            return
        self.is_rendering = True
        self.btn_render.config(state="disabled"); self.btn_test.config(state="disabled")
        self._log("Engine started...")
        threading.Thread(target=self._render_task, args=(limit,), daemon=True).start()

    def _render_task(self, limit):
        try:
            renderer = VideoRenderer(self.project_dir.get())
            renderer.cam_scale_w = self.cam_scale.get()
            renderer.cam_scale_h = int(renderer.cam_scale_w * (9/16))
            renderer.cursor_scale = self.cursor_scale.get()
            renderer.cam_shape = self.cam_shape.get()
            renderer.enable_caption = self.enable_caption.get()
            renderer.whisper_model = self.whisper_model.get()
            renderer.use_faster_whisper = self.use_faster.get()
            renderer.caption_font = self.font_name.get()
            renderer.caption_size = self.font_size.get()
            renderer.caption_pos = self.cap_pos.get()
            
            # Generate Timestamp Filename
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            mode = "test" if limit else "full"
            out = f"render_{timestamp}_{mode}.mp4"
            
            if renderer.generate_script(out, duration_limit=limit):
                self.root.after(0, lambda: self._log(f"Done! File: {out}"))
                self.root.after(0, lambda: messagebox.showinfo("Done", "Render Complete!"))
            else:
                self.root.after(0, lambda: self._log("Render failed. Check terminal."))
        except Exception as e:
            self.root.after(0, lambda: self._log(f"Error: {e}"))
        finally:
            self.is_rendering = False
            self.root.after(0, lambda: self.btn_render.config(state="normal"))
            self.root.after(0, lambda: self.btn_test.config(state="normal"))

if __name__ == "__main__":
    root = tk.Tk()
    app = RenderApp(root)
    app.project_dir.set(os.getcwd())
    root.mainloop()
