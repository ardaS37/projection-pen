# Kalibrasyon rehberi

## Hazırlık

Projeksiyon ve kamerayı sabitleyin. Kamera yüzeyi tamamıyla görmeli; işaretleyicinin birkaç pikselden büyük görünmesini sağlayın. Projeksiyon ekranındaki otomatik keystone/yakınlaştırma/çözünürlük ayarlarını kalibrasyondan sonra değiştirmeyin. Çok eğik kamera veya geniş açılı lens kenarlarda hata oluşturur; bu sürüm lens distorsiyonunu düzeltmez.

Kalibrasyon düz bir yüzey varsayar. Kamera ve projeksiyon farklı açılarda olabilir; yüzey eğriyse tek homography yeterli değildir.

## Dört nokta

1. Kamerayı başlatın ve doğru projeksiyon ekranını seçin.
2. **Kalibrasyon hedeflerini göster** düğmesine basın. Dört siyah/beyaz ArUco hedefi görünür; merkezleri sırasıyla 1 sol üst, 2 sağ üst, 3 sağ alt, 4 sol alttır.
3. Otomatik seçim için hedeflerin tümü kamera görüntüsünde okunurken **ArUco ile otomatik kalibre et** düğmesine basın. Başarısız olursa manuel yöntemi kullanın; uygulama uydurma noktalarla devam etmez.
4. Manuel yöntemde **Manuel köşe seçimini başlat** önizlemeyi dondurur. Kamera görüntüsünde dört hedefin **merkezlerine**, 1→2→3→4 sırasıyla tıklayın. Son seçimi geri alabilirsiniz. Son tıklamada dönüşüm hesaplanır. Yanlış sıra/dejenere dörtgen reddedilir.
5. Hedefler kaybolur. Kalemi yüzeye yakın hareket ettirerek turkuaz takip imlecini kontrol edin. Mürekkep oluşturmak için çizim kapısını açın.

Hedefler ekran kenarından içeridedir; dönüşüm tüm projeksiyon yüzeyine uzatılır. Kamera maskesi dönüşümün tersinden bulunan tam yüzey sınırını kullanır. Kenara doğru ekstrapolasyon hatası artabilir; doğrulama yapın.

## Uç ofseti

Varsayılan tespit renkli nesnenin kontur ağırlık merkezidir. Uçla aynı değildir. İşaretleyiciyi uca yaklaştırın. Gelişmiş sekmesindeki X/Y ofsetleri **kamera pikseli** olarak ağırlık merkezine eklenir; sonra perspektif dönüşümü yapılır. Önizleme, gerçek uç ile tahmini noktayı karşılaştırmak için kullanılabilir.

Sabit ofset yalnız kalem yönü ve işaretleyicinin uca uzaklığı yaklaşık sabitken işe yarar. Kalem havadayken kamera/projeksiyon arasındaki paralaks giderilmez. Kalibrasyon hedeflerini seçerken işaretleyici ofsetini hedef merkezine eklemeyin; hedefler yüzey noktalarını tanımlar.

## Bağımsız doğrulama

**5 noktalı doğrulama başlat** ekranın dört bölgesinde ve merkezinde sırayla hedef gösterir. Bunlar dönüşümü kuran görüntü hedeflerinden ayrı, kalem ucuyla yapılan ölçümlerdir. Her hedefte gerçek ucu merkeze yerleştirip **Hedefte 15 kare örnekle** düğmesine basın. On beş ardışık geçerli tespitin ortalaması alınır; arada takip kaybolursa o örnek birikimi sıfırlanır. Beklerken kalemi sabit tutun.

Her hedefte ölçülen kamera konumu projeksiyon piksellerine dönüştürülür. Öklid uzaklıklarının ortalaması ve maksimumu raporlanır. Dört uyum noktasında sıfıra yakın artık hata tek başına iyi kalibrasyon kanıtı değildir.

Milimetre istiyorsanız örnekleme bitmeden **tam yansıtılan alanın** gerçek genişlik ve yüksekliğini girin. Boş/0 bırakıldığında yalnız piksel raporlanır. Sonuç, piksel eksenlerini bu ölçülere ölçekleyerek yaklaşık mm hesaplar; keystone, eğri yüzey ve lens hatalarını telafi etmez.

Raporu Gelişmiş → **Tanılama ve hata raporu kaydet** ile JSON olarak alın. Ölçüm noktaları ve nokta başına piksel hataları dahildir.

## Profil ve yeniden kalibrasyon

Profili JSON olarak kaydedin. Kamera yeniden başlatıldıktan sonra profil kendiliğinden uygulanmaz; uygun profili yükleyin. Kamera kaynağı, gerçek kamera çözünürlüğü ve ekran geometrisi/DPI eşleşmelidir. Eşleşmeyen profil reddedilir. Uç ofseti de profilde saklanır.

Ekran/çözünürlük değişirse çizim durur ve kalibrasyon geçersizleşir. Kamera fiziksel olarak taşınırsa bu sürüm bunu otomatik algılayamaz: yeniden kalibre edin. Aynı isim/indeksle başka kamera bağlanması da profilin fiziksel doğruluğunu garanti etmez.
