# Bilinen sınırlamalar ve geliştirme yönleri

## Bu sürümdeki sınırlar

- Tek RGB kamera yüzey temasını güvenilir ölçmez. Sürekli mod kalem havadayken de çizer. Manuel mod kullanıcının çizim kapısını yönetmesini gerektirir.
- Deneysel temas modu yalnız projeksiyon koordinatındaki hareket hızını ve birkaç karelik kararlılığı kullanır. Gölge/derinlik/sinir ağı analizi yapmaz. Havada yavaş hareketi temas sanabilir; hızlı yazıyı reddedebilir. Varsayılan kapalıdır.
- Aynı renkte projeksiyon içeriği, mürekkep veya giysi yanlış tespit üretebilir. Alan/şekil/konum/hız filtreleri ve yüzey maskesi sorunu azaltır; çözüm garantisi yoktur. Hareketli projeksiyon içeriğini fiziksel kalemden kesin ayıran bir model uygulanmamıştır.
- Kamera pozlaması/beyaz dengesi backend'e bağlıdır. Desteklenmeyen ayarlar bildirilir; sayısal pozlama değerinin birimi cihazdan cihaza değişir. Otomatik pozlama ani ışık değişiminde maskeyi bozabilir.
- Nesne seçimi tek kalem içindir; çoklu kullanıcı/kalem yoktur. İşaretleyici merkezi + sabit ofset kullanılır; dönen kalemin gerçek uç pozu çözülmez.
- Homography düzlem varsayar. Lens distorsiyonu, bükülmüş yüzey, havadaki uç ve kenar ekstrapolasyonu hata üretir. Kamera hareket algılama uygulanmamıştır.
- Kare yakalama/işleme için yalnız son kare tutulur. Kamera sürücüsü ve USB cihazı yine kendi tamponunda gecikme biriktirebilir. İşleme FPS'si kameranın gerçek FPS'siyle aynı değildir.
- Kamera sürücüsünün bloke olan `read()` çağrısını Python iş parçacığında güvenle zorla kesmek mümkün değildir. Arayüz durdurmada sınırlı süre bekler; sürücü kapanmazsa uygulamayı yeniden başlatmak gerekebilir.
- Şeffaf overlay standart pencere yöneticisi isteklerini kullanır; exclusive fullscreen, güvenli masaüstü ve yönetici yetkili uygulamalar üstünde garanti vermez. KDE Wayland'da global kısayol yoktur; uygulama içi PDF/görüntü güvenilir alternatiftir. Normal masaüstü ekran yakalama gerektirmez.
- Global F8 Windows/X11 için uygulanmıştır; gerçek iki platform masaüstünde fiziksel kabul testi gerekir. Diğer OS'lerde uygulama odaktayken F8 ve panel düğmesi kullanılabilir.
- PNG dışa aktarımı mürekkebi ve isteğe göre uygulama zeminini içerir. Overlay'in altındaki başka uygulamayı yakalamaz. Oturum JSON'u harici arka plan dosyalarını gömmez.
- Silgi gerçek alfa silgidir; silinen eski çizgi geri al ile geri gelir. Temizleme geri alınamaz. Uzun oturumlarda vektör noktaları bellekte büyür; PNG veya oturum kaydedip temizleyin.
- Geri alma/sayfa yükleme sırasında çizgiler yeniden rasterize edilir. Çok büyük belgelerde ve yüksek DPI'da bu kısa GUI duraklaması yapabilir.
- Dokunma/fare emülasyonu, işletim sistemi genelinde tıklama, PPTX işleme, otomatik ekran içeriği yakalama, basınç algılama ve paketlenmiş exe/rpm bu sürüme dahil değildir.

## Deneysel temas ölçümü

Gelişmiş sekmesinde gerçek fiziksel teması gözleyerek **Gerçek temas var** etiketini açın/kapatın ve **Temas etiketlerini kare başına kaydet** kutusunu açın. Tahmin her işlenen karede etiketle karşılaştırılır. Rapor TP/FP/TN/FN sayımlarını içerir:

- Yanlış pozitif oranı: FP / (FP + TN).
- Yanlış negatif oranı: FN / (FN + TP).
- İlgili örnek sınıfı yoksa oran `null` olur; sıfır hata diye sunulmaz.

Elle etiketleme insan tepki gecikmesi taşır. Hem uzun temas/hava bölümleri hem geçişler ölçülmeli; bir oturumun doğruluğu farklı ışık ve kullanıcılara genellenmemelidir. Kamera kaybı ve yüzey dışındaki örneklerde temas tahmini false olur.

## Sonraki geliştirmeler

1. Gerçek donanım ölçümleriyle HSV/alan/hız ve filtre parametrelerini ayarlama; sensör-projeksiyon gecikmesini yüksek hızlı video ile ölçme.
2. Checkerboard ile kamera intrinsics/lens düzeltmesi ve çok referanslı sağlam homography uyumu.
3. Kalem ucunda küçük IR LED, fiziksel anahtar/pedal veya ikinci kamerayla gerçek çizim kapısı.
4. KDE portal/global shortcut entegrasyonu ve gerekirse KWin'e özel overlay desteği.
5. Yönlü işaretleyici ile kalem pozu/uç ofseti, otomatik kamera hareket uyarısı ve projeksiyon paraziti modelleme.
6. Bölgesel yeniden çizim, nokta sadeleştirme, oturum otomatik kurtarma ve Windows/Fedora paketleri.
