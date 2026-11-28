# P0016 - Industrial IoT Sensor Monitoring Dashboard

## Proje Hakkında
Bu proje, endüstriyel ortamlardaki sensör verilerinin MQTT protokolü üzerinden gerçek zamanlı izlenmesini amaçlayan bir IoT uygulamasıdır.

## Projenin Amacı
Sıcaklık, nem, titreşim ve motor akımı gibi sensör verilerini simüle ederek merkezi bir kontrol panelinde görüntülemek, geçmiş ölçümleri kaydetmek ve belirlenen eşik değerleri aşıldığında alarm oluşturmaktır.

## Kullanılan Teknolojiler
- Python 3.13
- MQTT / Mosquitto
- FastAPI
- SQLite
- Streamlit
- Plotly
- Pytest
- Git ve GitHub

## Planlanan Özellikler
- Python ile sensör verisi simülasyonu
- MQTT üzerinden gerçek zamanlı veri iletimi
- Canlı sensör grafikleri
- SQLite veritabanına veri kaydı
- Alarm ve eşik değeri kontrolü
- Geçmiş sensör verilerinin görüntülenmesi

## Tamamlanan Çalışmalar
- Python geliştirme ortamı oluşturuldu.
- Gerekli Python paketleri yüklendi.
- Sensör simülatörü geliştirildi (cihaz kimliği ayarlanabilir).
- `.env` tabanlı, doğrulamalı ayar modülü eklendi (`config.py`).
- Birden fazla cihaz için MQTT publisher geliştirildi (`simulator/publisher.py`).
- MQTT subscriber geliştirildi: `factory/+/telemetry` dinlenir, gelen mesajlar doğrulanır ve SQLite'a kaydedilir (`collector/subscriber.py`, `storage/database.py`).
- 56 otomatik test yazıldı; Mosquitto ile uçtan uca deneme yapıldı.

## Çalıştırma
Mosquitto, Windows kurulumunda servis olarak 1883 portunda otomatik çalışır; ayrıca başlatılmasına gerek yoktur. Servisin durumunu kontrol etmek için:
```powershell
Get-Service mosquitto
```
Ayar dosyasını oluşturun:
```powershell
copy .env.example .env
```
Ardından subscriber ve publisher'ı iki ayrı terminalde çalıştırın:
```powershell
python -m collector.subscriber
```
```powershell
python -m simulator.publisher
```
Ölçümler varsayılan olarak `data/sensors.db` dosyasına yazılır (`DATABASE_PATH` ile değiştirilebilir).

## Yapay Zeka Kullanımı
Projenin geliştirilmesinde Claude'dan yazılım mimarisi, Python kodları, hata ayıklama ve test geliştirme konularında destek alınmaktadır.

AI tarafından önerilen kodlar çalıştırılarak test edilmektedir.

## Proje Durumu
Geliştirme aşamasında.

## Geliştirilecek Modüller
1. MQTT haberleşmesi
2. Veritabanı ve API
3. Gerçek zamanlı dashboard
4. Alarm sistemi
5. Entegrasyon testleri
6. Kod kalitesi analizi
