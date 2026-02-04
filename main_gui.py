import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, font
import os
import threading
import datetime
import json
from video_engine import VideoRenderer

# Setup Theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

CONFIG_FILE = "settings.conf"

class RenderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Gemini Video Renderer Ultimate")
        self.geometry("850x800")
        
        # --- Variables ---
        self.project_dir = tk.StringVar()
        
        # We use IntVars mainly for internal state, but won't bind them directly to Entry to avoid TclError
        self.cam_scale_var = tk.IntVar(value=280)
        self.cursor_scale_var = tk.IntVar(value=48)
        self.cap_pos_var = tk.IntVar(value=50)
        
        self.cam_shape = tk.StringVar(value="rounded")
        self.cam_pos = tk.StringVar(value="Top-Right")
        
        self.enable_caption = tk.BooleanVar(value=False)
        self.use_faster = tk.BooleanVar(value=False)
        self.use_hevc = tk.BooleanVar(value=False)
        self.whisper_model = tk.StringVar(value="base")
        self.font_name = tk.StringVar(value="Arial")
        self.font_size = tk.IntVar(value=24) # Still safe for Entry if validated
        
        # Load Config
        self.load_settings()
        
        self.is_rendering = False
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

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
        
        # Smart Sliders (No direct textvariable binding for Entry to avoid crash)
        self.create_smart_slider(frame_vis, "Camera Width:", self.cam_scale_var, 100, 800, 1)
        self.create_smart_slider(frame_vis, "Cursor Size:", self.cursor_scale_var, 16, 256, 2)
        
        # Shape
        ctk.CTkLabel(frame_vis, text="Camera Shape:").grid(row=3, column=0, sticky="w", padx=10, pady=5)
        shape_frame = ctk.CTkFrame(frame_vis, fg_color="transparent")
        shape_frame.grid(row=3, column=1, columnspan=2, sticky="w")
        for s in ["Rounded", "Circle", "Rect"]: 
            ctk.CTkRadioButton(shape_frame, text=s, variable=self.cam_shape, value=s.lower()).pack(side="left", padx=10)

        # Position
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

        # Font Settings
        system_fonts = sorted(list(font.families()))
        ctk.CTkLabel(frame_ai, text="Font:").grid(row=2, column=0, sticky="w", padx=10)
        font_cb = ctk.CTkComboBox(frame_ai, variable=self.font_name, values=system_fonts, width=150)
        font_cb.grid(row=2, column=1, sticky="w", padx=10)
        if "Arial" in system_fonts and not self.font_name.get(): font_cb.set("Arial")
        
        ctk.CTkLabel(frame_ai, text="Size:").grid(row=2, column=2, sticky="e", padx=5)
        # For font size, simple entry is enough, we handle validation manually if needed
        ctk.CTkEntry(frame_ai, textvariable=self.font_size, width=50).grid(row=2, column=3, sticky="w", padx=10)

        # Caption Position Slider
        self.create_smart_slider(frame_ai, "Bottom Margin:", self.cap_pos_var, 0, 500, 3)

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

    def create_smart_slider(self, parent, label_text, variable, from_val, to_val, row_idx):
        ctk.CTkLabel(parent, text=label_text).grid(row=row_idx, column=0, sticky="w", padx=10)
        
        # 1. Entry (We don't use textvariable to avoid TclError crash on empty string)
        entry = ctk.CTkEntry(parent, width=60)
        entry.grid(row=row_idx, column=2, padx=10, sticky="w")
        entry.insert(0, str(variable.get())) # Init value

        # 2. Slider
        def on_slider(val):
            int_val = int(val)
            variable.set(int_val)
            # Update entry without triggering events
            entry.delete(0, "end")
            entry.insert(0, str(int_val))

        slider = ctk.CTkSlider(parent, from_=from_val, to=to_val, command=on_slider)
        slider.set(variable.get())
        slider.grid(row=row_idx, column=1, sticky="ew", padx=10)

        # 3. Sync Entry -> Slider
        def on_entry(event=None):
            val_str = entry.get()
            if val_str.isdigit():
                val = int(val_str)
                # Clamp
                if val < from_val: val = from_val
                if val > to_val: val = to_val
                
                variable.set(val)
                slider.set(val)
                
                # Reformatted update
                if str(val) != val_str:
                    entry.delete(0, "end")
                    entry.insert(0, str(val))
            else:
                # Revert if invalid
                entry.delete(0, "end")
                entry.insert(0, str(variable.get()))
        
        entry.bind("<Return>", on_entry)
        entry.bind("<FocusOut>", on_entry)

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.project_dir.set(data.get("project_dir", ""))
                    self.cam_scale_var.set(data.get("cam_scale", 280))
                    self.cursor_scale_var.set(data.get("cursor_scale", 48))
                    self.cam_shape.set(data.get("cam_shape", "rounded"))
                    self.cam_pos.set(data.get("cam_pos", "Top-Right"))
                    self.enable_caption.set(data.get("enable_caption", False))
                    self.use_faster.set(data.get("use_faster", False))
                    self.use_hevc.set(data.get("use_hevc", False))
                    self.whisper_model.set(data.get("whisper_model", "base"))
                    self.font_name.set(data.get("font_name", "Arial"))
                    self.font_size.set(data.get("font_size", 24))
                    self.cap_pos_var.set(data.get("cap_pos", 50))
            except Exception as e:
                print(f"Error loading config: {e}")

    def save_settings(self):
        data = {
            "project_dir": self.project_dir.get(),
            "cam_scale": self.cam_scale_var.get(),
            "cursor_scale": self.cursor_scale_var.get(),
            "cam_shape": self.cam_shape.get(),
            "cam_pos": self.cam_pos.get(),
            "enable_caption": self.enable_caption.get(),
            "use_faster": self.use_faster.get(),
            "use_hevc": self.use_hevc.get(),
            "whisper_model": self.whisper_model.get(),
            "font_name": self.font_name.get(),
            "font_size": self.font_size.get(),
            "cap_pos": self.cap_pos_var.get()
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def on_close(self):
        self.save_settings()
        self.destroy()

    def _log(self, msg):
        self.log_area.configure(state="normal")
        self.log_area.insert("end", msg.strip() + "\n")
        self.log_area.see("end")
        self.log_area.configure(state="disabled")

    def _browse_dir(self):
        d = filedialog.askdirectory()
        if d: self.project_dir.set(d)

    def _start_render(self, limit=None):
        self.save_settings()
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
            # Map vars
            renderer.cam_scale_w = self.cam_scale_var.get()
            renderer.cam_scale_h = int(renderer.cam_scale_w * (9/16))
            renderer.cursor_scale = self.cursor_scale_var.get()
            renderer.cam_shape = self.cam_shape.get()
            renderer.cam_position = self.cam_pos.get()
            renderer.enable_caption = self.enable_caption.get()
            renderer.whisper_model = self.whisper_model.get()
            renderer.use_faster_whisper = self.use_faster.get()
            renderer.caption_font = self.font_name.get()
            renderer.caption_size = self.font_size.get()
            renderer.caption_pos = self.cap_pos_var.get()
            
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