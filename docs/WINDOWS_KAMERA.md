# Windows'ta kamera listesi ve görüntü sorunu (0.1.1)

## Yeni ZIP ile kurulum

1. ZIP'i normal bir klasöre çıkarın; ZIP'in içinden çalıştırmayın.
2. **KUR_WINDOWS.bat** dosyasını çalıştırın. Python 3.12+ gerekir. İlk kurulum/yükseltme bağımlılık indirmek için internet kullanır.
3. **BASLAT_WINDOWS.bat** ile açın. Pencere başlığında **0.1.1** yazdığını kontrol edin; eski program penceresini kapatın.
4. Kamera sekmesindeki listede USB, dahili ve Windows'un sağladığı sanal kameralar adlarıyla görünür. USB cihazını sonradan taktıysanız **Bağlı kameraları yenile** düğmesine basın.
5. Kamerayı adıyla seçin; yöntem **Otomatik**, çözünürlük **640×480**, FPS **30** ile başlatın. Önizleme için projeksiyon veya kalibrasyon gerekmez.

Bu sürüm Media Foundation ve DirectShow üzerinden cihazları sistemden listeler; kamera açarak ilk birkaç indeksi tahmin etmez. Listeye girmek erişim izni veya görüntü garantisi değildir: kullanımda/engelli bir cihaz da listelenebilir. Aynı cihaz iki yöntemde görülürse sistem cihaz yolu ile eşleştirilir; aynı isimde iki fiziksel kamera birbirine karıştırılmaz. Eşleşemeyen sanal aygıt uçları ayrı satır olarak görünebilir.

Otomatik açılış ilk gerçek kareyi doğrular. İstenen çözünürlük/FPS ile görüntü alınmazsa kamerayı kapatıp varsayılan biçimiyle yeniden açmayı, sonra aynı cihazın diğer Windows yöntemini dener. Alt bilgi açılan yöntemi ve cihazın bildirdiği değerleri gösterir. Yöntemler arasında indisler farklı olabilir; kamera adıyla seçim önerilir.

## Hâlâ görüntü gelmiyorsa

- Windows **Ayarlar → Gizlilik ve güvenlik → Kamera** içinde **Kamera erişimi**, **Uygulamaların kameranıza erişmesine izin ver** ve **Masaüstü uygulamalarının kameranıza erişmesine izin ver** seçeneklerini açın. Windows 10'da ilgili bölüm **Ayarlar → Gizlilik → Kamera** altındadır.
- Kamera, Teams, Zoom, Discord, OBS ve tarayıcı görüntülü görüşmelerini kapatın. Bazı sürücüler aynı anda tek uygulamaya izin verir.
- Önce Windows'un **Kamera** uygulamasıyla aygıtı deneyin; testten sonra bu uygulamayı kapatın. Orada da çalışmıyorsa fiziksel gizlilik kapağını/anahtarını, USB portunu, Aygıt Yöneticisi'ni ve sürücüyü kontrol edin.
- **Kamera yöntemi** alanında önce **Media Foundation**, sonra **DirectShow** ile ayrı ayrı deneyin. Listede seçilen kameranın o yöntemde ucu yoksa yanlış indeksteki başka bir kamera açılmaz; açıklama gösterilir.
- Eski ayarları sıfırlamak için yöntemi Otomatik seçin ve 640×480 / 30 FPS kullanın. Profil eşleşmesi değişebileceği için görüntü geldikten sonra kalibrasyonu yeniden yapın.
- Başlatma sürücünün içinde takılı kalırsa Durdur düğmesini kullanın. Sürücü kapanmıyorsa programı yeniden başlatın; arka planda bloke olmuş `read()` çağrısının zorla kesildiği iddia edilmez.

## Destek için rapor

Gelişmiş → **Tanılama ve hata raporu kaydet** seçeneği kamera kimliği, yöntem ve açılış durumunu da kaydeder. Kamera listesini GUI olmadan almak için proje klasöründe:

```powershell
.\.venv\Scripts\python.exe -m projection_pen --list-cameras
```

Listede cihaz adları, işletim sisteminin sağladığı cihaz yolları ve yöntem başına indeksler JSON olarak yazdırılır. Cihaz yolu donanım seri bilgisi içerebilir; raporu paylaşmadan önce kontrol edin. Bu komut kamera görüntüsü veya video kaydetmez.
