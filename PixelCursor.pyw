# ============================================================================
# PixelCursor Studio - Açık Kaynak İmleç Tasarım ve Değiştirme Uygulaması
# Lisans: MIT License (Açık Kaynak - Özgürce değiştirilebilir ve dağıtılabilir)
# Platform: Windows 10 / 11 (Sistem imleci değişimi için user32.dll kullanır)
#
# TEK DOSYA SÜRÜMÜ: Eski IlkKurulum_ve_Baslat.bat + PixelCursor.vbs +
# pixel_cursor_studio.pyw bu dosyada birleştirildi. Çift tıklamak yeterli:
#   - Komut penceresi açılmaz (pythonw ile çalışır, konsol açılırsa gizlenir)
#   - Pillow her açılışta kurulmaz; yalnızca eksikse arka planda sessizce kurulur
# ============================================================================

import os
import sys
import struct
import ctypes
import tempfile
import threading
import subprocess
import importlib
from collections import deque
import tkinter as tk
from tkinter import ttk, colorchooser, filedialog, messagebox

Image = None  # Pillow tembel yüklenir (yalnızca "Görsel Yükle" için gerekir)

CREATE_NO_WINDOW = 0x08000000


def _hide_own_console():
    """Dosya python.exe ile açıldıysa ve konsol sadece bize aitse onu gizle."""
    if sys.platform != "win32":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        hwnd = kernel32.GetConsoleWindow()
        if not hwnd:
            return
        procs = (ctypes.c_uint * 4)()
        count = kernel32.GetConsoleProcessList(procs, 4)
        if count <= 1:  # Konsolu başka bir terminal paylaşmıyorsa gizle
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def _console_python():
    """pip için python.exe yolunu bul (pythonw.exe'nin stdout'u yoktur)."""
    exe = sys.executable or "python"
    folder, name = os.path.split(exe)
    if name.lower() == "pythonw.exe":
        candidate = os.path.join(folder, "python.exe")
        if os.path.exists(candidate):
            return candidate
    return exe


IS_FROZEN = getattr(sys, "frozen", False)  # PyInstaller ile .exe yapıldıysa True


def pillow_available() -> bool:
    try:
        import PIL  # noqa: F401  (exe içinde gömülü gelir)
        return True
    except ImportError:
        return False


