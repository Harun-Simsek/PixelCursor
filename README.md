# PixelCursor Studio

32x32 piksel fare imleçleri çizip **tek tıkla Windows'a uygulayabileceğin** küçük bir masaüstü uygulaması.

![PixelCursor ikonu](ikon.png)

## İndir ve çalıştır (Python gerekmez)

1. Sağ taraftaki **Releases** bölümünden en son sürüme gir (ya da depo adresinin sonuna `/releases/latest` ekle).
2. **`PixelCursor.exe`** dosyasını indir ve çift tıkla.
3. Windows "Windows bilgisayarınızı korudu" derse: **Ek bilgi → Yine de çalıştır**.
   (Uygulama dijital olarak imzalı olmadığı için bu uyarı sadece ilk açılışta çıkar.)

## Özellikler

- **32x32, 48x48 veya 64x64** piksel çizim alanı: kalem, silgi, boya kovası, renk seçici
- Tıklama noktası (hotspot) ayarı
- Hazır şablonlar: Neon Piksel Ok, RPG Piksel Kılıç, FPS Nişangah
- PNG / JPG / WEBP / GIF görselleri piksel imlece dönüştürme
  (boş kenarlar kırpılır, en-boy oranı korunur, tuvale ortalanır)
- `.cur` olarak dışa aktarma
- İmleci sisteme uygulama (normal ok, el, nişangah veya hepsi) ve tek tıkla varsayılana dönme
- **Kalıcı imleç:** uygulanan imleç bilgisayar yeniden başlasa da kalır
- **Ekranda boyut:** imleci Windows'ta 32 / 48 / 64 piksel büyüklüğünde gösterebilirsin
- **Otomatik kayıt:** uygulamayı kapatıp açtığında son çalışman kaldığı yerden devam eder
- **Geçmiş sekmesi:** yüklenen görseller, kaydedilen ve uygulanan imleçler küçük
  önizlemeleriyle listelenir; tek tıkla açılır veya uygulanır
- Geri al (Ctrl+Z)

Ayarlar ve geçmiş `%APPDATA%\PixelCursorStudio` klasöründe tutulur.

## Kaynak koddan çalıştırma

Python 3 kuruluysa `PixelCursor.pyw` dosyasına çift tıklaman yeterli. Komut penceresi açılmaz;
Pillow eksikse arka planda sessizce kurulur.

## EXE'yi kendin derlemek

Depoya her yeni değişiklik gönderildiğinde GitHub Actions exe'yi otomatik derleyip Releases'a koyar.
Kendi bilgisayarında derlemek için: Python kurulu bir Windows'ta `EXE_Olustur.bat` dosyasına çift tıkla.

## Lisans

MIT — özgürce kullanabilir, değiştirebilir ve dağıtabilirsin.
