# ============================================================================
# PixelCursor Studio - Açık Kaynak İmleç Tasarım ve Değiştirme Uygulaması
# Lisans: MIT License (Açık Kaynak - Özgürce değiştirilebilir ve dağıtılabilir)
# Platform: Windows 10 / 11 (Sistem imleci değişimi için user32.dll kullanır)
#
# TEK DOSYA SÜRÜMÜ: Eski IlkKurulum_ve_Baslat.bat + PixelCursor.vbs +
# pixel_cursor_studio.pyw bu dosyada birleştirildi. Çift tıklamak yeterli:
#   - Komut penceresi açılmaz (pythonw ile çalışır, konsol açılırsa gizlenir)
#   - Pillow her açılışta kurulmaz; yalnızca eksikse arka planda sessizce kurulur
#
# SÜRÜM 2:
#   - Son çalışma otomatik kaydedilir, açılışta kaldığı yerden devam eder
#   - GEÇMİŞ sekmesi: yüklenen görseller, kaydedilen ve uygulanan imleçler
#   - Uygulanan imleç kayıt defterine yazılır; bilgisayar yeniden başlasa da kalır
#   - 32x32 / 48x48 / 64x64 tuval; görseller oran korunarak ve kırpılarak aktarılır
#
# SÜRÜM 4:
#   - Türkçe / İngilizce arayüz (sağ üstteki TR / EN)
#   - "Güncellemeleri denetle": yeni sürüm varsa sorar, indirir, doğrular ve kendini günceller
#
# SÜRÜM 3:
#   - Yüklerken arka planı otomatik kaldırma + "Arka Planı Kaldır" düğmesi
#   - Sihirli silgi (benzer renkli bölgeyi siler), Alan silgisi (dikdörtgen)
#   - Fırça boyutu (1/2/3/5) ve Tolerans ayarı
#   Veriler: %APPDATA%\PixelCursorStudio
# ============================================================================

import os
import re
import sys
import json
import time
import hashlib
import queue
import urllib.request
import webbrowser
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
SPIF_UPDATE_AND_BROADCAST = 0x01 | 0x02
OCR_NORMAL = 32512      # Standart Ok
OCR_IBEAM = 32513       # Metin Seçimi
OCR_CROSS = 32515       # Hassas Seçim (Crosshair)
OCR_HAND = 32649        # Bağlantı Seçimi (El)

# Kayıt defterinde (HKCU\Control Panel\Cursors) her imlecin değer adı.
# İmleç buraya yazıldığı için bilgisayar yeniden başlasa da kalıcı olur.
CURSOR_REG_KEY = r"Control Panel\Cursors"
ROLE_NAMES = {OCR_NORMAL: "Arrow", OCR_HAND: "Hand", OCR_CROSS: "Crosshair", OCR_IBEAM: "IBeam"}

GRID_CHOICES = (32, 48, 64)
CANVAS_PX = 512          # Çizim alanının ekrandaki boyutu (piksel)
HISTORY_LIMIT = 40
BRUSH_CHOICES = (1, 2, 3, 5)
MAX_COLOR_DIST = 441.68  # sqrt(3 * 255^2): iki renk arasındaki en büyük fark

TOOL_HINTS = {
    "pencil": "Kalem: sol tıkla çiz. Sağ tık her araçta siler.",
    "eraser": "Silgi: fırça boyutunda siler.",
    "fill": "Boya kovası: aynı renkli bölgeyi doldurur.",
    "picker": "Renk seçici: tıkladığın pikselin rengini alır.",
    "magic": "Sihirli silgi: tıkladığın renge benzeyen bitişik bölgeyi tek seferde siler (Tolerans ayarına bakar).",
    "area": "Alan silgisi: sürükleyerek bir dikdörtgen çiz, içi silinir.",
    "hotspot": "Tıklama noktası: imlecin tıklayan ucunu seç.",
}
TOOL_HINTS_EN = {
    "pencil": "Pencil: left-click to draw. Right-click erases with any tool.",
    "eraser": "Eraser: erases at the brush size.",
    "fill": "Paint bucket: fills the same-colored area.",
    "picker": "Color picker: picks the color of the clicked pixel.",
    "magic": "Magic eraser: removes the connected area similar to the clicked color (uses Tolerance).",
    "area": "Area eraser: drag a rectangle to clear its inside.",
    "hotspot": "Click point: choose the tip of the cursor that clicks.",
}

BG = "#181825"
PANEL = "#1E1E2E"
FG = "#CDD6F4"
MUTED = "#A6ADC8"
BTN = "#313244"


# ---------------------------------------------------------------------------
# Sürüm ve güncelleme
# Yeni sürüm yayınlamak için: EXE_Olustur.bat çalıştır (sürümü artırır, exe'yi
# derler ve version.json'u üretir), sonra hepsini GitHub'a gönder.
# ---------------------------------------------------------------------------
APP_VERSION = "4.0.0"
GITHUB_REPO = "Harun-Simsek/PixelCursor"
RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main"
UPDATE_INFO_URL = f"{RAW_BASE}/version.json"
REPO_PAGE_URL = f"https://github.com/{GITHUB_REPO}"


def parse_version(v) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:3]) or (0,)


