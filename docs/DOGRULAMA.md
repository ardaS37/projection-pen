# Bu teslimatta yapılan doğrulama

- Python 3.12.14, PySide6 6.12.0, NumPy 2.5.4, OpenCV contrib headless 4.14.0.94, pytest 9.2.0.
- Linux bulut ortamı; Qt `offscreen` platformu. USB kamera ve fiziksel projeksiyon bağlı değildi.
- Editable paket kurulumu ve `projection-pen` komutu doğrulandı. `pip check` bağımlılık sorunu bildirmedi.
- Otomatik testler HSV/ışık değişimi, renk aralığı sarması, çoklu nesne, uç ofseti, tam yüzey maskesi, takip kaybı, atlanan yeniden yakalama karesi, homography/profil, ArUco, PDF, PNG alfa/silgi/geri al/yinele, oturum, sentetik kamera→GUI→çizim ve video sonunu kapsar.
- `projection-pen --smoke-test` simülasyonla açıldı, çizdi ve normal kapandı.
- Qt kontrol paneli ve projeksiyon ekranı görüntüleri üretildi; simülasyon çizgisi ve önizleme kontrol edildi.
- 1280×720 sentetik takip benchmark'ı, 300 kare: ortalama yaklaşık 1,71 ms, yüzde 95 yaklaşık 1,79 ms. Bu kamera/GUI/projeksiyon dahil FPS veya fiziksel gecikme ölçümü değildir.
- Windows/Linux CI iş akışı depoya dahil edilmiştir. Çalıştırılan platform sonuçları ayrıca GitHub Actions üzerinden incelenmelidir.
- Fiziksel eşleme hatası, gerçek 30/60 kamera FPS'si, Windows/X11 global F8, şeffaf overlay'in compositor davranışı ve KDE Wayland donanım kabul testleri bu ortamda doğrulanmadı. Prosedür `DONANIM_TESTI.md` içindedir.

## 0.1.1 kamera düzeltmesi

- Yerel doğrulama: 44 test geçti; gerçek X sunucusu gerektiren tek test offscreen koşusunda atlandı.
- Yeni testler: altıdan fazla kamera listeleme, cihaz adları, aynı adlı iki aygıt, Windows yöntemleri arasında farklı indeksler, farklı arayüz GUID'leri, açılıp görüntü vermeyen kamera, varsayılan biçime dönüş, kaynakların serbest bırakılması ve arayüz seçimi.
- Listelenen aygıtların gerçek kullanıcının Windows bilgisayarında açılması uzaktan doğrulanamaz; bunun için `WINDOWS_KAMERA.md` içindeki adımlar ve tanılama komutu eklendi.
