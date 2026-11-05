# PixelCursor Studio

32x32 piksel fare imleçleri çizip **tek tıkla Windows'a uygulayabileceğin** küçük bir masaüstü uygulaması.

![PixelCursor ikonu](ikon.png)

## İndir ve çalıştır (Python gerekmez)

1. Sağ taraftaki **Releases** bölümünden en son sürüme gir (ya da depo adresinin sonuna `/releases/latest` ekle).
2. **`PixelCursor.exe`** dosyasını indir ve çift tıkla.
3. Windows "Windows bilgisayarınızı korudu" derse: **Ek bilgi → Yine de çalıştır**.
   (Uygulama dijital olarak imzalı olmadığı için bu uyarı sadece ilk açılışta çıkar.)

## Özellikler

- 32x32 piksel çizim alanı: kalem, silgi, boya kovası, renk seçici
- Tıklama noktası (hotspot) ayarı
- Hazır şablonlar: Neon Piksel Ok, RPG Piksel Kılıç, FPS Nişangah
- PNG / JPG / WEBP görselleri piksel imlece dönüştürme
- `.cur` olarak dışa aktarma
- İmleci sisteme uygulama (normal ok, el, nişangah veya hepsi) ve tek tıkla varsayılana dönme
- Geri al (Ctrl+Z)

## Kaynak koddan çalıştırma

Python 3 kuruluysa `PixelCursor.pyw` dosyasına çift tıklaman yeterli. Komut penceresi açılmaz;
Pillow eksikse arka planda sessizce kurulur.

## EXE'yi kendin derlemek

Depoya her yeni değişiklik gönderildiğinde GitHub Actions exe'yi otomatik derleyip Releases'a koyar.
Kendi bilgisayarında derlemek için: Python kurulu bir Windows'ta `EXE_Olustur.bat` dosyasına çift tıkla.

## Lisans

MIT — özgürce kullanabilir, değiştirebilir ve dağıtabilirsin.