def fetch_update_info(timeout: float = 8.0) -> dict:
    url = f"{UPDATE_INFO_URL}?nocache={int(time.time())}"
    req = urllib.request.Request(url, headers={"User-Agent": f"PixelCursor/{APP_VERSION}",
                                               "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def download_file(url: str, dest: str, progress=None, timeout: float = 30.0) -> str:
    """Dosyayı indirir, ilerlemeyi progress(okunan, toplam) ile bildirir, SHA-256 döndürür."""
    req = urllib.request.Request(url, headers={"User-Agent": f"PixelCursor/{APP_VERSION}"})
    sha = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            sha.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    return sha.hexdigest()


def file_sha256(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def clean_env_for_relaunch() -> dict:
    """PyInstaller'ın tek-dosya exe'si kendini yeniden başlatırken eski geçici
    klasörü kullanmasın diye ortam değişkenlerini temizler."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("_PYI", "_MEIPASS"))}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def cleanup_old_exe():
    """Önceki güncellemeden kalan .old dosyasını siler (çalışırken silinemediği için)."""
    if IS_FROZEN:
        old = sys.executable + ".old"
        try:
            if os.path.exists(old):
                os.remove(old)
        except OSError:
            pass


def make_version_json(folder: str) -> dict:
    """Derleme betiği için: klasördeki exe ve pyw'nin sürüm/özet bilgisini yazar."""
    info = {"version": APP_VERSION}
    for key, name in (("exe", "PixelCursor.exe"), ("pyw", "PixelCursor.pyw")):
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            data = f.read()
        if key == "pyw":
            # Git (.gitattributes: text=auto) metin dosyalarını depoda LF satır sonuyla saklar;
            # indirilen dosya da LF olacağı için özet LF haline göre hesaplanır.
            data = data.replace(b"\r\n", b"\n")
        info[f"{key}_url"] = f"{RAW_BASE}/{name}"
        info[f"{key}_sha256"] = hashlib.sha256(data).hexdigest()
        info[f"{key}_size"] = len(data)
    with open(os.path.join(folder, "version.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)
    return info


def bump_version_in_file(path: str, new_version: str = "") -> str:
    """PixelCursor.pyw içindeki APP_VERSION'ı yeni sürüme (boşsa bir artırarak) ayarlar."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    current = re.search(r'APP_VERSION = "([^"]+)"', text).group(1)
    if not new_version.strip():
        parts = list(parse_version(current)) + [0, 0]
        new_version = f"{parts[0]}.{parts[1]}.{parts[2] + 1}"
    new_version = new_version.strip()
    text = text.replace(f'APP_VERSION = "{current}"', f'APP_VERSION = "{new_version}"', 1)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return new_version


# ---------------------------------------------------------------------------
# Dil desteği: metinler Türkçe yazılır, İngilizce karşılıkları bu tablodadır.
# T("metin {x}", x=1) seçili dile çevirir ve {..} alanlarını doldurur.
# ---------------------------------------------------------------------------
LANG = "tr"
EN = {
    "PixelCursor Studio - İmleç Tasarla & Değiştir": "PixelCursor Studio - Design & Change Cursors",
    "ARAÇLAR": "TOOLS",
    "Kalem": "Pencil",
    "Silgi": "Eraser",
    "Boya Kovası": "Paint Bucket",
    "Renk Seçici": "Color Picker",
    "Sihirli Silgi": "Magic Eraser",
    "Alan Silgisi": "Area Eraser",
    "Tıklama Noktası (Hotspot)": "Click Point (Hotspot)",
    "Fırça:": "Brush:",
    "Tolerans:": "Tolerance:",
    "Izgarayı Göster": "Show Grid",
    "TUVAL BOYUTU": "CANVAS SIZE",
    "AKTİF RENK": "ACTIVE COLOR",
    "Özel Renk Seç": "Custom Color",
    "TUVAL İŞLEMLERİ": "CANVAS ACTIONS",
    "Arka Planı Kaldır": "Remove Background",
    "Geri Al (Ctrl+Z)": "Undo (Ctrl+Z)",
    "Temizle": "Clear",
    "HAZIR ŞABLONLAR": "TEMPLATES",
    "Neon Ok": "Neon Arrow",
    "Kılıç": "Sword",
    "Nişangah": "Crosshair",
    "İMLEÇ": "CURSOR",
    "GEÇMİŞ": "HISTORY",
    "GERÇEK BOYUT (1:1)": "ACTUAL SIZE (1:1)",
    "DOSYA İŞLEMLERİ": "FILE",
    "Görsel Yükle (PNG/JPG/GIF)": "Import Image (PNG/JPG/GIF)",
    "Yüklerken arka planı otomatik kaldır": "Remove background automatically on import",
    ".CUR Olarak Kaydet": "Save as .CUR",
    "BİLGİSAYARA UYGULA": "APPLY TO COMPUTER",
    "Standart Fare Oku": "Standard Arrow",
    "El İmleci (Link Seçimi)": "Hand (Link Select)",
    "Nişangah (Crosshair)": "Crosshair",
    "Tüm Ana İmleçler": "All Main Cursors",
    "Ekranda boyut:": "On-screen size:",
    "Windows ayarı": "Windows default",
    "İMLECİ ŞİMDİ UYGULA": "APPLY CURSOR NOW",
    "Varsayılan Windows İmlecine Dön": "Restore Default Windows Cursor",
    "Hazır.": "Ready.",
    "Yüklenen görseller ve\nuygulanan imleçler": "Imported images and\napplied cursors",
    "Henüz geçmiş yok.\nGörsel yüklediğinde veya imleç\nuyguladığında burada görünür.":
        "No history yet.\nImported images and applied\ncursors will appear here.",
    "Aç": "Open",
    "Uygula": "Apply",
    "Sil": "Delete",
    "Görsel": "Image",
    "Uygulandı": "Applied",
    "Kaydedildi": "Saved",
    "Standart ok": "Standard arrow",
    "El imleci": "Hand cursor",
    "Tüm imleçler": "All cursors",
    "{n}x{n} PİKSEL TASARIM ALANI (Sol Tık: Çiz / Sağ Tık: Sil)": "{n}x{n} PIXEL CANVAS (Left click: Draw / Right click: Erase)",
    "Boyut: {n}x{n}\nHotspot: ({x}, {y})": "Size: {n}x{n}\nHotspot: ({x}, {y})",
    "Tuval {n}x{n} olarak ayarlandı.": "Canvas set to {n}x{n}.",
    "Renk Seç": "Choose Color",
    "Geri alınacak işlem yok.": "Nothing to undo.",
    "Son işlem geri alındı.": "Last action undone.",
    "Tuval temizlendi.": "Canvas cleared.",
    "Tıklama noktası ({x}, {y}) olarak ayarlandı.": "Click point set to ({x}, {y}).",
    "Renk seçildi: {c}": "Color picked: {c}",
    "Sihirli silgi: {n} piksel silindi.": "Magic eraser: {n} pixels removed.",
    "Alan silindi: {w}x{h} piksel.": "Area cleared: {w}x{h} pixels.",
    "Tuval zaten boş.": "The canvas is already empty.",
    "Kenarlara bağlı bir arka plan bulunamadı. Sihirli silgi veya Alan silgisini dene.":
        "No background connected to the edges was found. Try the Magic or Area eraser.",
    "Arka plan orijinal görselden kaldırıldı ve nesne tuvale sığdırıldı. Fazla/az sildiyse Ctrl+Z yapıp Tolerans'ı değiştir.":
        "Background removed from the original image and the object was fitted to the canvas. If it removed too much/little, press Ctrl+Z and change Tolerance.",
    "Arka plan kaldırıldı ({n} / {total} piksel). Fazla/az sildiyse Ctrl+Z yapıp Tolerans'ı değiştir.":
        "Background removed ({n} / {total} pixels). If it removed too much/little, press Ctrl+Z and change Tolerance.",
    "İmleç İçin Görsel Seç": "Choose an Image for the Cursor",
    "Görsel Dosyaları": "Image Files",
    "Tüm Dosyalar": "All Files",
    "Görsel desteği hazırlanıyor (Pillow), lütfen bekleyin...": "Preparing image support (Pillow), please wait...",
    "Pillow Bulunamadı": "Pillow Not Found",
    "Görsel yüklemek için gereken Pillow kütüphanesi kurulamadı.\nİnternet bağlantınızı kontrol edip tekrar deneyin.":
        "The Pillow library needed to import images could not be installed.\nCheck your internet connection and try again.",
    " Arka plan kaldırıldı.": " Background removed.",
    "'{name}' {n}x{n} piksel olarak aktarıldı ve geçmişe eklendi.{extra}": "'{name}' imported as {n}x{n} pixels and added to history.{extra}",
    "Görsel Hatası": "Image Error",
    "Görsel yüklenemedi:\n{e}": "Could not load the image:\n{e}",
    "İmleci Kaydet": "Save Cursor",
    "Windows İmleç Dosyası": "Windows Cursor File",
    "Kaydedildi: {name}": "Saved: {name}",
    "Kayıt Hatası": "Save Error",
    "Dosya kaydedilemedi:\n{e}": "Could not save the file:\n{e}",
    "Platform Uyarısı": "Platform Warning",
    "Sistem imleci değiştirme yalnızca Windows'ta çalışır.": "Changing the system cursor only works on Windows.",
    "Uyarı": "Warning",
    "Tamamen boş bir imleç uygulayamazsınız! Lütfen önce çizim yapın.": "You can't apply an empty cursor! Please draw something first.",
    "İmleç uygulandı ve kalıcı olarak kaydedildi. Bilgisayar yeniden başlasa da kalacak.":
        "Cursor applied and saved permanently. It will stay after restarting the computer.",
    "İmleç uygulandı ama kalıcı kaydedilemedi ({e}). Yeniden başlatınca sıfırlanabilir.":
        "Cursor applied but could not be saved permanently ({e}). It may reset after a restart.",
    "Sistem Hatası": "System Error",
    "İmleç uygulanırken hata oluştu:\n{e}": "An error occurred while applying the cursor:\n{e}",
    "Varsayılan Windows imleci geri yüklendi.": "Default Windows cursor restored.",
    "Varsayılan imleç geri yüklenemedi:\n{e}": "Could not restore the default cursor:\n{e}",
    "Son çalışman geri yüklendi.": "Your last work was restored.",
    "Geçmişi Temizle": "Clear History",
    "Tüm geçmiş silinsin mi?": "Delete all history?",
    "Geçmişten açıldı: {name}": "Opened from history: {name}",
    "Güncellemeleri denetle": "Check for updates",
    "Denetleniyor...": "Checking...",
    "Yeni sürüm: v{v}": "New version: v{v}",
    "Güncelleme": "Update",
    "En güncel sürümü kullanıyorsun (v{v}).": "You're using the latest version (v{v}).",
    "Güncelleme sunucusuna ulaşılamadı. İnternet bağlantını kontrol edip tekrar dene.\n\n{e}":
        "Couldn't reach the update server. Check your internet connection and try again.\n\n{e}",
    "Yeni bir sürüm var!\n\nSendeki sürüm: v{cur}\nYeni sürüm: v{new}\n\nYeni sürüme güncellemek ister misin?":
        "A new version is available!\n\nYour version: v{cur}\nNew version: v{new}\n\nDo you want to update to the new version?",
    "Güncelleniyor": "Updating",
    "Yeni sürüm indiriliyor... %{p}": "Downloading the new version... {p}%",
    "Yeni sürüm indiriliyor...": "Downloading the new version...",
    "İndirilen dosya doğrulanamadı (dosya bozuk veya sunucu henüz güncellenmemiş). Birkaç dakika sonra tekrar dene.":
        "The downloaded file couldn't be verified (corrupted, or the server isn't updated yet). Try again in a few minutes.",
    "Güncelleme yapılamadı:\n{e}\n\nİndirme sayfası açılsın mı?":
        "The update failed:\n{e}\n\nOpen the download page?",
    "Güncelleme tamamlandı. Uygulama yeniden başlatılıyor...": "Update complete. Restarting the app...",
}


def T(text: str, **kw) -> str:
    if LANG == "en":
        text = EN.get(text, text)
    return text.format(**kw) if kw else text


def data_dir() -> str:
    """Ayarlar, geçmiş ve kalıcı imleç dosyalarının klasörü."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "PixelCursorStudio")
    os.makedirs(os.path.join(path, "cursors"), exist_ok=True)
    return path


def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, data):
    """Önce geçici dosyaya yazar, sonra değiştirir: elektrik kesilse bile dosya bozulmaz."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def encode_pixels(pixels) -> str:
    return "".join((c[1:] if c else "------") for row in pixels for c in row)


def decode_pixels(text: str, size: int):
    out = []
    for y in range(size):
        row = []
        for x in range(size):
            chunk = text[(y * size + x) * 6:(y * size + x) * 6 + 6]
            row.append(None if (not chunk or chunk == "------") else "#" + chunk.upper())
        out.append(row)
    return out


def hex_to_rgb(hex_str: str):
    h = hex_str.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def tolerance_to_dist(tolerance: float) -> float:
    return max(0.0, min(100.0, tolerance)) / 100.0 * MAX_COLOR_DIST


def _close(a, b, limit_sq):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2 <= limit_sq


def erase_similar_region(pixels, seeds, tolerance: float) -> int:
    """seeds noktalarından başlayıp her tohumun rengine benzeyen BİTİŞİK pikselleri siler.

    Şeffaf (None) pikseller geçilebilir ama referans rengi olmadığı için
    yalnızca renkli bir tohumdan gelen yayılma renkli piksel siler.
    Silinen piksel sayısını döndürür.
    """
    n = len(pixels)
    limit_sq = tolerance_to_dist(tolerance) ** 2
    queue = deque()
    seen = set()
    for (x, y) in seeds:
        if (x, y) in seen:
            continue
        seen.add((x, y))
        c = pixels[y][x]
        queue.append((x, y, hex_to_rgb(c) if c else None))
    removed = 0
    while queue:
        x, y, ref = queue.popleft()
        c = pixels[y][x]
        if c is not None:
            if ref is None or not _close(hex_to_rgb(c), ref, limit_sq):
                continue
            pixels[y][x] = None
            removed += 1
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < n and 0 <= ny < n and (nx, ny) not in seen:
                seen.add((nx, ny))
                queue.append((nx, ny, ref))
    return removed


def find_background_seeds(pixels, tolerance: float):
    """Çizimin dış çerçevesinde (dolu piksellerin sınır kutusu) baskın bir arka plan
    rengi arar. Çerçevenin çoğu doluysa ve tek bir renk baskınsa o pikselleri döndürür;
    zaten şeffaf arka planlı çizimlerde (ör. ok imleci) boş liste döner, böylece
    çizimin kendisi silinmez.
    """
    n = len(pixels)
    filled = [(x, y) for y in range(n) for x in range(n) if pixels[y][x]]
    if not filled:
        return []
    x0 = min(p[0] for p in filled); x1 = max(p[0] for p in filled)
    y0 = min(p[1] for p in filled); y1 = max(p[1] for p in filled)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return []
    perim = [(x, y0) for x in range(x0, x1 + 1)] + [(x, y1) for x in range(x0, x1 + 1)]
    perim += [(x0, y) for y in range(y0 + 1, y1)] + [(x1, y) for y in range(y0 + 1, y1)]
    on = [(x, y) for (x, y) in perim if pixels[y][x]]
    if len(on) < 0.7 * len(perim):
        return []
    limit_sq = tolerance_to_dist(tolerance) ** 2
    rgbs = [hex_to_rgb(pixels[y][x]) for (x, y) in on]
    best, best_count = None, 0
    for cand in rgbs[::max(1, len(rgbs) // 64)]:
        count = sum(1 for c in rgbs if _close(c, cand, limit_sq))
        if count > best_count:
            best, best_count = cand, count
    if best_count < 0.5 * len(on):
        return []
    return [p for p, c in zip(on, rgbs) if _close(c, best, limit_sq)]


def edge_cells(n: int):
    cells = [(x, 0) for x in range(n)] + [(x, n - 1) for x in range(n)]
    cells += [(0, y) for y in range(1, n - 1)] + [(n - 1, y) for y in range(1, n - 1)]
    return cells


def remove_image_background(img, tolerance: float, max_side: int = 320):
    """Pillow RGBA görselinin kenarlardan başlayan düz/benzer renkli arka planını şeffaf yapar.

    Hız için önce görsel en fazla max_side piksele küçültülür (tuval zaten en fazla 64 px).
    """
    w, h = img.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.LANCZOS)
        w, h = img.size
    px = img.load()
    limit_sq = tolerance_to_dist(tolerance) ** 2
    queue = deque()
    seen = bytearray(w * h)
    for x in range(w):
        for y in (0, h - 1):
            if not seen[y * w + x]:
                seen[y * w + x] = 1
                queue.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if not seen[y * w + x]:
                seen[y * w + x] = 1
                queue.append((x, y))
    # Her kenar pikseli kendi rengini referans alır (degrade arka planlar için)
    refs = {}
    for (x, y) in queue:
        r, g, b, a = px[x, y]
        refs[(x, y)] = None if a < 32 else (r, g, b)
    queue = deque((x, y, refs[(x, y)]) for (x, y) in queue)
    while queue:
        x, y, ref = queue.popleft()
        r, g, b, a = px[x, y]
        if a >= 32:
            if ref is None:
                ref = (r, g, b)  # şeffaf kenardan gelinen ilk opak piksel: dur
                continue
            if not _close((r, g, b), ref, limit_sq):
                continue
        px[x, y] = (r, g, b, 0)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx]:
                seen[ny * w + nx] = 1
                queue.append((nx, ny, ref))
    return img


def resample_pixels(pixels, new_size: int):
    """Piksel ızgarasını en yakın komşu yöntemiyle başka bir boyuta taşır."""
    old = len(pixels)
    return [[pixels[y * old // new_size][x * old // new_size] for x in range(new_size)]
            for y in range(new_size)]


# ---------------------------------------------------------------------------
# Kayıt defteri yardımcıları (yalnızca Windows)
# ---------------------------------------------------------------------------
def reg_read(name):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CURSOR_REG_KEY) as k:
            value, typ = winreg.QueryValueEx(k, name)
            return value, typ
    except FileNotFoundError:
        return None, None


def reg_write(name, value, typ=None):
    import winreg
    if typ is None:
        typ = winreg.REG_EXPAND_SZ
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, CURSOR_REG_KEY, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, typ, value)


def reg_delete(name):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CURSOR_REG_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, name)
    except FileNotFoundError:
        pass


def reload_system_cursors():
    """Windows'a imleçleri kayıt defterinden yeniden yüklemesini söyler."""
    ctypes.windll.user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, SPIF_UPDATE_AND_BROADCAST)


class PixelCursorStudio:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(T("PixelCursor Studio - İmleç Tasarla & Değiştir"))
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self.data_path = data_dir()
        self.state_file = os.path.join(self.data_path, "state.json")
        self.history_file = os.path.join(self.data_path, "history.json")
        self.settings = read_json(self.state_file, {})
        self.history = read_json(self.history_file, [])
        global LANG
        LANG = self.settings.get("lang", "tr") if self.settings.get("lang") in ("tr", "en") else "tr"
        if not isinstance(self.history, list):
            self.history = []

        # Durum Değişkenleri
        grid = self.settings.get("grid", 32)
        self.grid = grid if grid in GRID_CHOICES else 32
        self.cell = CANVAS_PX // self.grid
        self.pixels = [[None] * self.grid for _ in range(self.grid)]
        self.undo_stack = []
        self.current_color = self.settings.get("color", "#00F5D4")
        self.current_tool = tk.StringVar(value="pencil")
        self.show_grid = tk.BooleanVar(value=True)
        self.target_cursor_mode = tk.StringVar(value=self.settings.get("target_mode", "normal"))
        size = str(self.settings.get("screen_size", ""))
        self.screen_size = tk.StringVar(value=size if size.isdigit() else T("Windows ayarı"))
        self.grid_var = tk.IntVar(value=self.grid)
        brush = self.settings.get("brush", 1)
        self.brush_var = tk.IntVar(value=brush if brush in BRUSH_CHOICES else 1)
        self.tolerance_var = tk.IntVar(value=int(self.settings.get("tolerance", 15)))
        self.auto_bg_var = tk.BooleanVar(value=bool(self.settings.get("auto_bg", True)))
        self._area_start = None
        self._pending_update = None   # açılışta bulunan yeni sürüm bilgisi
        self._updating = False
        self._ui_queue = queue.Queue()  # arka plan iş parçacıklarından arayüze mesajlar
        self._import_src = None  # (dosya yolu, ızgara, pikseller) - son yüklenen görsel
        self.hotspot = [0, 0]  # [x, y]
        self._save_job = None
        self._history_images = []

        # Varsayılan Renk Paleti (Retro / Oyun Paleti)
        self.palette = [
            "#FFFFFF", "#000000", "#FF0055", "#FF5500",
            "#FFCC00", "#00F5D4", "#00BBF9", "#9B5DE5",
            "#F15BB5", "#00F566", "#8D99AE", "#2B2D42",
            "#E63946", "#FFB703", "#8ECAE6", "#588157"
        ]

        self._setup_styles()
        self._build_ui()
        self._build_canvas_cells()

        if not self._restore_last_session():
            self._load_template_arrow(record_undo=False)
        self._render_history()

        # Kısayollar
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-Z>", lambda e: self.undo())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.current_tool.trace_add("write", lambda *_: self._show_tool_hint())
        self._show_tool_hint()
        cleanup_old_exe()
        self._poll_ui_queue()
        # Açılışta sessizce yeni sürüm var mı bak (internet yoksa hiçbir şey göstermez)
        threading.Thread(target=self._background_update_check, daemon=True).start()

    # ------------------------------------------------------------------ UI --
    def _setup_styles(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Dark.TNotebook", background=PANEL, borderwidth=0)
        style.configure("Dark.TNotebook.Tab", background=BTN, foreground=FG,
                        padding=(14, 6), font=("Segoe UI", 9, "bold"), borderwidth=0)
        style.map("Dark.TNotebook.Tab",
                  background=[("selected", "#00F5D4")],
                  foreground=[("selected", "#11111B")])
        style.configure("Dark.TFrame", background=PANEL)
        style.configure("Dark.Vertical.TScrollbar", background=BTN, troughcolor=PANEL,
                        bordercolor=PANEL, arrowcolor=FG, lightcolor=BTN, darkcolor=BTN,
                        gripcount=0)
        style.map("Dark.Vertical.TScrollbar", background=[("active", "#45475A")])
        style.configure("Dark.Horizontal.TScale", background="#00F5D4", troughcolor=BTN,
                        bordercolor=PANEL, lightcolor="#00F5D4", darkcolor="#00F5D4")
        style.configure("Dark.TCombobox", fieldbackground=BTN, background=BTN,
                        foreground=FG, arrowcolor=FG, bordercolor="#45475A",
                        lightcolor=BTN, darkcolor=BTN)
        style.map("Dark.TCombobox",
                  fieldbackground=[("readonly", BTN)],
                  foreground=[("readonly", FG)],
                  selectbackground=[("readonly", BTN)],
                  selectforeground=[("readonly", FG)],
                  background=[("active", "#45475A"), ("readonly", BTN)])
        self.root.option_add("*TCombobox*Listbox.background", BTN)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)
        self.root.option_add("*TCombobox*Listbox.selectBackground", "#00F5D4")
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#11111B")

    def _section(self, parent, text, top=12):
        tk.Label(parent, text=T(text), fg=FG, bg=PANEL,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(top, 4))

    def _build_ui(self):
        main_frame = tk.Frame(self.root, bg=BG, padx=16, pady=16)
        main_frame.pack(fill="both", expand=True)
        self.main_frame = main_frame

        # SOL PANEL: Araçlar ve Renk Paleti
        left_panel = tk.Frame(main_frame, bg=PANEL, padx=12, pady=12)
        left_panel.grid(row=0, column=0, sticky="ns", padx=(0, 14))

        self._section(left_panel, "ARAÇLAR", top=0)
        tools = [
            ("Kalem", "pencil"),
            ("Silgi", "eraser"),
            ("Boya Kovası", "fill"),
            ("Renk Seçici", "picker"),
            ("Sihirli Silgi", "magic"),
            ("Alan Silgisi", "area"),
            ("Tıklama Noktası (Hotspot)", "hotspot"),
        ]
        tool_grid = tk.Frame(left_panel, bg=PANEL)
        tool_grid.pack(fill="x")
        for idx, (text, val) in enumerate(tools):
            last = idx == len(tools) - 1
            tk.Radiobutton(
                tool_grid, text=T(text), variable=self.current_tool, value=val,
                bg=BTN if val in ("magic", "area") else PANEL, fg=FG, selectcolor="#45475A",
                activebackground=PANEL, activeforeground="#89B4FA",
                font=("Segoe UI", 9), indicatoron=False,
                pady=4, bd=0, highlightthickness=0
            ).grid(row=idx // 2, column=idx % 2, columnspan=2 if last else 1,
                   sticky="ew", padx=2, pady=2)
        tool_grid.columnconfigure(0, weight=1, uniform="t")
        tool_grid.columnconfigure(1, weight=1, uniform="t")

        brush_row = tk.Frame(left_panel, bg=PANEL)
        brush_row.pack(fill="x", pady=(6, 0))
        tk.Label(brush_row, text=T("Fırça:"), fg=MUTED, bg=PANEL,
                 font=("Segoe UI", 9)).pack(side="left", padx=(2, 6))
        for b in BRUSH_CHOICES:
            tk.Radiobutton(
                brush_row, text=str(b), variable=self.brush_var, value=b,
                command=self._schedule_save,
                bg=PANEL, fg=FG, selectcolor="#00F5D4", activebackground=PANEL,
                font=("Segoe UI", 9, "bold"), indicatoron=False, width=3, pady=2,
                bd=0, highlightthickness=0
            ).pack(side="left", padx=2, expand=True, fill="x")

        tol_row = tk.Frame(left_panel, bg=PANEL)
        tol_row.pack(fill="x", pady=(4, 0))
        tk.Label(tol_row, text=T("Tolerans:"), fg=MUTED, bg=PANEL,
                 font=("Segoe UI", 9)).pack(side="left", padx=(2, 0), anchor="s", pady=(0, 2))
        self.tol_value_lbl = tk.Label(tol_row, text=str(self.tolerance_var.get()), fg=FG, bg=PANEL,
                                      font=("Consolas", 9, "bold"), width=3)
        self.tol_value_lbl.pack(side="right")
        ttk.Scale(
            tol_row, from_=0, to=100, orient="horizontal", style="Dark.Horizontal.TScale",
            command=self._on_tolerance
        ).pack(side="left", fill="x", expand=True, padx=(6, 4))
        tol_row.winfo_children()[-1].set(self.tolerance_var.get())

        tk.Checkbutton(
            left_panel, text=T("Izgarayı Göster"), variable=self.show_grid,
            command=self._refresh_canvas_grid, bg=PANEL, fg=MUTED,
            selectcolor=BTN, activebackground=PANEL, font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(2, 0))

        self._section(left_panel, "TUVAL BOYUTU", top=6)
        size_row = tk.Frame(left_panel, bg=PANEL)
        size_row.pack(fill="x")
        for n in GRID_CHOICES:
            tk.Radiobutton(
                size_row, text=f"{n}x{n}", variable=self.grid_var, value=n,
                command=lambda n=n: self.change_grid_size(n),
                bg=PANEL, fg=FG, selectcolor="#00F5D4", activebackground=PANEL,
                font=("Segoe UI", 9, "bold"), indicatoron=False, width=6, pady=4,
                bd=0, highlightthickness=0
            ).pack(side="left", padx=2, expand=True, fill="x")

        self._section(left_panel, "AKTİF RENK", top=8)
        color_row = tk.Frame(left_panel, bg=PANEL)
        color_row.pack(fill="x", pady=2)
        self.color_preview = tk.Frame(
            color_row, bg=self.current_color, width=34, height=34,
            highlightbackground=FG, highlightthickness=1
        )
        self.color_preview.pack(side="left", padx=(0, 8))
        tk.Button(
            color_row, text=T("Özel Renk Seç"), command=self.choose_custom_color,
            bg=BTN, fg=FG, activebackground="#45475A",
            relief="flat", font=("Segoe UI", 9), padx=8, pady=6
        ).pack(side="left", fill="x", expand=True)

        palette_frame = tk.Frame(left_panel, bg=PANEL)
        palette_frame.pack(pady=4)
        for idx, hex_col in enumerate(self.palette):
            tk.Button(
                palette_frame, bg=hex_col, activebackground=hex_col, width=3, height=1,
                relief="flat", command=lambda c=hex_col: self.set_color(c)
            ).grid(row=idx // 4, column=idx % 4, padx=2, pady=2)

        self._section(left_panel, "TUVAL İŞLEMLERİ", top=6)
        tk.Button(
            left_panel, text=T("Arka Planı Kaldır"), command=self.remove_background,
            bg="#9B5DE5", fg="#FFFFFF", activebackground="#B07CF0", activeforeground="#FFFFFF",
            font=("Segoe UI", 9, "bold"), relief="flat", pady=5, cursor="hand2"
        ).pack(fill="x", pady=2)
        ops_row = tk.Frame(left_panel, bg=PANEL)
        ops_row.pack(fill="x")
        for text, cmd, color in (("Geri Al (Ctrl+Z)", self.undo, BTN),
                                 ("Temizle", self.clear_canvas, "#45475A")):
            tk.Button(ops_row, text=T(text), command=cmd, bg=color, fg=FG,
                      activebackground="#585B70", activeforeground="#FFFFFF",
                      relief="flat", font=("Segoe UI", 9), pady=4, cursor="hand2"
                      ).pack(side="left", fill="x", expand=True, padx=(0, 2) if cmd == self.undo else (2, 0), pady=2)

        self._section(left_panel, "HAZIR ŞABLONLAR", top=6)
        tpl_row = tk.Frame(left_panel, bg=PANEL)
        tpl_row.pack(fill="x")
        for text, cmd in (("Neon Ok", self._load_template_arrow),
                          ("Kılıç", self._load_template_sword),
                          ("Nişangah", self._load_template_crosshair)):
            tk.Button(tpl_row, text=T(text), command=cmd, bg=BTN, fg=FG,
                      activebackground="#585B70", activeforeground="#FFFFFF",
                      relief="flat", font=("Segoe UI", 9), pady=4, cursor="hand2"
                      ).pack(side="left", fill="x", expand=True, padx=1, pady=2)

        # ORTA PANEL: Piksel Tuvali
        center_panel = tk.Frame(main_frame, bg=BG)
        center_panel.grid(row=0, column=1, sticky="n")

        self.header_lbl = tk.Label(center_panel, fg=MUTED, bg=BG, font=("Segoe UI", 9, "bold"))
        self.header_lbl.pack(pady=(0, 6))

        self.canvas = tk.Canvas(
            center_panel, width=CANVAS_PX, height=CANVAS_PX,
            bg="#262637", highlightthickness=2, highlightbackground="#45475A"
        )
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self.on_left_down)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_up)
        self.canvas.bind("<ButtonPress-3>", self.on_right_down)
        self.canvas.bind("<B3-Motion>", self.on_right_drag)
        self.hint_label = tk.Label(center_panel, text="", fg=MUTED, bg=BG,
                                   font=("Segoe UI", 9), wraplength=CANVAS_PX, justify="center")
        self.hint_label.pack(pady=(8, 0))

        # SAĞ PANEL: Sekmeler (İmleç / Geçmiş)
        right_panel = tk.Frame(main_frame, bg=PANEL, padx=10, pady=10)
        right_panel.grid(row=0, column=2, sticky="ns", padx=(14, 0))

        top_row = tk.Frame(right_panel, bg=PANEL)
        top_row.pack(fill="x", pady=(0, 8))
        for code in ("tr", "en"):
            active = LANG == code
            tk.Button(
                top_row, text=code.upper(), command=lambda c=code: self.set_language(c),
                bg="#00F5D4" if active else BTN, fg="#11111B" if active else FG,
                activebackground="#45475A", relief="flat", font=("Segoe UI", 8, "bold"),
                width=3, pady=2, cursor="hand2"
            ).pack(side="left", padx=(0, 3))
        self.update_btn = tk.Button(
            top_row, text=T("Güncellemeleri denetle"), command=self.check_for_updates,
            bg=BTN, fg=FG, activebackground="#45475A", relief="flat",
            font=("Segoe UI", 8), pady=2, cursor="hand2"
        )
        self.update_btn.pack(side="right", fill="x", expand=True, padx=(6, 0))
        if self._pending_update:
            self._mark_update_available(self._pending_update)

        self.notebook = ttk.Notebook(right_panel, style="Dark.TNotebook")
        self.notebook.pack(fill="both", expand=True)
        tab_main = tk.Frame(self.notebook, bg=PANEL, padx=6, pady=8)
        tab_hist = tk.Frame(self.notebook, bg=PANEL, padx=2, pady=8)
        self.notebook.add(tab_main, text=T("İMLEÇ"))
        self.notebook.add(tab_hist, text=T("GEÇMİŞ"))

        self._build_main_tab(tab_main)
        self._build_history_tab(tab_hist)

    # ------------------------------------------------------- GÜNCELLEME --
    def _post(self, func):
        """Arka plan iş parçacığından arayüz işlemi iste (Tkinter yalnızca ana iş parçacığında güvenli)."""
        self._ui_queue.put(func)

    def _poll_ui_queue(self):
        try:
            while True:
                self._ui_queue.get_nowait()()
        except queue.Empty:
            pass
        try:
            self._poll_job = self.root.after(100, self._poll_ui_queue)
        except tk.TclError:
            pass

    def _background_update_check(self):
        try:
            info = fetch_update_info(timeout=6)
        except Exception:
            return
        if parse_version(info.get("version")) > parse_version(APP_VERSION):
            self._post(lambda: self._mark_update_available(info))

    def _mark_update_available(self, info):
        self._pending_update = info
        try:
            self.update_btn.configure(text="⬆ " + T("Yeni sürüm: v{v}", v=info.get("version")),
                                      bg="#F9E2AF", fg="#11111B")
        except tk.TclError:
            pass

    def check_for_updates(self):
        if self._updating:
            return
        self.update_btn.configure(text=T("Denetleniyor..."))
        self.root.update_idletasks()
        try:
            info = fetch_update_info()
        except Exception as e:
            self.update_btn.configure(text=T("Güncellemeleri denetle"))
            messagebox.showerror(T("Güncelleme"), T(
                "Güncelleme sunucusuna ulaşılamadı. İnternet bağlantını kontrol edip tekrar dene.\n\n{e}", e=e))
            return
        new = info.get("version", "0")
        if parse_version(new) <= parse_version(APP_VERSION):
            self._pending_update = None
            self.update_btn.configure(text=T("Güncellemeleri denetle"), bg=BTN, fg=FG)
            messagebox.showinfo(T("Güncelleme"), T("En güncel sürümü kullanıyorsun (v{v}).", v=APP_VERSION))
            return
        self._mark_update_available(info)
        if messagebox.askyesno(T("Güncelleme"), T(
                "Yeni bir sürüm var!\n\nSendeki sürüm: v{cur}\nYeni sürüm: v{new}\n\n"
                "Yeni sürüme güncellemek ister misin?", cur=APP_VERSION, new=new)):
            self._start_update(info)

    def _start_update(self, info):
        """İndirmeyi arka planda yapar; arayüz donmaz, ilerleme penceresi gösterir."""
        kind = "exe" if IS_FROZEN else "pyw"
        url, expected = info.get(f"{kind}_url"), (info.get(f"{kind}_sha256") or "").lower()
        target = sys.executable if IS_FROZEN else os.path.abspath(__file__)
        if not url:
            self._update_failed("version.json: missing URL")
            return
        self._updating = True
        self._save_now()

        win = tk.Toplevel(self.root)
        win.title(T("Güncelleniyor"))
        win.configure(bg=PANEL, padx=20, pady=16)
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        win.protocol("WM_DELETE_WINDOW", lambda: None)  # indirme sürerken kapatılmasın
        label = tk.Label(win, text=T("Yeni sürüm indiriliyor..."), fg=FG, bg=PANEL, font=("Segoe UI", 10))
        label.pack(anchor="w")
        bar = ttk.Progressbar(win, length=320, mode="determinate", maximum=100)
        bar.pack(pady=(10, 0))
        self._update_window = win

        def progress(done, total):
            if total:
                pct = int(done * 100 / total)
                self._post(lambda: (bar.configure(value=pct),
                                    label.configure(text=T("Yeni sürüm indiriliyor... %{p}", p=pct))))

        def worker():
            tmp = target + ".download"
            try:
                digest = download_file(url, tmp, progress)
                if expected and digest.lower() != expected:
                    os.remove(tmp)
                    raise ValueError(T("İndirilen dosya doğrulanamadı (dosya bozuk veya sunucu henüz "
                                       "güncellenmemiş). Birkaç dakika sonra tekrar dene."))
                self._post(lambda: self._install_update(tmp, target))
            except Exception as e:
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except OSError:
                    pass
                self._post(lambda e=e: self._update_failed(e))

        threading.Thread(target=worker, daemon=True).start()

    def _install_update(self, new_file: str, target: str):
        try:
            if IS_FROZEN:
                # Çalışan bir exe silinemez ama yeniden adlandırılabilir:
                # eskisini .old yap, yenisini yerine koy (.old bir sonraki açılışta silinir).
                old = target + ".old"
                if os.path.exists(old):
                    os.remove(old)
                os.replace(target, old)
                try:
                    os.replace(new_file, target)
                except Exception:
                    os.replace(old, target)  # geri al
                    raise
                cmd = [target]
            else:
                os.replace(new_file, target)
                cmd = [sys.executable, target]
        except Exception as e:
            self._update_failed(e)
            return
        self.status_label.configure(text=T("Güncelleme tamamlandı. Uygulama yeniden başlatılıyor..."))
        self.root.update_idletasks()
        flags = 0x00000008 if sys.platform == "win32" else 0  # DETACHED_PROCESS
        subprocess.Popen(cmd, env=clean_env_for_relaunch(), close_fds=True, creationflags=flags,
                         cwd=os.path.dirname(target))
        self.on_close()

    def _update_failed(self, error):
        self._updating = False
        win = getattr(self, "_update_window", None)
        if win is not None:
            try:
                win.grab_release()
                win.destroy()
            except tk.TclError:
                pass
            self._update_window = None
        if messagebox.askyesno(T("Güncelleme"), T("Güncelleme yapılamadı:\n{e}\n\nİndirme sayfası açılsın mı?",
                                                   e=error)):
            webbrowser.open(REPO_PAGE_URL)

    def set_language(self, lang: str):
        """Dili değiştirir ve arayüzü çizimi kaybetmeden yeniden kurar."""
        global LANG
        if lang == LANG:
            return
        old_default = T("Windows ayarı")
        LANG = lang
        self.settings["lang"] = lang
        if self.screen_size.get() == old_default:
            self.screen_size.set(T("Windows ayarı"))
        tab = self.notebook.index("current")
        self.main_frame.destroy()
        self.root.title(T("PixelCursor Studio - İmleç Tasarla & Değiştir"))
        self._build_ui()
        self._build_canvas_cells()
        self.redraw_all()
        self._render_history()
        self._show_tool_hint()
        self.notebook.select(tab)
        self._save_now()

    def _build_main_tab(self, tab):
        self._section(tab, "GERÇEK BOYUT (1:1)", top=0)
        preview_box = tk.Frame(tab, bg="#11111B", padx=10, pady=10)
        preview_box.pack(fill="x", pady=(2, 8))
        self.mini_canvas = tk.Canvas(
            preview_box, width=64, height=64, bg=BG,
            highlightthickness=1, highlightbackground="#585B70"
        )
        self.mini_canvas.pack(side="left", padx=(4, 12))
        self.hotspot_label = tk.Label(
            preview_box, text="", fg=MUTED, bg="#11111B",
            font=("Consolas", 9), justify="left"
        )
        self.hotspot_label.pack(side="left")
        self.mini_image = None

        self._section(tab, "DOSYA İŞLEMLERİ", top=4)
        self._make_btn(tab, "Görsel Yükle (PNG/JPG/GIF)", self.import_image, BTN)
        tk.Checkbutton(
            tab, text=T("Yüklerken arka planı otomatik kaldır"), variable=self.auto_bg_var,
            command=self._schedule_save, bg=PANEL, fg=FG, selectcolor=BTN,
            activebackground=PANEL, font=("Segoe UI", 8)
        ).pack(anchor="w", pady=(0, 2))
        self._make_btn(tab, ".CUR Olarak Kaydet", self.export_cur_dialog, BTN)

        self._section(tab, "BİLGİSAYARA UYGULA", top=12)
        modes = [
            ("Standart Fare Oku", "normal"),
            ("El İmleci (Link Seçimi)", "hand"),
            ("Nişangah (Crosshair)", "cross"),
            ("Tüm Ana İmleçler", "all"),
        ]
        for text, val in modes:
            tk.Radiobutton(
                tab, text=T(text), variable=self.target_cursor_mode, value=val,
                bg=PANEL, fg=FG, selectcolor=BTN,
                activebackground=PANEL, font=("Segoe UI", 9)
            ).pack(anchor="w", pady=0)

        size_row = tk.Frame(tab, bg=PANEL)
        size_row.pack(fill="x", pady=(8, 0))
        tk.Label(size_row, text=T("Ekranda boyut:"), fg=MUTED, bg=PANEL,
                 font=("Segoe UI", 9)).pack(side="left")
        ttk.Combobox(
            size_row, textvariable=self.screen_size, state="readonly", width=13,
            values=(T("Windows ayarı"), "32", "48", "64"), style="Dark.TCombobox"
        ).pack(side="left", padx=(6, 0))

        tk.Button(
            tab, text=T("İMLECİ ŞİMDİ UYGULA"),
            command=self.apply_cursor_to_system,
            bg="#00F5D4", fg="#11111B", activebackground="#00BBF9",
            font=("Segoe UI", 10, "bold"), relief="flat", pady=9, cursor="hand2"
        ).pack(fill="x", pady=(10, 4))

        tk.Button(
            tab, text=T("Varsayılan Windows İmlecine Dön"),
            command=self.restore_default_cursors,
            bg="#F38BA8", fg="#11111B", activebackground="#EBA0AC",
            font=("Segoe UI", 9, "bold"), relief="flat", pady=6, cursor="hand2"
        ).pack(fill="x", pady=2)

        self.status_label = tk.Label(
            tab, text=T("Hazır."), fg="#A6E3A1", bg=PANEL,
            font=("Segoe UI", 9), wraplength=220, justify="left"
        )
        self.status_label.pack(anchor="w", pady=(10, 0))

    def _build_history_tab(self, tab):
        top = tk.Frame(tab, bg=PANEL)
        top.pack(fill="x", padx=4)
        tk.Label(top, text=T("Yüklenen görseller ve\nuygulanan imleçler"), fg=MUTED, bg=PANEL,
                 font=("Segoe UI", 8), justify="left").pack(side="left")
        tk.Button(top, text=T("Temizle"), command=self.clear_history, bg="#45475A", fg=FG,
                  activebackground="#585B70", relief="flat", font=("Segoe UI", 8),
                  padx=6, pady=2).pack(side="right")

        holder = tk.Frame(tab, bg=PANEL)
        holder.pack(fill="both", expand=True, pady=(8, 0))
        self.hist_canvas = tk.Canvas(holder, bg=PANEL, highlightthickness=0, width=236, height=560)
        scroll = ttk.Scrollbar(holder, orient="vertical", command=self.hist_canvas.yview,
                               style="Dark.Vertical.TScrollbar")
        self.hist_canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.hist_canvas.pack(side="left", fill="both", expand=True)
        self.hist_inner = tk.Frame(self.hist_canvas, bg=PANEL)
        self.hist_canvas.create_window((0, 0), window=self.hist_inner, anchor="nw")
        self.hist_inner.bind(
            "<Configure>",
            lambda e: self.hist_canvas.configure(scrollregion=self.hist_canvas.bbox("all")))
        self.hist_canvas.bind("<Enter>", lambda e: self.root.bind_all("<MouseWheel>", self._on_hist_wheel))
        self.hist_canvas.bind("<Leave>", lambda e: self.root.unbind_all("<MouseWheel>"))

    def _on_hist_wheel(self, event):
        self.hist_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _make_btn(self, parent, text, cmd, bg_color):
        btn = tk.Button(
            parent, text=T(text), command=cmd, bg=bg_color, fg=FG,
            activebackground="#585B70", activeforeground="#FFFFFF",
            relief="flat", font=("Segoe UI", 9), pady=4, cursor="hand2"
        )
        btn.pack(fill="x", pady=2)
        return btn

    # ------------------------------------------------------------ TUVAL --
    def _checker(self, x, y):
        return "#2A2B3C" if (x + y) % 2 == 0 else "#202130"

    def _build_canvas_cells(self):
        """Seçili ızgara boyutuna göre tuval hücrelerini (yeniden) oluşturur."""
        self.canvas.delete("all")
        self.cell = CANVAS_PX // self.grid
        size = self.cell * self.grid
        self.canvas.configure(width=size, height=size)
        outline = "#36384C" if self.show_grid.get() else ""
        self.rect_ids = []
        for y in range(self.grid):
            row = []
            for x in range(self.grid):
                x1, y1 = x * self.cell, y * self.cell
                row.append(self.canvas.create_rectangle(
                    x1, y1, x1 + self.cell, y1 + self.cell,
                    fill=self._checker(x, y), outline=outline))
            self.rect_ids.append(row)
        self.hotspot_marker = self.canvas.create_oval(0, 0, 0, 0, outline="#FF0055", width=2)
        self.mini_image = tk.PhotoImage(width=self.grid, height=self.grid)
        self.mini_canvas.delete("all")
        self.mini_canvas.configure(width=self.grid, height=self.grid)
        self.mini_canvas.create_image(0, 0, image=self.mini_image, anchor="nw")
        self.header_lbl.configure(
            text=T("{n}x{n} PİKSEL TASARIM ALANI (Sol Tık: Çiz / Sağ Tık: Sil)", n=self.grid))
        self.grid_var.set(self.grid)

    def change_grid_size(self, new_size: int):
        if new_size == self.grid:
            return
        self.save_undo_state()
        old = self.grid
        self.pixels = resample_pixels(self.pixels, new_size)
        self.hotspot = [min(new_size - 1, self.hotspot[0] * new_size // old),
                        min(new_size - 1, self.hotspot[1] * new_size // old)]
        self.grid = new_size
        self._build_canvas_cells()
        self.redraw_all()
        self.status_label.configure(text=T("Tuval {n}x{n} olarak ayarlandı.", n=new_size))

    def set_color(self, hex_color: str):
        self.current_color = hex_color
        self.color_preview.configure(bg=hex_color)
        if self.current_tool.get() in ("eraser", "hotspot", "picker"):
            self.current_tool.set("pencil")
        self._schedule_save()

    def choose_custom_color(self):
        color = colorchooser.askcolor(color=self.current_color, title=T("Renk Seç"))
        if color and color[1]:
            self.set_color(color[1].upper())

    def save_undo_state(self):
        self.undo_stack.append((self.grid, [row[:] for row in self.pixels], self.hotspot[:]))
        if len(self.undo_stack) > 30:
            self.undo_stack.pop(0)

    def undo(self):
        if not self.undo_stack:
            self.status_label.configure(text=T("Geri alınacak işlem yok."))
            return
        grid, pixels, hotspot = self.undo_stack.pop()
        self.pixels, self.hotspot = pixels, hotspot
        if grid != self.grid:
            self.grid = grid
            self._build_canvas_cells()
        self.redraw_all()
        self.status_label.configure(text=T("Son işlem geri alındı."))

    def clear_canvas(self):
        self.save_undo_state()
        self.pixels = [[None] * self.grid for _ in range(self.grid)]
        self.redraw_all()
        self.status_label.configure(text=T("Tuval temizlendi."))

    def _get_cell_coords(self, event):
        x = event.x // self.cell
        y = event.y // self.cell
        if 0 <= x < self.grid and 0 <= y < self.grid:
            return x, y
        return None, None

    def _on_tolerance(self, value):
        v = int(round(float(value)))
        self.tolerance_var.set(v)
        self.tol_value_lbl.configure(text=str(v))
        self._schedule_save()

    def _show_tool_hint(self):
        hints = TOOL_HINTS_EN if LANG == "en" else TOOL_HINTS
        self.hint_label.configure(text=hints.get(self.current_tool.get(), ""))

    def _paint_brush(self, x, y, color):
        """Fırça boyutunda kare boyar/siler (tıklanan nokta merkezde)."""
        size = self.brush_var.get()
        start = -(size // 2)
        for dy in range(start, start + size):
            for dx in range(start, start + size):
                px, py = x + dx, y + dy
                if 0 <= px < self.grid and 0 <= py < self.grid:
                    self._set_pixel(px, py, color)

    def on_left_down(self, event):
        x, y = self._get_cell_coords(event)
        if x is None:
            return
        tool = self.current_tool.get()

        if tool == "hotspot":
            self.save_undo_state()
            self.hotspot = [x, y]
            self._update_hotspot_visual()
            self._schedule_save()
            self.status_label.configure(text=T("Tıklama noktası ({x}, {y}) olarak ayarlandı.", x=x, y=y))
            return

        if tool == "picker":
            picked = self.pixels[y][x]
            if picked:
                self.set_color(picked)
                self.status_label.configure(text=T("Renk seçildi: {c}", c=picked))
            return

        if tool == "area":
            self._area_start = (x, y)
            self._draw_area_rect(x, y)
            return

        if tool == "magic":
            if self.pixels[y][x] is None:
                return
            self.save_undo_state()
            removed = erase_similar_region(self.pixels, [(x, y)], self.tolerance_var.get())
            self.redraw_all()
            self.status_label.configure(text=T("Sihirli silgi: {n} piksel silindi.", n=removed))
            return

        self.save_undo_state()
        if tool == "fill":
            self.flood_fill(x, y, self.current_color)
            self.redraw_all()
        elif tool == "eraser":
            self._paint_brush(x, y, None)
        else:
            self._paint_brush(x, y, self.current_color)

    def on_left_drag(self, event):
        tool = self.current_tool.get()
        if tool == "area" and self._area_start:
            x = min(max(event.x // self.cell, 0), self.grid - 1)
            y = min(max(event.y // self.cell, 0), self.grid - 1)
            self._draw_area_rect(x, y)
            return
        x, y = self._get_cell_coords(event)
        if x is None:
            return
        if tool == "pencil":
            self._paint_brush(x, y, self.current_color)
        elif tool == "eraser":
            self._paint_brush(x, y, None)

    def on_left_up(self, event):
        if self.current_tool.get() != "area" or not self._area_start:
            return
        x0, y0 = self._area_start
        x1 = min(max(event.x // self.cell, 0), self.grid - 1)
        y1 = min(max(event.y // self.cell, 0), self.grid - 1)
        self._area_start = None
        self.canvas.delete("area_sel")
        self.erase_area(x0, y0, x1, y1)

    def _draw_area_rect(self, x, y):
        x0, y0 = self._area_start
        self.canvas.delete("area_sel")
        self.canvas.create_rectangle(
            min(x0, x) * self.cell, min(y0, y) * self.cell,
            (max(x0, x) + 1) * self.cell, (max(y0, y) + 1) * self.cell,
            outline="#FF0055", width=2, dash=(4, 3), tags="area_sel")

    def erase_area(self, x0, y0, x1, y1):
        self.save_undo_state()
        for y in range(min(y0, y1), max(y0, y1) + 1):
            for x in range(min(x0, x1), max(x0, x1) + 1):
                self.pixels[y][x] = None
        self.redraw_all()
        self.status_label.configure(
            text=T("Alan silindi: {w}x{h} piksel.", w=abs(x1 - x0) + 1, h=abs(y1 - y0) + 1))

    def remove_background(self):
        """Arka planı tek tıkla siler.

        Tuval, yüklenen bir görselden geldiyse ve sonradan değiştirilmediyse arka plan
        orijinal görselden (yüksek çözünürlükte) kaldırılır ve nesne tuvale yeniden
        sığdırılır. Aksi halde tuvaldeki piksellerden kaldırılır.
        """
        if not self._has_pixels():
            self.status_label.configure(text=T("Tuval zaten boş."))
            return
        before = sum(1 for row in self.pixels for c in row if c)
        src = self._import_src
        if (src and src[1] == self.grid and src[2] == encode_pixels(self.pixels)
                and os.path.exists(src[0]) and load_pillow() is not None):
            self.save_undo_state()
            try:
                self._place_image(src[0], True)
            except Exception:
                self.undo()
                return
            if encode_pixels(self.pixels) == src[2]:
                self.undo_stack.pop()
                self.status_label.configure(
                    text=T("Kenarlara bağlı bir arka plan bulunamadı. Sihirli silgi veya Alan silgisini dene."))
                return
            self.status_label.configure(
                text=T("Arka plan orijinal görselden kaldırıldı ve nesne tuvale sığdırıldı. "
                       "Fazla/az sildiyse Ctrl+Z yapıp Tolerans'ı değiştir."))
            return

        seeds = find_background_seeds(self.pixels, self.tolerance_var.get())
        self.save_undo_state()
        removed = erase_similar_region(self.pixels, seeds, self.tolerance_var.get()) if seeds else 0
        if removed == 0:
            self.undo_stack.pop()
            self.status_label.configure(
                text=T("Kenarlara bağlı bir arka plan bulunamadı. Sihirli silgi veya Alan silgisini dene."))
            return
        self.redraw_all()
        self.status_label.configure(
            text=T("Arka plan kaldırıldı ({n} / {total} piksel). "
                   "Fazla/az sildiyse Ctrl+Z yapıp Tolerans'ı değiştir.", n=removed, total=before))

    def on_right_down(self, event):
        x, y = self._get_cell_coords(event)
        if x is None:
            return
        self.save_undo_state()
        self._paint_brush(x, y, None)

    def on_right_drag(self, event):
        x, y = self._get_cell_coords(event)
        if x is not None:
            self._paint_brush(x, y, None)

    def _set_pixel(self, x: int, y: int, color):
        if self.pixels[y][x] == color:
            return
        self.pixels[y][x] = color
        self.canvas.itemconfig(self.rect_ids[y][x], fill=color or self._checker(x, y))
        self.mini_image.put(color or BG, (x, y))
        self._schedule_save()

    def flood_fill(self, start_x: int, start_y: int, new_color: str):
        target_color = self.pixels[start_y][start_x]
        if target_color == new_color:
            return
        queue = deque([(start_x, start_y)])
        while queue:
            cx, cy = queue.popleft()
            if self.pixels[cy][cx] != target_color:
                continue
            self.pixels[cy][cx] = new_color
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if 0 <= nx < self.grid and 0 <= ny < self.grid:
                    queue.append((nx, ny))

    def _refresh_canvas_grid(self):
        outline = "#36384C" if self.show_grid.get() else ""
        for row in self.rect_ids:
            for rid in row:
                self.canvas.itemconfig(rid, outline=outline)

    def _update_hotspot_visual(self):
        hx, hy = self.hotspot
        pad = max(1, self.cell // 5)
        self.canvas.coords(self.hotspot_marker,
                           hx * self.cell + pad, hy * self.cell + pad,
                           (hx + 1) * self.cell - pad, (hy + 1) * self.cell - pad)
        self.canvas.tag_raise(self.hotspot_marker)
        self.hotspot_label.configure(
            text=T("Boyut: {n}x{n}\nHotspot: ({x}, {y})", n=self.grid, x=hx, y=hy))

    def _update_mini_preview(self):
        rows = []
        for y in range(self.grid):
            rows.append("{" + " ".join((c or BG) for c in self.pixels[y]) + "}")
        self.mini_image.put(" ".join(rows), to=(0, 0))

    def redraw_all(self):
        for y in range(self.grid):
            for x in range(self.grid):
                col = self.pixels[y][x]
                self.canvas.itemconfig(self.rect_ids[y][x], fill=col or self._checker(x, y))
        self._update_hotspot_visual()
        self._update_mini_preview()
        self._schedule_save()

    def _has_pixels(self):
        return any(c is not None for row in self.pixels for c in row)

    # ------------------------------------------------------ GÖRSEL YÜKLE --
    def import_image(self):
        file_path = filedialog.askopenfilename(
            title=T("İmleç İçin Görsel Seç"),
            filetypes=[(T("Görsel Dosyaları"), "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.ico"),
                       (T("Tüm Dosyalar"), "*.*")]
        )
        if not file_path:
            return
        if Image is None:
            self.status_label.configure(text=T("Görsel desteği hazırlanıyor (Pillow), lütfen bekleyin..."))
            self.root.update_idletasks()
        if load_pillow() is None:
            messagebox.showerror(
                T("Pillow Bulunamadı"),
                T("Görsel yüklemek için gereken Pillow kütüphanesi kurulamadı.\n"
                  "İnternet bağlantınızı kontrol edip tekrar deneyin.")
            )
            return
        try:
            self.save_undo_state()
            self._place_image(file_path, self.auto_bg_var.get())
            name = os.path.basename(file_path)
            self.add_history("Görsel", name)
            extra = T(" Arka plan kaldırıldı.") if self.auto_bg_var.get() else ""
            self.status_label.configure(
                text=T("'{name}' {n}x{n} piksel olarak aktarıldı ve geçmişe eklendi.{extra}",
                       name=name, n=self.grid, extra=extra))
        except Exception as e:
            if self.undo_stack:
                self.undo_stack.pop()
            messagebox.showerror(T("Görsel Hatası"), T("Görsel yüklenemedi:\n{e}", e=e))

    def _place_image(self, file_path: str, remove_bg: bool):
        """Görseli açar, (istenirse) arka planını kaldırır, kırpar, ızgaraya sığdırıp ortalar."""
        img = Image.open(file_path)
        img.seek(0)  # GIF ise ilk kare
        img = img.convert("RGBA")

        # 0) Düz/benzer renkli arka planı orijinal çözünürlükte kaldır
        if remove_bg:
            img = remove_image_background(img, self.tolerance_var.get())

        # 1) Görselin etrafındaki boş (şeffaf) kenarları kırp
        alpha_mask = img.getchannel("A").point(lambda a: 255 if a >= 32 else 0)
        bbox = alpha_mask.getbbox()
        if bbox:
            img = img.crop(bbox)

        # 2) En-boy oranını bozmadan ızgaraya sığdır
        n = self.grid
        w, h = img.size
        scale = min(n / w, n / h)
        nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
        resample = Image.Resampling.BOX if scale < 1 else Image.Resampling.NEAREST
        img = img.resize((nw, nh), resample)

        # 3) Ortala
        ox, oy = (n - nw) // 2, (n - nh) // 2
        self.pixels = [[None] * n for _ in range(n)]
        for y in range(nh):
            for x in range(nw):
                r, g, b, a = img.getpixel((x, y))
                if a >= 100:
                    self.pixels[oy + y][ox + x] = f"#{r:02X}{g:02X}{b:02X}"
        self.hotspot = [ox, oy]
        self.redraw_all()
        # Tuval bu görselden geldi: "Arka Planı Kaldır" orijinal dosyayı kullanabilsin
        self._import_src = (file_path, n, encode_pixels(self.pixels))

    # ---------------------------------------------------------- .CUR --
    def build_cur_bytes(self) -> bytes:
        n = self.grid
        hx, hy = self.hotspot
        row_bytes = ((n + 31) // 32) * 4  # AND maskesi satırı 4 bayta hizalı olmalı

        xor_bytes = bytearray()
        and_bytes = bytearray()
        for y in range(n - 1, -1, -1):  # BMP satırları alttan üste
            bits = bytearray(row_bytes)
            for x in range(n):
                col = self.pixels[y][x]
                if col is None:
                    xor_bytes.extend((0, 0, 0, 0))
                    bits[x // 8] |= 0x80 >> (x % 8)
                else:
                    r, g, b = hex_to_rgb(col)
                    xor_bytes.extend((b, g, r, 255))
            and_bytes.extend(bits)

        dib_header = struct.pack(
            "<IiiHHIIiiII", 40, n, n * 2, 1, 32, 0,
            len(xor_bytes) + len(and_bytes), 0, 0, 0, 0
        )
        image_data = dib_header + xor_bytes + and_bytes
        dim = n if n < 256 else 0
        icondir = struct.pack("<HHH", 0, 2, 1)
        icondirentry = struct.pack("<BBBBHHII", dim, dim, 0, 0, hx, hy, len(image_data), 6 + 16)
        return icondir + icondirentry + image_data

    def export_cur_dialog(self):
        file_path = filedialog.asksaveasfilename(
            title=T("İmleci Kaydet"),
            defaultextension=".cur",
            filetypes=[(T("Windows İmleç Dosyası"), "*.cur")]
        )
        if not file_path:
            return
        try:
            with open(file_path, "wb") as f:
                f.write(self.build_cur_bytes())
            self.add_history("Kaydedildi", os.path.basename(file_path))
            self.status_label.configure(text=T("Kaydedildi: {name}", name=os.path.basename(file_path)))
        except Exception as e:
            messagebox.showerror(T("Kayıt Hatası"), T("Dosya kaydedilemedi:\n{e}", e=e))

    # ------------------------------------------------- SİSTEME UYGULA --
    def _target_ids(self):
        mode = self.target_cursor_mode.get()
        if mode == "hand":
            return [OCR_HAND]
        if mode == "cross":
            return [OCR_CROSS]
        if mode == "all":
            return [OCR_NORMAL, OCR_HAND, OCR_CROSS, OCR_IBEAM]
        return [OCR_NORMAL]

    def _backup_reg_value(self, name):
        """Windows'un orijinal değerini ilk değişiklikten önce bir kez yedekler."""
        backup = self.settings.setdefault("cursor_backup", {})
        if name not in backup:
            value, typ = reg_read(name)
            backup[name] = [value, typ]

    def apply_cursor_to_system(self):
        if sys.platform != "win32":
            messagebox.showwarning(T("Platform Uyarısı"), T("Sistem imleci değiştirme yalnızca Windows'ta çalışır."))
            return
        if not self._has_pixels():
            messagebox.showwarning(T("Uyarı"), T("Tamamen boş bir imleç uygulayamazsınız! Lütfen önce çizim yapın."))
            return

        cur_bytes = self.build_cur_bytes()
        target_ids = self._target_ids()
        cursor_dir = os.path.join(self.data_path, "cursors")
        stamp = time.strftime("%Y%m%d_%H%M%S") + f"_{int(time.time() * 1000) % 1000:03d}"

        try:
            # Kalıcı yöntem: imleç dosyasını AppData'ya kaydet ve kayıt defterine yaz.
            # Windows açılışta imleçleri buradan okuduğu için yeniden başlatınca da kalır.
            for cid in target_ids:
                role = ROLE_NAMES[cid]
                path = os.path.join(cursor_dir, f"{role}_{stamp}.cur")
                with open(path, "wb") as f:
                    f.write(cur_bytes)
                for old in os.listdir(cursor_dir):
                    if old.startswith(role + "_") and old != os.path.basename(path):
                        try:
                            os.remove(os.path.join(cursor_dir, old))
                        except OSError:
                            pass
                self._backup_reg_value(role)
                reg_write(role, path)

            size = self.screen_size.get()
            if size.isdigit():
                import winreg
                self._backup_reg_value("CursorBaseSize")
                reg_write("CursorBaseSize", int(size), winreg.REG_DWORD)

            reload_system_cursors()
            self._save_now()
            self.add_history("Uygulandı", self._mode_label())
            self.status_label.configure(
                text=T("İmleç uygulandı ve kalıcı olarak kaydedildi. Bilgisayar yeniden başlasa da kalacak."))
        except Exception as e:
            # Kayıt defterine yazılamazsa eski (geçici) yöntemle en azından şimdilik uygula
            try:
                temp_path = os.path.join(tempfile.gettempdir(), "pixel_cursor_active.cur")
                with open(temp_path, "wb") as f:
                    f.write(cur_bytes)
                user32 = ctypes.windll.user32
                user32.LoadCursorFromFileW.restype = ctypes.c_void_p
                user32.SetSystemCursor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
                for cid in target_ids:
                    hcursor = user32.LoadCursorFromFileW(temp_path)
                    if hcursor:
                        user32.SetSystemCursor(hcursor, cid)
                self.status_label.configure(
                    text=T("İmleç uygulandı ama kalıcı kaydedilemedi ({e}). Yeniden başlatınca sıfırlanabilir.", e=e))
            except Exception as e2:
                messagebox.showerror(T("Sistem Hatası"), T("İmleç uygulanırken hata oluştu:\n{e}", e=e2))

    def _mode_label(self):
        return {"normal": "Standart ok", "hand": "El imleci", "cross": "Nişangah",
                "all": "Tüm imleçler"}.get(self.target_cursor_mode.get(), "")

    def restore_default_cursors(self):
        if sys.platform != "win32":
            return
        try:
            backup = self.settings.get("cursor_backup", {})
            for name, (value, typ) in backup.items():
                if value is None:
                    reg_delete(name)
                else:
                    reg_write(name, value, typ)
            self.settings["cursor_backup"] = {}
            self._save_now()
            reload_system_cursors()
            cursor_dir = os.path.join(self.data_path, "cursors")
            for f in os.listdir(cursor_dir):
                try:
                    os.remove(os.path.join(cursor_dir, f))
                except OSError:
                    pass
            self.status_label.configure(text=T("Varsayılan Windows imleci geri yüklendi."))
        except Exception as e:
            messagebox.showerror(T("Sistem Hatası"), T("Varsayılan imleç geri yüklenemedi:\n{e}", e=e))

    # ------------------------------------------- KAYIT / OTURUM --
    def _schedule_save(self):
        if self._save_job is not None:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(1500, self._save_now)

    def _save_now(self):
        if self._save_job is not None:
            try:
                self.root.after_cancel(self._save_job)
            except tk.TclError:
                pass
        self._save_job = None
        self.settings.update({
            "version": 2,
            "grid": self.grid,
            "pixels": encode_pixels(self.pixels),
            "hotspot": self.hotspot,
            "color": self.current_color,
            "target_mode": self.target_cursor_mode.get(),
            "screen_size": self.screen_size.get() if self.screen_size.get().isdigit() else "",
            "lang": LANG,
            "brush": self.brush_var.get(),
            "tolerance": self.tolerance_var.get(),
            "auto_bg": self.auto_bg_var.get(),
        })
        try:
            write_json(self.state_file, self.settings)
        except Exception:
            pass

    def _restore_last_session(self) -> bool:
        s = self.settings
        if not s.get("pixels"):
            return False
        try:
            self.pixels = decode_pixels(s["pixels"], self.grid)
            hx, hy = s.get("hotspot", [0, 0])
            self.hotspot = [min(hx, self.grid - 1), min(hy, self.grid - 1)]
            self.color_preview.configure(bg=self.current_color)
            self.redraw_all()
            self.status_label.configure(text=T("Son çalışman geri yüklendi."))
            return True
        except Exception:
            return False

    def on_close(self):
        if getattr(self, "_poll_job", None) is not None:
            try:
                self.root.after_cancel(self._poll_job)
            except tk.TclError:
                pass
        if self._save_job is not None:
            self.root.after_cancel(self._save_job)
        self._save_now()
        self.root.destroy()

    # ---------------------------------------------------------- GEÇMİŞ --
    def add_history(self, kind: str, name: str = ""):
        entry = {
            "time": time.strftime("%d.%m.%Y %H:%M"),
            "kind": kind,
            "name": name,
            "grid": self.grid,
            "hotspot": self.hotspot[:],
            "pixels": encode_pixels(self.pixels),
        }
        if self.history and all(self.history[0].get(k) == entry[k] for k in ("grid", "hotspot", "pixels")):
            self.history[0].update(time=entry["time"], kind=kind, name=name or self.history[0].get("name", ""))
        else:
            self.history.insert(0, entry)
            del self.history[HISTORY_LIMIT:]
        self._save_history()
        self._render_history()

    def _save_history(self):
        try:
            write_json(self.history_file, self.history)
        except Exception:
            pass

    def clear_history(self):
        if not self.history:
            return
        if messagebox.askyesno(T("Geçmişi Temizle"), T("Tüm geçmiş silinsin mi?")):
            self.history = []
            self._save_history()
            self._render_history()

    def _thumb(self, entry):
        n = entry["grid"]
        img = tk.PhotoImage(width=n, height=n)
        px = decode_pixels(entry["pixels"], n)
        img.put(" ".join("{" + " ".join((c or "#11111B") for c in row) + "}" for row in px), to=(0, 0))
        factor = max(1, 48 // n)
        return img.zoom(factor) if factor > 1 else img

    def _render_history(self):
        for w in self.hist_inner.winfo_children():
            w.destroy()
        self._history_images = []
        if not self.history:
            tk.Label(self.hist_inner, text=T("Henüz geçmiş yok.\nGörsel yüklediğinde veya imleç\n"
                                              "uyguladığında burada görünür."),
                     fg=MUTED, bg=PANEL, font=("Segoe UI", 9), justify="left").pack(anchor="w", pady=8, padx=4)
            return
        kind_colors = {"Görsel": "#89B4FA", "Uygulandı": "#00F5D4", "Kaydedildi": "#F9E2AF"}
        for idx, entry in enumerate(self.history):
            try:
                thumb = self._thumb(entry)
            except Exception:
                continue
            self._history_images.append(thumb)
            card = tk.Frame(self.hist_inner, bg="#11111B", padx=6, pady=6)
            card.pack(fill="x", pady=3, padx=2)
            tk.Label(card, image=thumb, bg="#11111B").grid(row=0, column=0, rowspan=3, padx=(0, 8))
            tk.Label(card, text=T(entry.get("kind", "")), fg=kind_colors.get(entry.get("kind"), FG),
                     bg="#11111B", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w")
            name = T(entry.get("name", ""))
            if len(name) > 20:
                name = name[:19] + "…"
            tk.Label(card, text=f"{name}\n{entry.get('time', '')} · {entry['grid']}px",
                     fg=MUTED, bg="#11111B", font=("Segoe UI", 8), justify="left"
                     ).grid(row=1, column=1, sticky="w")
            btns = tk.Frame(card, bg="#11111B")
            btns.grid(row=2, column=1, sticky="w", pady=(3, 0))
            for text, cmd, color in (("Aç", lambda i=idx: self.load_history(i), BTN),
                                     ("Uygula", lambda i=idx: self.load_history(i, apply=True), "#00F5D4"),
                                     ("Sil", lambda i=idx: self.delete_history(i), "#45475A")):
                tk.Button(btns, text=T(text), command=cmd, bg=color,
                          fg="#11111B" if color == "#00F5D4" else FG,
                          relief="flat", font=("Segoe UI", 8), padx=6, pady=1,
                          cursor="hand2").pack(side="left", padx=(0, 4))

    def load_history(self, index: int, apply: bool = False):
        entry = self.history[index]
        self.save_undo_state()
        self.pixels = decode_pixels(entry["pixels"], entry["grid"])
        self.hotspot = list(entry.get("hotspot", [0, 0]))
        if entry["grid"] != self.grid:
            self.grid = entry["grid"]
            self._build_canvas_cells()
        self.redraw_all()
        self.status_label.configure(
            text=T("Geçmişten açıldı: {name}", name=T(entry.get("name") or entry.get("kind", ""))))
        if apply:
            self.notebook.select(0)
            self.apply_cursor_to_system()

    def delete_history(self, index: int):
        del self.history[index]
        self._save_history()
        self._render_history()

    # -------------------------------------------------------- ŞABLONLAR --
    def _apply_template(self, pixels32, hotspot32, record_undo=True):
        """Şablonlar 32x32 tasarlandı; seçili tuval boyutuna büyütülür."""
        if record_undo:
            self.save_undo_state()
        n = self.grid
        self.pixels = resample_pixels(pixels32, n) if n != 32 else pixels32
        self.hotspot = [hotspot32[0] * n // 32, hotspot32[1] * n // 32]
        self.redraw_all()

    def _load_template_arrow(self, record_undo=True):
        p = [[None] * 32 for _ in range(32)]
        for i in range(1, 16):
            for j in range(1, i + 1):
                if i >= 12 and j > 6:
                    continue
                if j == 1 or j == i or (i == 11 and j > 5) or (i == 15 and j <= 6):
                    p[i][j] = "#000000"
                else:
                    p[i][j] = "#00F5D4"
        self._apply_template(p, [1, 1], record_undo)

    def _load_template_sword(self):
        p = [[None] * 32 for _ in range(32)]
        for i in range(2, 18):
            p[i][i] = "#FFFFFF"
            p[i - 1][i] = "#8ECAE6"
            p[i][i - 1] = "#2B2D42"
        for k in range(-3, 4):
            p[18 - k][18 + k] = "#FFB703"
        for s in range(19, 23):
            p[s][s] = "#9B5DE5"
        self._apply_template(p, [2, 2])

    def _load_template_crosshair(self):
        p = [[None] * 32 for _ in range(32)]
        c = 15
        p[c][c] = "#FF0055"
        for offset in range(3, 9):
            for dx, dy in ((offset, 0), (-offset, 0), (0, offset), (0, -offset)):
                p[c + dy][c + dx] = "#00F566"
                p[c + dy + (1 if dx else 0)][c + dx + (1 if dy else 0)] = "#000000"
        self._apply_template(p, [c, c])


if __name__ == "__main__":
    # Derleme betiğinin kullandığı komutlar (arayüz açmadan çalışır)
    if len(sys.argv) >= 2 and sys.argv[1] == "--bump-version":
        print(bump_version_in_file(os.path.abspath(__file__), sys.argv[2] if len(sys.argv) > 2 else ""))
        sys.exit(0)
    if len(sys.argv) >= 2 and sys.argv[1] == "--make-version-json":
        folder = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__))
        print(json.dumps(make_version_json(folder), indent=2))
        sys.exit(0)

    _hide_own_console()
    root = tk.Tk()
    apply_window_icon(root)
    app = PixelCursorStudio(root)
    # Pillow eksikse arayüzü bekletmeden arka planda sessizce kur
    if not pillow_available():
        threading.Thread(target=install_pillow_silently, daemon=True).start()
    root.mainloop()