def install_pillow_silently() -> bool:
    """Pillow'u görünmez şekilde kurar. Başarılıysa True döner."""
    if pillow_available():
        return True
    if IS_FROZEN:  # .exe içinde pip çalıştırılamaz; Pillow zaten gömülü olmalı
        return False
    try:
        flags = CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.run(
            [_console_python(), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "Pillow"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, creationflags=flags, timeout=300,
        )
    except Exception:
        return False
    importlib.invalidate_caches()
    return pillow_available()


def load_pillow():
    """PIL.Image modülünü döndürür; gerekirse önce sessizce kurar."""
    global Image
    if Image is None and install_pillow_silently():
        from PIL import Image as _Image
        Image = _Image
    return Image


# Uygulama ikonu: 16x16 piksel fare imleci (K=siyah kontur, C=neon dolgu,
# W=parlama, S=gölge). Aynı desen .exe ikonunda da kullanılır.
ICON_ROWS = [
    "..K.............",
    "..KK............",
    "..KCK...........",
    "..KWCK..........",
    "..KWCCK.........",
    "..KWCCCK........",
    "..KWCCCCK.......",
    "..KWCCCCCK......",
    "..KWCCCCCCK.....",
    "..KWCCCCCCCK....",
    "..KWCCCCCKKKKS..",
    "..KWCKCCKSSSSS..",
    "..KCKSKCCKS.....",
    "..KKS.KCCKS.....",
    "..KS...KCCKS....",
    "...S...SKKSS....",
]
ICON_COLORS = {"K": "#11111B", "C": "#00F5D4", "W": "#C8FFF6", "S": "#3B3F58"}


def apply_window_icon(root):
    """Pencere ve görev çubuğu ikonunu piksel imleç yapar (dosya gerektirmez)."""
    try:
        if sys.platform == "win32" and not IS_FROZEN:
            # pythonw ile çalışırken görev çubuğunda Python ikonu yerine bizimki görünsün
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PixelCursor.Studio")
        base = tk.PhotoImage(width=16, height=16)
        for y, row in enumerate(ICON_ROWS):
            for x, ch in enumerate(row):
                if ch in ICON_COLORS:
                    base.put(ICON_COLORS[ch], (x, y))
        images = [base, base.zoom(2), base.zoom(4)]
        root._icon_images = images  # çöp toplayıcı silmesin
        root.iconphoto(True, *images)
    except Exception:
        pass


# Windows API Sabitleri
SPI_SETCURSORS = 0x0057
OCR_NORMAL = 32512      # Standart Ok
OCR_IBEAM = 32513       # Metin Seçimi
OCR_CROSS = 32515       # Hassas Seçim (Crosshair)
OCR_HAND = 32649        # Bağlantı Seçimi (El)

GRID_SIZE = 32
CELL_SIZE = 16          # 32 * 16 = 512x512 piksel çizim alanı


class PixelCursorStudio:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PixelCursor Studio - İmleç Tasarla & Değiştir")
        self.root.configure(bg="#181825")
        self.root.resizable(False, False)

        # Durum Değişkenleri
        self.pixels = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.undo_stack = []
        self.current_color = "#00F5D4"
        self.current_tool = tk.StringVar(value="pencil")
        self.show_grid = tk.BooleanVar(value=True)
        self.target_cursor_mode = tk.StringVar(value="normal")
        self.hotspot = [0, 0]  # [x, y]

        # Varsayılan Renk Paleti (Retro / Oyun Paleti)
        self.palette = [
            "#FFFFFF", "#000000", "#FF0055", "#FF5500",
            "#FFCC00", "#00F5D4", "#00BBF9", "#9B5DE5",
            "#F15BB5", "#00F566", "#8D99AE", "#2B2D42",
            "#E63946", "#FFB703", "#8ECAE6", "#588157"
        ]

        self._build_ui()
        self._load_template_arrow()

        # Kısayollar
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-Z>", lambda e: self.undo())

    def _build_ui(self):
        main_frame = tk.Frame(self.root, bg="#181825", padx=16, pady=16)
        main_frame.pack(fill="both", expand=True)

        # SOL PANEL: Araçlar ve Renk Paleti
        left_panel = tk.Frame(main_frame, bg="#1E1E2E", padx=12, pady=12, relief="flat")
        left_panel.grid(row=0, column=0, sticky="ns", padx=(0, 14))

        tk.Label(
            left_panel, text="ARAÇLAR", fg="#CDD6F4", bg="#1E1E2E",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(0, 6))

        tools = [
            ("Kalem (Sol Tık)", "pencil"),
            ("Silgi (Sağ Tık)", "eraser"),
            ("Boya Kovası", "fill"),
            ("Renk Seçici (Damla)", "picker"),
            ("Tıklama Noktası (Hotspot)", "hotspot"),
        ]
        for text, val in tools:
            rb = tk.Radiobutton(
                left_panel, text=text, variable=self.current_tool, value=val,
                bg="#1E1E2E", fg="#CDD6F4", selectcolor="#313244",
                activebackground="#1E1E2E", activeforeground="#89B4FA",
                font=("Segoe UI", 9), anchor="w", indicatoron=False,
                width=22, pady=5, bd=0, highlightthickness=0
            )
            rb.pack(pady=2)

        tk.Checkbutton(
            left_panel, text="Izgarayı Göster", variable=self.show_grid,
            command=self._refresh_canvas_grid, bg="#1E1E2E", fg="#A6ADC8",
            selectcolor="#313244", activebackground="#1E1E2E",
            font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(8, 4))

        tk.Label(
            left_panel, text="AKTİF RENK", fg="#CDD6F4", bg="#1E1E2E",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(10, 4))

        color_row = tk.Frame(left_panel, bg="#1E1E2E")
        color_row.pack(fill="x", pady=4)

        self.color_preview = tk.Frame(
            color_row, bg=self.current_color, width=36, height=36,
            highlightbackground="#CDD6F4", highlightthickness=1
        )
        self.color_preview.pack(side="left", padx=(0, 8))

        tk.Button(
            color_row, text="Özel Renk Seç", command=self.choose_custom_color,
            bg="#313244", fg="#CDD6F4", activebackground="#45475A",
            relief="flat", font=("Segoe UI", 9), padx=8, pady=6
        ).pack(side="left", fill="x", expand=True)

        palette_frame = tk.Frame(left_panel, bg="#1E1E2E")
        palette_frame.pack(pady=6)
        for idx, hex_col in enumerate(self.palette):
            btn = tk.Button(
                palette_frame, bg=hex_col, width=3, height=1, relief="flat",
                command=lambda c=hex_col: self.set_color(c)
            )
            btn.grid(row=idx // 4, column=idx % 4, padx=2, pady=2)

        tk.Label(
            left_panel, text="TUVAL İŞLEMLERİ", fg="#CDD6F4", bg="#1E1E2E",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(12, 4))

        self._make_btn(left_panel, "Geri Al (Ctrl+Z)", self.undo, "#313244")
        self._make_btn(left_panel, "Tuvali Temizle", self.clear_canvas, "#45475A")

        tk.Label(
            left_panel, text="HAZIR ŞABLONLAR", fg="#CDD6F4", bg="#1E1E2E",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(12, 4))

        self._make_btn(left_panel, "Neon Piksel Ok", self._load_template_arrow, "#313244")
        self._make_btn(left_panel, "RPG Piksel Kılıç", self._load_template_sword, "#313244")
        self._make_btn(left_panel, "FPS Nişangah", self._load_template_crosshair, "#313244")

        # ORTA PANEL: 32x32 Piksel Tuvali
        center_panel = tk.Frame(main_frame, bg="#181825")
        center_panel.grid(row=0, column=1, sticky="n")

        header_lbl = tk.Label(
            center_panel,
            text="32x32 PİKSEL TASARIM ALANI (Sol Tık: Çiz / Sağ Tık: Sil)",
            fg="#A6ADC8", bg="#181825", font=("Segoe UI", 9, "bold")
        )
        header_lbl.pack(pady=(0, 6))

        canvas_size = GRID_SIZE * CELL_SIZE
        self.canvas = tk.Canvas(
            center_panel, width=canvas_size, height=canvas_size,
            bg="#262637", highlightthickness=2, highlightbackground="#45475A"
        )
        self.canvas.pack()

        self.rect_ids = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                checker = "#2A2B3C" if (x + y) % 2 == 0 else "#202130"
                x1, y1 = x * CELL_SIZE, y * CELL_SIZE
                x2, y2 = x1 + CELL_SIZE, y1 + CELL_SIZE
                rid = self.canvas.create_rectangle(
                    x1, y1, x2, y2, fill=checker, outline="#36384C"
                )
                self.rect_ids[y][x] = rid

        self.hotspot_marker = self.canvas.create_oval(
            0, 0, 0, 0, outline="#FF0055", width=2
        )

        self.canvas.bind("<ButtonPress-1>", self.on_left_down)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonPress-3>", self.on_right_down)
        self.canvas.bind("<B3-Motion>", self.on_right_drag)

        # SAĞ PANEL: Önizleme, Görsel Aktarma ve Sistem Kontrolü
        right_panel = tk.Frame(main_frame, bg="#1E1E2E", padx=14, pady=12, width=250)
        right_panel.grid(row=0, column=2, sticky="ns", padx=(14, 0))

        tk.Label(
            right_panel, text="GERÇEK BOYUT (1:1)", fg="#CDD6F4", bg="#1E1E2E",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w")

        preview_box = tk.Frame(right_panel, bg="#11111B", padx=12, pady=12)
        preview_box.pack(fill="x", pady=(6, 12))

        self.mini_canvas = tk.Canvas(
            preview_box, width=32, height=32, bg="#181825",
            highlightthickness=1, highlightbackground="#585B70"
        )
        self.mini_canvas.pack(side="left", padx=(8, 14))

        self.hotspot_label = tk.Label(
            preview_box, text="Hotspot: (0, 0)", fg="#A6ADC8",
            bg="#11111B", font=("Consolas", 9)
        )
        self.hotspot_label.pack(side="left")

        tk.Label(
            right_panel, text="DOSYA İŞLEMLERİ", fg="#CDD6F4", bg="#1E1E2E",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(8, 4))

        self._make_btn(
            right_panel, "Görsel Yükle (PNG/JPG)",
            self.import_image, "#313244"
        )
        self._make_btn(
            right_panel, ".CUR Olarak Kaydet",
            self.export_cur_dialog, "#313244"
        )

        tk.Label(
            right_panel, text="BİLGİSAYARA UYGULA", fg="#CDD6F4", bg="#1E1E2E",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(16, 4))

        modes = [
            ("Standart Fare Oku", "normal"),
            ("El İmleci (Link Seçimi)", "hand"),
            ("Nişangah (Crosshair)", "cross"),
            ("Tüm Ana İmleçler", "all"),
        ]
        for text, val in modes:
            tk.Radiobutton(
                right_panel, text=text, variable=self.target_cursor_mode, value=val,
                bg="#1E1E2E", fg="#CDD6F4", selectcolor="#313244",
                activebackground="#1E1E2E", font=("Segoe UI", 9)
            ).pack(anchor="w", pady=1)

        tk.Button(
            right_panel, text="İMLECİ ŞİMDİ UYGULA",
            command=self.apply_cursor_to_system,
            bg="#00F5D4", fg="#11111B", activebackground="#00BBF9",
            font=("Segoe UI", 10, "bold"), relief="flat", pady=10, cursor="hand2"
        ).pack(fill="x", pady=(12, 6))

        tk.Button(
            right_panel, text="Varsayılan Windows İmlecine Dön",
            command=self.restore_default_cursors,
            bg="#F38BA8", fg="#11111B", activebackground="#EBA0AC",
            font=("Segoe UI", 9, "bold"), relief="flat", pady=7, cursor="hand2"
        ).pack(fill="x", pady=4)

        self.status_label = tk.Label(
            right_panel, text="Hazır.", fg="#A6E3A1", bg="#1E1E2E",
            font=("Segoe UI", 9), wraplength=210, justify="left"
        )
        self.status_label.pack(anchor="w", pady=(14, 0))

    def _make_btn(self, parent, text, cmd, bg_color):
        btn = tk.Button(
            parent, text=text, command=cmd, bg=bg_color, fg="#CDD6F4",
            activebackground="#585B70", activeforeground="#FFFFFF",
            relief="flat", font=("Segoe UI", 9), pady=5, cursor="hand2"
        )
        btn.pack(fill="x", pady=2)
        return btn

    def set_color(self, hex_color: str):
        self.current_color = hex_color
        self.color_preview.configure(bg=hex_color)
        if self.current_tool.get() in ("eraser", "hotspot", "picker"):
            self.current_tool.set("pencil")

    def choose_custom_color(self):
        color = colorchooser.askcolor(color=self.current_color, title="Renk Seç")
        if color and color[1]:
            self.set_color(color[1].upper())

    def save_undo_state(self):
        snapshot = [row[:] for row in self.pixels]
        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > 30:
            self.undo_stack.pop(0)

    def undo(self):
        if not self.undo_stack:
            self.status_label.configure(text="Geri alınacak işlem yok.")
            return
        self.pixels = self.undo_stack.pop()
        self.redraw_all()
        self.status_label.configure(text="Son işlem geri alındı.")

    def clear_canvas(self):
        self.save_undo_state()
        self.pixels = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.redraw_all()
        self.status_label.configure(text="Tuval temizlendi.")

    def _get_cell_coords(self, event):
        x = event.x // CELL_SIZE
        y = event.y // CELL_SIZE
        if 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE:
            return x, y
        return None, None

    def on_left_down(self, event):
        x, y = self._get_cell_coords(event)
        if x is None:
            return
        tool = self.current_tool.get()

        if tool == "hotspot":
            self.hotspot = [x, y]
            self._update_hotspot_visual()
            self.status_label.configure(text=f"Tıklama noktası ({x}, {y}) olarak ayarlandı.")
            return

        if tool == "picker":
            picked = self.pixels[y][x]
            if picked:
                self.set_color(picked)
                self.status_label.configure(text=f"Renk seçildi: {picked}")
            return

        self.save_undo_state()
        if tool == "fill":
            self.flood_fill(x, y, self.current_color)
            self.redraw_all()
        elif tool == "eraser":
            self._set_pixel(x, y, None)
        else:
            self._set_pixel(x, y, self.current_color)

    def on_left_drag(self, event):
        x, y = self._get_cell_coords(event)
        if x is None:
            return
        tool = self.current_tool.get()
        if tool == "pencil":
            self._set_pixel(x, y, self.current_color)
        elif tool == "eraser":
            self._set_pixel(x, y, None)

    def on_right_down(self, event):
        x, y = self._get_cell_coords(event)
        if x is None:
            return
        self.save_undo_state()
        self._set_pixel(x, y, None)

    def on_right_drag(self, event):
        x, y = self._get_cell_coords(event)
        if x is not None:
            self._set_pixel(x, y, None)

    def _set_pixel(self, x: int, y: int, color):
        self.pixels[y][x] = color
        fill_col = color if color else ("#2A2B3C" if (x + y) % 2 == 0 else "#202130")
        self.canvas.itemconfig(self.rect_ids[y][x], fill=fill_col)
        self._update_mini_preview()

    def flood_fill(self, start_x: int, start_y: int, new_color: str):
        target_color = self.pixels[start_y][start_x]
        if target_color == new_color:
            return
        queue = deque([(start_x, start_y)])
        visited = set()
        while queue:
            cx, cy = queue.popleft()
            if (cx, cy) in visited:
                continue
            visited.add((cx, cy))
            if self.pixels[cy][cx] == target_color:
                self.pixels[cy][cx] = new_color
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                        queue.append((nx, ny))

    def _refresh_canvas_grid(self):
        show = self.show_grid.get()
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                outline = "#36384C" if show else ""
                self.canvas.itemconfig(self.rect_ids[y][x], outline=outline)

    def _update_hotspot_visual(self):
        hx, hy = self.hotspot
        x1 = hx * CELL_SIZE + 3
        y1 = hy * CELL_SIZE + 3
        x2 = (hx + 1) * CELL_SIZE - 3
        y2 = (hy + 1) * CELL_SIZE - 3
        self.canvas.coords(self.hotspot_marker, x1, y1, x2, y2)
        self.canvas.tag_raise(self.hotspot_marker)
        self.hotspot_label.configure(text=f"Hotspot: ({hx}, {hy})")

    def _update_mini_preview(self):
        self.mini_canvas.delete("all")
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                col = self.pixels[y][x]
                if col:
                    self.mini_canvas.create_rectangle(x, y, x + 1, y + 1, fill=col, outline=col)

    def redraw_all(self):
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                col = self.pixels[y][x]
                fill_col = col if col else ("#2A2B3C" if (x + y) % 2 == 0 else "#202130")
                self.canvas.itemconfig(self.rect_ids[y][x], fill=fill_col)
        self._update_hotspot_visual()
        self._update_mini_preview()

    def import_image(self):
        file_path = filedialog.askopenfilename(
            title="İmleç İçin Görsel Seç",
            filetypes=[("Görsel Dosyaları", "*.png *.jpg *.jpeg *.webp *.bmp *.ico")]
        )
        if not file_path:
            return
        if Image is None:
            self.status_label.configure(text="Görsel desteği hazırlanıyor (Pillow), lütfen bekleyin...")
            self.root.update_idletasks()
        if load_pillow() is None:
            messagebox.showerror(
                "Pillow Bulunamadı",
                "Görsel yüklemek için gereken Pillow kütüphanesi kurulamadı.\n"
                "İnternet bağlantınızı kontrol edip tekrar deneyin."
            )
            return
        try:
            self.save_undo_state()
            img = Image.open(file_path).convert("RGBA")
            img = img.resize((GRID_SIZE, GRID_SIZE), Image.Resampling.NEAREST)
            for y in range(GRID_SIZE):
                for x in range(GRID_SIZE):
                    r, g, b, a = img.getpixel((x, y))
                    if a < 64:
                        self.pixels[y][x] = None
                    else:
                        self.pixels[y][x] = f"#{r:02X}{g:02X}{b:02X}"
            self.redraw_all()
            self.status_label.configure(text="Görsel 32x32 piksel olarak aktarıldı!")
        except Exception as e:
            messagebox.showerror("Görsel Hatası", f"Görsel yüklenemedi:\n{e}")

    def _hex_to_rgb(self, hex_str: str):
        h = hex_str.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def build_cur_bytes(self) -> bytes:
        hx, hy = self.hotspot
        width, height = GRID_SIZE, GRID_SIZE

        xor_bytes = bytearray()
        and_bytes = bytearray()

        for y in range(height - 1, -1, -1):
            row_and_bits = 0
            for x in range(width):
                col = self.pixels[y][x]
                if col is None:
                    xor_bytes.extend((0, 0, 0, 0))
                    row_and_bits = (row_and_bits << 1) | 1
                else:
                    r, g, b = self._hex_to_rgb(col)
                    xor_bytes.extend((b, g, r, 255))
                    row_and_bits = (row_and_bits << 1) | 0
            and_bytes.extend(struct.pack(">I", row_and_bits))

        dib_header = struct.pack(
            "<IiiHHIIiiII",
            40,
            width,
            height * 2,
            1,
            32,
            0,
            len(xor_bytes) + len(and_bytes),
            0, 0, 0, 0
        )

        image_data = dib_header + xor_bytes + and_bytes
        icondir = struct.pack("<HHH", 0, 2, 1)
        icondirentry = struct.pack(
            "<BBBBHHII",
            width,
            height,
            0,
            0,
            hx,
            hy,
            len(image_data),
            6 + 16
        )

        return icondir + icondirentry + image_data

    def export_cur_dialog(self):
        file_path = filedialog.asksaveasfilename(
            title="İmleci Kaydet",
            defaultextension=".cur",
            filetypes=[("Windows İmleç Dosyası", "*.cur")]
        )
        if not file_path:
            return
        try:
            cur_data = self.build_cur_bytes()
            with open(file_path, "wb") as f:
                f.write(cur_data)
            self.status_label.configure(text=f"Kaydedildi: {os.path.basename(file_path)}")
        except Exception as e:
            messagebox.showerror("Kayıt Hatası", f"Dosya kaydedilemedi:\n{e}")

    def apply_cursor_to_system(self):
        if sys.platform != "win32":
            messagebox.showwarning("Platform Uyarısı", "Sistem imleci değiştirme yalnızca Windows'ta çalışır.")
            return

        has_pixels = any(self.pixels[y][x] is not None for y in range(GRID_SIZE) for x in range(GRID_SIZE))
        if not has_pixels:
            messagebox.showwarning("Uyarı", "Tamamen boş bir imleç uygulayamazsınız! Lütfen önce çizim yapın.")
            return

        try:
            cur_bytes = self.build_cur_bytes()
            temp_path = os.path.join(tempfile.gettempdir(), "pixel_cursor_active.cur")
            with open(temp_path, "wb") as f:
                f.write(cur_bytes)

            mode = self.target_cursor_mode.get()
            if mode == "normal":
                target_ids = [OCR_NORMAL]
            elif mode == "hand":
                target_ids = [OCR_HAND]
            elif mode == "cross":
                target_ids = [OCR_CROSS]
            else:
                target_ids = [OCR_NORMAL, OCR_HAND, OCR_CROSS, OCR_IBEAM]

            user32 = ctypes.windll.user32
            user32.LoadCursorFromFileW.restype = ctypes.c_void_p
            user32.SetSystemCursor.argtypes = [ctypes.c_void_p, ctypes.c_uint]

            for cid in target_ids:
                hcursor = user32.LoadCursorFromFileW(temp_path)
                if not hcursor:
                    raise RuntimeError("Windows imleç dosyasını yükleyemedi.")
                user32.SetSystemCursor(hcursor, cid)

            self.status_label.configure(text="İmleç başarıyla bilgisayara uygulandı!")
        except Exception as e:
            messagebox.showerror("Sistem Hatası", f"İmleç uygulanırken hata oluştu:\n{e}")

    def restore_default_cursors(self):
        if sys.platform != "win32":
            return
        ctypes.windll.user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, 0)
        self.status_label.configure(text="Varsayılan Windows imleci geri yüklendi.")

    def _load_template_arrow(self):
        self.save_undo_state()
        self.pixels = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.hotspot = [1, 1]
        for i in range(1, 16):
            for j in range(1, i + 1):
                if i >= 12 and j > 6:
                    continue
                if j == 1 or j == i or (i == 11 and j > 5) or (i == 15 and j <= 6):
                    self.pixels[i][j] = "#000000"
                else:
                    self.pixels[i][j] = "#00F5D4"
        self.redraw_all()

    def _load_template_sword(self):
        self.save_undo_state()
        self.pixels = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.hotspot = [2, 2]
        for i in range(2, 18):
            self.pixels[i][i] = "#FFFFFF"
            self.pixels[i - 1][i] = "#8ECAE6"
            self.pixels[i][i - 1] = "#2B2D42"
        for k in range(-3, 4):
            self.pixels[18 - k][18 + k] = "#FFB703"
        for s in range(19, 23):
            self.pixels[s][s] = "#9B5DE5"
        self.redraw_all()

    def _load_template_crosshair(self):
        self.save_undo_state()
        self.pixels = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        c = 15
        self.hotspot = [c, c]
        self.pixels[c][c] = "#FF0055"
        for offset in range(3, 9):
            for dx, dy in ((offset, 0), (-offset, 0), (0, offset), (0, -offset)):
                self.pixels[c + dy][c + dx] = "#00F566"
                self.pixels[c + dy + (1 if dx else 0)][c + dx + (1 if dy else 0)] = "#000000"
        self.redraw_all()


if __name__ == "__main__":
    _hide_own_console()
    root = tk.Tk()
    apply_window_icon(root)
    app = PixelCursorStudio(root)
    # Pillow eksikse arayüzü bekletmeden arka planda sessizce kur
    if not pillow_available():
        threading.Thread(target=install_pillow_silently, daemon=True).start()
    root.mainloop()
