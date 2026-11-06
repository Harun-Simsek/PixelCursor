# PixelCursor Studio

**[Türkçe](#türkçe) · [English](#english)**

![PixelCursor](ikon.png)

---

## Türkçe

32x32, 48x48 veya 64x64 piksel fare imleçleri çizip **tek tıkla Windows'a uygulayabileceğin** küçük bir masaüstü uygulaması.

### İndir ve çalıştır (Python gerekmez)

1. Bu sayfada **`PixelCursor.exe`** dosyasına tıkla → sağ üstteki **indir (⬇)** butonuna bas.
2. İndirilen dosyaya çift tıkla.
3. Windows "Windows bilgisayarınızı korudu" derse: **Ek bilgi → Yine de çalıştır**.
   (Uygulama dijital olarak imzalı olmadığı için bu uyarı sadece ilk açılışta çıkar.)

### Özellikler

- **32x32, 48x48 veya 64x64** piksel çizim alanı: kalem, silgi, boya kovası, renk seçici
- Tıklama noktası (hotspot) ayarı
- Hazır şablonlar: Neon Ok, Kılıç, Nişangah
- PNG / JPG / WEBP / GIF görselleri piksel imlece dönüştürme
  (boş kenarlar kırpılır, en-boy oranı korunur, tuvale ortalanır)
- **Arka plan kaldırma:** görsel yüklenirken düz veya degrade arka plan otomatik silinir;
  istersen sonradan **Arka Planı Kaldır** düğmesiyle tek tıkla da yapabilirsin
- **Sihirli silgi:** tıkladığın renge benzeyen bitişik bölgeyi tek seferde siler
- **Alan silgisi:** sürükleyerek çizdiğin dikdörtgenin içini siler
- **Fırça boyutu** (1 / 2 / 3 / 5) ve **Tolerans** ayarı (silmenin ne kadar hassas olacağı)
- `.cur` olarak dışa aktarma
- İmleci sisteme uygulama (normal ok, el, nişangah veya hepsi) ve tek tıkla varsayılana dönme
- **Kalıcı imleç:** uygulanan imleç bilgisayar yeniden başlasa da kalır
- **Ekranda boyut:** imleci Windows'ta 32 / 48 / 64 piksel büyüklüğünde gösterebilirsin
- **Otomatik kayıt:** uygulamayı kapatıp açtığında son çalışman kaldığı yerden devam eder
- **Geçmiş sekmesi:** yüklenen görseller, kaydedilen ve uygulanan imleçler küçük
  önizlemeleriyle listelenir; tek tıkla açılır veya uygulanır
- Geri al (Ctrl+Z)

Ayarlar ve geçmiş `%APPDATA%\PixelCursorStudio` klasöründe tutulur.

### Kaynak koddan çalıştırma

Python 3 kuruluysa `PixelCursor.pyw` dosyasına çift tıklaman yeterli. Komut penceresi açılmaz;
Pillow eksikse arka planda sessizce kurulur.

### EXE'yi kendin derlemek

Python kurulu bir Windows bilgisayarda `EXE_Olustur.bat` dosyasına çift tıkla.
PyInstaller kurulur ve aynı klasörde `PixelCursor.exe` oluşturulur.

### Lisans

MIT — özgürce kullanabilir, değiştirebilir ve dağıtabilirsin.

---

## English

A small desktop app for drawing 32x32, 48x48 or 64x64 pixel-art mouse cursors and **applying them to Windows with one click**.

### Download and run (no Python needed)

1. On this page, click **`PixelCursor.exe`** → press the **download (⬇)** button in the top right.
2. Double-click the downloaded file.
3. If Windows shows "Windows protected your PC": click **More info → Run anyway**.
   (The app isn't digitally signed, so this warning only appears the first time.)

### Features

- **32x32, 48x48 or 64x64** pixel canvas: pencil, eraser, paint bucket, color picker
- Click point (hotspot) setting
- Built-in templates: Neon Arrow, Sword, Crosshair
- Turn PNG / JPG / WEBP / GIF images into pixel cursors
  (empty borders are cropped, aspect ratio is kept, image is centered)
- **Background removal:** solid or gradient backgrounds are removed automatically on import;
  you can also do it later with the **Remove Background** button
- **Magic eraser:** removes the connected area of similar color in one click
- **Area eraser:** drag a rectangle to clear everything inside it
- **Brush size** (1 / 2 / 3 / 5) and **Tolerance** setting (how strict erasing is)
- Export as `.cur`
- Apply the cursor to Windows (normal arrow, hand, crosshair or all) and restore the default with one click
- **Persistent cursor:** the applied cursor stays after restarting the computer
- **On-screen size:** show the cursor at 32 / 48 / 64 pixels in Windows
- **Auto-save:** when you reopen the app, your last work is right where you left it
- **History tab:** imported images, saved and applied cursors are listed with small
  previews; open or apply any of them with one click
- Undo (Ctrl+Z)

> The app interface is in Turkish. Settings and history are stored in `%APPDATA%\PixelCursorStudio`.

### Run from source

If Python 3 is installed, just double-click `PixelCursor.pyw`. No console window opens;
Pillow is installed silently in the background if it's missing.

### Build the EXE yourself

On a Windows PC with Python installed, double-click `EXE_Olustur.bat`.
It installs PyInstaller and creates `PixelCursor.exe` in the same folder.

### License

MIT — free to use, modify and distribute.
