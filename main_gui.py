import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, font
import os
import threading
import datetime
from video_engine import VideoRenderer

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class RenderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Gemini Video Renderer Ultimate")
        self.geometry("800x800")
        
        # Variables
        self.project_dir = tk.StringVar()
        self.cam_scale = tk.IntVar(value=280)
        self.cursor_scale = tk.IntVar(value=48)
        self.cam_shape = tk.StringVar(value="rounded")
        self.cam_pos = tk.StringVar(value="Top-Right")
        
        self.enable_caption = tk.BooleanVar(value=False)
        self.use_faster = tk.BooleanVar(value=False)
        self.use_hevc = tk.BooleanVar(value=False)
        self.whisper_model = tk.StringVar(value="base")
        self.font_name = tk.StringVar(value="Arial")
        self.font_size = tk.IntVar(value=24)
        self.cap_pos = tk.IntVar(value=50)
        
        self.is_rendering = False
        self._create_widgets()

    def _create_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        # 1. Project Selection
        frame_dir = ctk.CTkFrame(self)
        frame_dir.grid(row=0, column=0, padx=20, pady=(20,10), sticky="ew")
        ctk.CTkLabel(frame_dir, text="Project Directory", font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        dir_inner = ctk.CTkFrame(frame_dir, fg_color="transparent")
        dir_inner.pack(fill="x", padx=10, pady=(0,10))
        ctk.CTkEntry(dir_inner, textvariable=self.project_dir, placeholder_text="Select project folder...").pack(side="left", fill="x", expand=True, padx=(0,10))
        ctk.CTkButton(dir_inner, text="Browse", width=80, command=self._browse_dir).pack(side="right")

        # 2. Visual Settings
        frame_vis = ctk.CTkFrame(self)
        frame_vis.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        ctk.CTkLabel(frame_vis, text="Visual Settings", font=("Roboto", 14, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=5)
        
        ctk.CTkLabel(frame_vis, text="Camera Width:").grid(row=1, column=0, sticky="w", padx=10)
        ctk.CTkSlider(frame_vis, from_=100, to=600, variable=self.cam_scale, command=lambda v: self.cam_scale.set(int(v))).grid(row=1, column=1, sticky="ew", padx=10)
        ctk.CTkLabel(frame_vis, textvariable=self.cam_scale, width=40).grid(row=1, column=2, padx=10)
        
        ctk.CTkLabel(frame_vis, text="Cursor Size:").grid(row=2, column=0, sticky="w", padx=10)
        ctk.CTkSlider(frame_vis, from_=16, to=128, variable=self.cursor_scale, command=lambda v: self.cursor_scale.set(int(v))).grid(row=2, column=1, sticky="ew", padx=10)
        ctk.CTkLabel(frame_vis, textvariable=self.cursor_scale, width=40).grid(row=2, column=2, padx=10)
        
        ctk.CTkLabel(frame_vis, text="Camera Shape:").grid(row=3, column=0, sticky="w", padx=10, pady=5)
        shape_frame = ctk.CTkFrame(frame_vis, fg_color="transparent")
        shape_frame.grid(row=3, column=1, columnspan=2, sticky="w")
        for s in ["Rounded", "Circle", "Rect"]: ctk.CTkRadioButton(shape_frame, text=s, variable=self.cam_shape, value=s.lower()).pack(side="left", padx=10)

        ctk.CTkLabel(frame_vis, text="Camera Pos:").grid(row=4, column=0, sticky="w", padx=10, pady=5)
        pos_opts = ["Top-Left", "Top-Right", "Bottom-Left", "Bottom-Right", "Top-Center", "Bottom-Center"]
        ctk.CTkComboBox(frame_vis, variable=self.cam_pos, values=pos_opts).grid(row=4, column=1, sticky="w", padx=10)

        # 3. AI Settings
        frame_ai = ctk.CTkFrame(self)
        frame_ai.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        ctk.CTkLabel(frame_ai, text="AI Auto Caption", font=("Roboto", 14, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=5)
        ctk.CTkCheckBox(frame_ai, text="Enable Caption", variable=self.enable_caption).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        ctk.CTkCheckBox(frame_ai, text="Use Faster-Whisper", variable=self.use_faster).grid(row=1, column=1, padx=10, pady=5, sticky="w")
        ctk.CTkLabel(frame_ai, text="Model:").grid(row=1, column=2, sticky="e", padx=5)
        ctk.CTkComboBox(frame_ai, variable=self.whisper_model, values=["tiny", "base", "small", "medium"], width=90).grid(row=1, column=3, sticky="w", padx=10)

        system_fonts = sorted(list(font.families()))
        ctk.CTkLabel(frame_ai, text="Font:").grid(row=2, column=0, sticky="w", padx=10)
        font_cb = ctk.CTkComboBox(frame_ai, variable=self.font_name, values=system_fonts, width=150)
        font_cb.grid(row=2, column=1, sticky="w", padx=10)
        if "Arial" in system_fonts: font_cb.set("Arial")
        ctk.CTkLabel(frame_ai, text="Size:").grid(row=2, column=2, sticky="e", padx=5)
        ctk.CTkEntry(frame_ai, textvariable=self.font_size, width=50).grid(row=2, column=3, sticky="w", padx=10)
        
        ctk.CTkLabel(frame_ai, text="Pos (Y):").grid(row=3, column=0, sticky="w", padx=10)
        ctk.CTkSlider(frame_ai, from_=10, to=500, variable=self.cap_pos, command=lambda v: self.cap_pos.set(int(v))).grid(row=3, column=1, sticky="ew", padx=10)
        ctk.CTkLabel(frame_ai, textvariable=self.cap_pos, width=40).grid(row=3, column=2, padx=10)

        # 4. Render Settings
        frame_ren = ctk.CTkFrame(self)
        frame_ren.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        ctk.CTkLabel(frame_ren, text="Render Options", font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        ctk.CTkCheckBox(frame_ren, text="Use H.265 (HEVC) - Smaller File Size", variable=self.use_hevc).pack(anchor="w", padx=10, pady=5)

        # 5. Buttons
        frame_act = ctk.CTkFrame(self, fg_color="transparent")
        frame_act.grid(row=4, column=0, padx=20, pady=10, sticky="ew")
        self.btn_test = ctk.CTkButton(frame_act, text="Test Render (1 min)", fg_color="#2b2b2b", border_width=2, command=lambda: self._start_render(60))
        self.btn_test.pack(side="left", fill="x", expand=True, padx=(0,10))
        self.btn_render = ctk.CTkButton(frame_act, text="RENDER FULL VIDEO", font=("Roboto", 16, "bold"), height=40, command=self._start_render)
        self.btn_render.pack(side="right", fill="x", expand=True, padx=(10,0))

        # 6. Log
        self.log_area = ctk.CTkTextbox(self, height=150)
        self.log_area.grid(row=5, column=0, padx=20, pady=(0,20), sticky="nsew")
        self.log_area.configure(state="disabled")

    def _log(self, msg):
        self.log_area.configure(state="normal")
        self.log_area.insert("end", msg.strip() + "\n")
        self.log_area.see("end")
        self.log_area.configure(state="disabled")

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
        self.btn_render.configure(state="disabled"); self.btn_test.configure(state="disabled")
        self.log_area.configure(state="normal"); self.log_area.delete("1.0", "end"); self.log_area.configure(state="disabled")
        self._log("Initializing Engine...")
        threading.Thread(target=self._render_task, args=(limit,), daemon=True).start()

    def _render_task(self, limit):
        try:
            renderer = VideoRenderer(self.project_dir.get())
            renderer.cam_scale_w = self.cam_scale.get()
            renderer.cam_scale_h = int(renderer.cam_scale_w * (9/16))
            renderer.cursor_scale = self.cursor_scale.get()
            renderer.cam_shape = self.cam_shape.get()
            renderer.cam_position = self.cam_pos.get()
            renderer.enable_caption = self.enable_caption.get()
            renderer.whisper_model = self.whisper_model.get()
            renderer.use_faster_whisper = self.use_faster.get()
            renderer.caption_font = self.font_name.get()
            renderer.caption_size = self.font_size.get()
            renderer.caption_pos = self.cap_pos.get()
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            mode = "test" if limit else "full"
            out = f"render_{timestamp}_{mode}.mp4"
            
            def log_callback(msg): self.after(0, lambda: self._log(msg))
            success = renderer.generate_script(out, duration_limit=limit, callback=log_callback, use_hevc=self.use_hevc.get())
            if success: self.after(0, lambda: messagebox.showinfo("Success", f"Render Complete!\nSaved: {out}"))
            else: self.after(0, lambda: messagebox.showerror("Failed", "Render Failed. See Log."))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._log(f"[CRITICAL ERROR] {err}"))
        finally:
            self.is_rendering = False
            self.after(0, lambda: self.btn_render.configure(state="normal"))
            self.after(0, lambda: self.btn_test.configure(state="normal"))

if __name__ == "__main__":
    app = RenderApp()
    app.project_dir.set(os.getcwd())
    app.mainloop()