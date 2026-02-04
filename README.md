# Gemini Video Renderer Ultimate (Cap.so Alternative)

Tool rendering video berbasis FFmpeg yang dioptimalkan untuk memproses rekaman layar dari aplikasi **Cap.so desktop**. Menghasilkan video yang lebih smooth dan profesional dengan bantuan AI.

## 🚀 Fitur Utama
- **Smooth Cursor Interpolation**: Pergerakan kursor yang mengalir mulus menggunakan algoritma LERP (Linear Interpolation).
- **AI Auto Caption**: Transkripsi otomatis Bahasa Indonesia menggunakan **OpenAI Whisper**.
- **Faster-Whisper Integration**: Dukungan model dari Hugging Face untuk transkripsi 4x lebih cepat.
- **Dynamic Cursor System**: Berganti jenis kursor (pointer, hand, text) secara otomatis sesuai data rekaman.
- **PRO GUI**: Antarmuka desktop untuk kustomisasi ukuran kamera, ukuran kursor, bentuk crop, dan gaya subtitle.

## 🛠️ Persyaratan Sistem
- **Python 3.10+**
- **FFmpeg**: Terinstal di sistem dan terdaftar di PATH.

## 📦 Instalasi
1. Clone repository ini.
2. Instal library yang dibutuhkan:
```powershell
# Dasar (Wajib)
pip install openai-whisper

# Untuk performa AI lebih cepat (Opsional)
pip install faster-whisper
```

## 📋 Cara Penggunaan
1. Jalankan aplikasi: `python main_gui.py`.
2. Pilih folder proyek yang berisi data rekaman Cap.so.
3. Atur konfigurasi visual dan AI di panel Settings.
4. Klik **Render**.

## 📂 Struktur Folder
Proyek ini mengharapkan struktur input sebagai berikut:
```text
[Folder Proyek]/
├── cursors/             # Gambar kursor (cursor_0.png s/d cursor_10.png)
├── segments/
│   └── segment-0/       # File rekaman mentah
│       ├── camera.mp4
│       ├── display.mp4
│       ├── audio-input.ogg
│       └── cursor.json  # Metadata pergerakan kursor
├── main_gui.py          # Aplikasi GUI
└── video_engine.py      # Mesin Render
```

---
*Dibuat secara otomatis oleh Gemini CLI Agent.*