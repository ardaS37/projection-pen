# Donanım kabul ve performans testi

Bu belge fiziksel test prosedürüdür; testin burada yapıldığını göstermez. Önce otomatik testleri ve simülasyonu çalıştırın.

## Kurulum kaydı

OS/sürüm, X11/Wayland, CPU, kamera modeli/USB portu, talep edilen/gerçek çözünürlük-FPS, projeksiyon çözünürlüğü/DPI, yüzey ölçüleri, mesafeler, ışık ve HSV ayarlarını kaydedin. Aynı donanımla tekrarlamak için kalibrasyon ve oturum profillerini saklayın.

## Kabul adımları

| Test | İşlem | Beklenen |
| --- | --- | --- |
| Kamera | İki kamera arasında geçin, 640×480 ve 1280×720 deneyin | GUI yanıt verir; gerçek değerler görünür; eski kalibrasyon kullanılmaz |
| Renk | Yeşil işaretleyiciyi örnekleyin; ışığı kademeli değiştirin | Maske izlenebilir; kayıpta mürekkep durur |
| Aynı renk | Kalem takip edilirken ikinci yeşil nesne ekleyin | Yakındaki mevcut nesne tercih edilir; büyük sıçramada çizgi kesilir |
| Kalibrasyon | Dört hedefi önce manuel, sonra ArUco ile seçin | Tutarlı eşleme; bulunamayan hedeflerde açık hata |
| Fiziksel doğruluk | Beş bağımsız hedefte ucun temas konumunu örnekleyin | Ortalama/maksimum ve nokta hataları piksel olarak raporlanır |
| Yüzey kenarı | Kenarların yakınında küçük daireler çizin | Doğru fiziksel bölgede görünür; hatayı ayrıca kaydedin |
| Kayıp | İki çizgi arasında işaretleyiciyi kapatıp açın | Aradaki boşlukta bağlayıcı çizgi yok |
| Kontrol | Manuel kapıyı kapatın/açın; odak başka uygulamadayken F8 deneyin | Windows/X11 kayıt başarılıysa global kontrol; yeni çizgi ayrı başlar |
| Overlay | Tarayıcı/sunum üzerinde çizip fareyle sunumu yönetin | Mürekkep görünür; fare alt uygulamaya ulaşır |
| Wayland | PDF ve görüntü zemini açın | Uygulama içinde çizim; global F8 vaadi yok |
| Kayıt | Silgi/geri al/yinele sonrası JSON ve iki PNG kaydedin | Açılan oturum eşdeğer; şeffaf PNG zeminsiz |
| Kopma | Kamerayı/projeksiyonu çıkarın | Çökmez; çizim durur; ekran değişiminde yeniden kalibrasyon istenir |
| Uzun kullanım | 30–60 dakika yazın, arada kaydedin | UI yanıt verir; hata/kare yaşı ve bellek büyümesi kaydedilir |

Doğruluk hedefini donanımı ölçmeden kesinleştirmeyin. Başlangıç değerlendirmesi için beş hedefte ortalama ≤10 px ve maksimum ≤20 px bir **deneme eşiği** olarak kullanılabilir; bu yazılım tarafından sağlandığı iddia edilen sonuç değildir. Görüntü boyutu, işaretleyici büyüklüğü ve kalem ofsetine göre uygun eşik belirleyin.

## Gecikme/FPS

30 FPS ve kamera gerçekten destekliyorsa 60 FPS için ayrı koşu yapın. 640×480, 1280×720 ve 1920×1080 deneyin. Kamera/işleme FPS'si, ortalama ve yüzde 95 işleme/yazılım yaşı değerlerini tanılama JSON'undan çıkarın. Kamera tarafından bildirilen 60 FPS tek başına 60 gerçek kare kanıtı değildir.

`tools/benchmark.py` yalnız sentetik takip maliyetini ölçer; donanım veya uçtan uca gecikme testi değildir. İşleme FPS'sini artırmak gerçek kameranın hızını artırmaz.

Fiziksel uçtan uca gecikme için kalemin hareket başlangıcını ve duvardaki dijital tepkiyi aynı yüksek hızlı videoda kaydedin. Aradaki kare farkını video FPS'sine bölün. Yazılım panelindeki süreye projeksiyon/sensör gecikmesi dahil değildir.

## Işık ve yanlış pozitif matrisi

Aynı hareketleri düşük/normal/parlak oda ışığı, beyaz/siyah zemin, hareketli sunum ve yeşil dijital içerikle tekrarlayın. Fiziksel kalem sahnede yokken 60 saniye izleyip yanlış çizimleri sayın. Pozlama ve beyaz dengesini sabitleyerek karşılaştırın. Yeşil mürekkebi stres testi için kullanın; normal kullanımda takip renginden farklı mürekkep seçin.

Deneysel temas için sabit havada tutma, yüzeye yakın havada çizme, yavaş/hızlı temaslı çizme örneklerini elle etiketleyin. Hata oranlarını raporlayın; bu testin başarısızlığı manuel modu etkilememelidir.
