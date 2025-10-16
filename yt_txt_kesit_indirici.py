# -*- coding: utf-8 -*-
# Gerekenler:
#   pip install yt-dlp customtkinter
# FFmpeg sistem PATH'te olmalı (ffmpeg.org)

import os
import re
import threading
import subprocess
import tkinter.filedialog as fd
import tkinter as tk
import customtkinter as ctk
from datetime import datetime

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

APP_TITLE = "YouTube Kesit İndirici (TXT → Otomatik)"
DEFAULT_OUTDIR = os.path.join(os.getcwd(), "indirilen_kesitler")

# yt-dlp stdout'undan yüzde/ETA yakalamak için regex
PERCENT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)%")
ETA_RE = re.compile(r"ETA\s+([0-9:\.]+)")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("900x620")
        self.resizable(True, True)

        # --- Üst: URL & TXT & Klasör seçimi ---
        self.frm_top = ctk.CTkFrame(self, corner_radius=12, fg_color=("gray10", "gray12"))
        self.frm_top.pack(fill="x", padx=12, pady=(12, 8))

        # URL
        ctk.CTkLabel(self.frm_top, text="YouTube URL", anchor="w").grid(row=0, column=0, sticky="ew", padx=(0,8), pady=6)
        self.ent_url = ctk.CTkEntry(self.frm_top, placeholder_text="https://www.youtube.com/watch?v=...")
        self.ent_url.grid(row=0, column=1, sticky="ew", padx=(0,8), pady=6)
        self.frm_top.grid_columnconfigure(1, weight=1)

        # TXT dosyası
        ctk.CTkLabel(self.frm_top, text="Zaman Aralıkları TXT", anchor="w").grid(row=1, column=0, sticky="ew", padx=(0,8), pady=6)
        self.ent_txt = ctk.CTkEntry(self.frm_top, placeholder_text="araliklar.txt (örn: 0:58 05:55)")
        self.ent_txt.grid(row=1, column=1, sticky="ew", padx=(0,8), pady=6)
        self.btn_browse_txt = ctk.CTkButton(self.frm_top, text="Seç", command=self.select_txt)
        self.btn_browse_txt.grid(row=1, column=2, padx=(0,0), pady=6)

        # Çıkış klasörü
        ctk.CTkLabel(self.frm_top, text="Çıkış Klasörü", anchor="w").grid(row=2, column=0, sticky="ew", padx=(0,8), pady=6)
        self.ent_out = ctk.CTkEntry(self.frm_top)
        self.ent_out.insert(0, DEFAULT_OUTDIR)
        self.ent_out.grid(row=2, column=1, sticky="ew", padx=(0,8), pady=6)
        self.btn_browse_out = ctk.CTkButton(self.frm_top, text="Seç", command=self.select_outdir)
        self.btn_browse_out.grid(row=2, column=2, padx=(0,0), pady=6)

        # Seçenekler
        self.chk_1080 = ctk.CTkCheckBox(self.frm_top, text="1080p ile sınırla (varsa)", checkbox_width=18, checkbox_height=18)
        self.chk_1080.grid(row=3, column=0, sticky="w", pady=6)
        self.chk_1080.select()

        # Başlat & Durdur
        self.btn_start = ctk.CTkButton(self.frm_top, text="İndirmeyi Başlat", command=self.start_worker)
        self.btn_start.grid(row=3, column=1, sticky="e", pady=6)
        self.btn_stop = ctk.CTkButton(self.frm_top, text="Durdur", command=self.request_stop, fg_color="#8a1f1f", hover_color="#6d1717")
        self.btn_stop.grid(row=3, column=2, sticky="e", pady=6)

        # --- Orta: Progress bilgileri ---
        self.frm_prog = ctk.CTkFrame(self, corner_radius=12)
        self.frm_prog.pack(fill="x", padx=12, pady=(0,8))

        # Toplam ilerleme
        ctk.CTkLabel(self.frm_prog, text="Toplam İlerleme").grid(row=0, column=0, sticky="w")
        self.pg_total = ctk.CTkProgressBar(self.frm_prog)
        self.pg_total.set(0)
        self.pg_total.grid(row=0, column=1, sticky="ew", padx=8)
        self.lbl_total = ctk.CTkLabel(self.frm_prog, text="0% (0/0)")
        self.lbl_total.grid(row=0, column=2, sticky="e")
        self.frm_prog.grid_columnconfigure(1, weight=1)

        # Parça ilerleme
        ctk.CTkLabel(self.frm_prog, text="Parça İlerleme").grid(row=1, column=0, sticky="w", pady=(10,0))
        self.pg_part = ctk.CTkProgressBar(self.frm_prog)
        self.pg_part.set(0)
        self.pg_part.grid(row=1, column=1, sticky="ew", padx=8, pady=(10,0))
        self.lbl_part = ctk.CTkLabel(self.frm_prog, text="0% | ETA: -")
        self.lbl_part.grid(row=1, column=2, sticky="e", pady=(10,0))

        # Şu an indirilen
        self.lbl_now_title = ctk.CTkLabel(self.frm_prog, text="Şu An:", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_now_title.grid(row=2, column=0, sticky="w", pady=(10,0))
        self.lbl_now = ctk.CTkLabel(self.frm_prog, text="-")
        self.lbl_now.grid(row=2, column=1, columnspan=2, sticky="w", pady=(10,0))

        # --- Alt: Log penceresi (scrollbar'lı) ---
        self.frm_log = ctk.CTkFrame(self, corner_radius=12)
        self.frm_log.pack(fill="both", expand=True, padx=12, pady=(0,12))

        ctk.CTkLabel(self.frm_log, text="İşlem Günlüğü").pack(anchor="w")
        self.txt_log = tk.Text(self.frm_log, height=16, wrap="word", bg="#111111", fg="#e5e5e5", insertbackground="white")
        self.txt_log.pack(fill="both", expand=True, side="left", padx=(0,6), pady=(6,0))
        self.scroll = ctk.CTkScrollbar(self.frm_log, command=self.txt_log.yview)
        self.scroll.pack(fill="y", side="right", pady=(6,0))
        self.txt_log['yscrollcommand'] = self.scroll.set

        # Durum kontrolü
        self._worker_thread = None
        self._stop_flag = threading.Event()

        # Başlangıçta kısa bir kontrol logu
        self.after(200, self.initial_checks)

    # ---------- UI Helpers ----------
    def select_txt(self):
        p = fd.askopenfilename(title="Zaman aralıkları TXT seç", filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if p:
            self.ent_txt.delete(0, "end")
            self.ent_txt.insert(0, p)

    def select_outdir(self):
        p = fd.askdirectory(title="Çıkış klasörü seç")
        if p:
            self.ent_out.delete(0, "end")
            self.ent_out.insert(0, p)

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.txt_log.insert("end", f"[{ts}] {msg}\n")
        self.txt_log.see("end")

    def set_now(self, text: str):
        self.lbl_now.configure(text=text)

    def set_part_progress(self, frac: float, label: str):
        self.pg_part.set(max(0.0, min(1.0, frac)))
        self.lbl_part.configure(text=label)

    def set_total_progress(self, frac: float, label: str):
        self.pg_total.set(max(0.0, min(1.0, frac)))
        self.lbl_total.configure(text=label)

    def request_stop(self):
        self._stop_flag.set()
        self.log("❗ Durdurma istendi. Mevcut işlem güvenli şekilde sonlandırılacak.")

    def start_worker(self):
        if self._worker_thread and self._worker_thread.is_alive():
            self.log("Zaten çalışıyor…")
            return
        self._stop_flag.clear()
        self._worker_thread = threading.Thread(target=self.run_job, daemon=True)
        self._worker_thread.start()

    # ---------- İş mantığı ----------
    def parse_ranges(self, path: str):
        ranges = []
        with open(path, "r", encoding="utf-8") as f:
            for ln in f:
                s = ln.strip()
                if not s:
                    continue
                parts = s.split()
                if len(parts) != 2:
                    self.log(f"⚠️ Hatalı satır atlandı: {s}")
                    continue
                start, end = parts
                ranges.append((start, end))
        return ranges

    def ytdlp_cmd(self, url: str, start: str, end: str, outpath: str, limit1080: bool):
        if limit1080:
            fmt = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
        else:
            fmt = "bestvideo+bestaudio/best"

        return [
            "yt-dlp", url,
            "--newline",  # progress'i satır satır akıtalım
            "--download-sections", f"*{start}-{end}",
            "--force-keyframes-at-cuts",
            "-f", fmt,
            "--merge-output-format", "mp4",
            "-o", outpath
        ]

    def initial_checks(self):
        # Kullanıcıya kısaca kontrol notu yazalım
        self.log("Hazır. URL ve TXT dosyasını seçin, ardından 'İndirmeyi Başlat' deyin.")
        # yt-dlp mevcut mu (opsiyonel kontrol)
        try:
            subprocess.run(["yt-dlp", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        except Exception:
            self.log("⚠️ Uyarı: 'yt-dlp' bulunamadı veya PATH'te değil. 'pip install yt-dlp' kurulu olmalı.")

    def run_job(self):
        url = self.ent_url.get().strip()
        txt = self.ent_txt.get().strip()
        outdir = self.ent_out.get().strip()
        limit1080 = bool(self.chk_1080.get())

        if not url:
            self.safe_ui(lambda: self.log("❌ URL boş olamaz."))
            return
        if not txt or not os.path.isfile(txt):
            self.safe_ui(lambda: self.log("❌ Geçerli bir TXT dosyası seçmelisiniz."))
            return

        os.makedirs(outdir, exist_ok=True)
        ranges = self.parse_ranges(txt)
        total = len(ranges)
        if total == 0:
            self.safe_ui(lambda: self.log("❌ TXT içinde geçerli aralık bulunamadı."))
            return

        self.safe_ui(lambda: self.set_total_progress(0, f"0% (0/{total})"))
        self.safe_ui(lambda: self.set_part_progress(0, "0% | ETA: -"))
        self.safe_ui(lambda: self.log(f"🎬 Başlıyor: {total} parça indirilecek."))
        self.safe_ui(lambda: self.set_now("-"))

        for idx, (start, end) in enumerate(ranges, start=1):
            if self._stop_flag.is_set():
                break

            outpath = os.path.join(outdir, f"kesit_{idx:02d}.mp4")
            display = f"Parça {idx}/{total}: {start} → {end}"
            self.safe_ui(lambda s=display: self.set_now(s))
            self.safe_ui(lambda s=display: self.log(f"⬇️ {s} indiriliyor…"))

            cmd = self.ytdlp_cmd(url, start, end, outpath, limit1080)

            try:
                with subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, universal_newlines=True
                ) as proc:
                    for line in proc.stdout:
                        if self._stop_flag.is_set():
                            proc.terminate()
                            break

                        # Log'a düşür
                        self.safe_ui(lambda l=line.rstrip(): self.log(l))

                        # Yüzde & ETA yakala
                        m = PERCENT_RE.search(line)
                        eta_m = ETA_RE.search(line)
                        percent = float(m.group(1)) if m else None
                        eta_txt = eta_m.group(1) if eta_m else "-"

                        if percent is not None:
                            frac = max(0.0, min(1.0, percent / 100.0))
                            label = f"{percent:.2f}% | ETA: {eta_txt}"
                            self.safe_ui(lambda f=frac, lab=label: self.set_part_progress(f, lab))

                # Parça bittiğinde part bar sıfırla
                self.safe_ui(lambda: self.set_part_progress(0, "0% | ETA: -"))

            except FileNotFoundError:
                self.safe_ui(lambda: self.log("❌ yt-dlp bulunamadı. 'pip install yt-dlp' ve FFmpeg kurulu olmalı."))
                return
            except Exception as e:
                self.safe_ui(lambda: self.log(f"❌ Hata: {e}"))
                # devam: diğer parçalara geçebilir
                pass

            # Toplam ilerleme güncelle
            done = idx
            frac_total = done / total
            self.safe_ui(lambda f=frac_total, d=done, t=total: self.set_total_progress(f, f"{int(f*100)}% ({d}/{t})"))

        if self._stop_flag.is_set():
            self.safe_ui(lambda: self.log("🛑 Kullanıcı tarafından durduruldu."))
        else:
            self.safe_ui(lambda: self.log("✅ Tüm parçalar tamamlandı!"))
            self.safe_ui(lambda: self.set_now("Tamamlandı."))

    # UI güncellemelerini ana threade taşı
    def safe_ui(self, fn):
        self.after(0, fn)

if __name__ == "__main__":
    app = App()
    app.mainloop()
