# Karşılaşılan Zorluklar ve Çözümler

Geliştirme sırasında karşılaşılan sorunlar, nedenleri ve nasıl çözüldükleri. Her madde,
ilgili commit ile birlikte verilmiştir.

## 1. Broker'ı ikinci kez başlatmaya çalışan çalıştırma talimatı

- **Sorun:** README'deki çalıştırma adımlarında `mosquitto -p 1883` komutu vardı. Mosquitto
  Windows'ta kurulumla birlikte servis olarak 1883 portunda zaten çalıştığı için bu komut
  "address in use" hatasıyla duruyordu.
- **Çözüm:** Komut kaldırıldı, yerine servisin durumunu gösteren `Get-Service mosquitto`
  eklendi. Talimatlar, hangi komutun ayrı terminal gerektirdiği açık olacak şekilde bölündü.
- **Commit:** `26d2536 docs: fix broker step in README run instructions`

## 2. Aynı istemci kimliğiyle bağlanan istemcilerin birbirini düşürmesi

- **Sorun:** Publisher ve subscriber'ın MQTT istemci kimliği koda sabit yazılmıştı. MQTT
  protokolünde broker, aynı kimlikle yeni bir istemci bağlandığında eskisinin bağlantısını
  kapatır. Entegrasyon testi çalışan bir subscriber'ın yanında aynı kimlikle bağlansaydı,
  çalışan subscriber kopacaktı.
- **Çözüm:** `create_client` fonksiyonlarına isteğe bağlı `client_id` parametresi eklendi;
  varsayılan değerler korunarak mevcut kullanım bozulmadı. Testler her çalıştırmada benzersiz
  kimlik kullanır.
- **Commit:** `66c0f86 feat: allow overriding the MQTT client id`

## 3. SQLite bağlantısının başka bir thread'den kullanılamaması

- **Sorun:** Entegrasyon testinde subscriber arka plan thread'inde çalışmalıydı. Python'un
  `sqlite3` modülü varsayılan olarak bir bağlantının yalnızca onu oluşturan thread'de
  kullanılmasına izin verir; ana thread'de açılan bağlantıyla kayıt yapılamazdı.
- **Çözüm:** Bağlantı, subscriber'ın çalıştığı thread'in içinde açıldı. Bu, gerçek
  `subscriber.run()` fonksiyonunun yaptığıyla aynıdır (`loop_forever` mesajları aynı thread'de
  işler). Test, veritabanını kendi ayrı bağlantısıyla okur.
- **Commit:** `748d350 test: add end-to-end MQTT integration tests`

## 4. Entegrasyon testinin gerçek ortamı etkilemesi ve kararsızlık riski

- **Sorun:** Test, geliştirme sırasında da kullanılan aynı broker'a bağlanır. Aynı topic'leri
  kullansaydı çalışan publisher'ın mesajlarını kaydeder, sayımlar tutmazdı. Ayrıca mesajın
  gelmesini sabit süre (`sleep`) beklemek yavaş makinede testi rastgele başarısız yapabilirdi.
- **Çözüm:**
  - Her test kendi topic önekini (`test-<rastgele>`) ve geçici veritabanını kullanır.
  - Sabit bekleme yerine koşul en fazla 5 saniye boyunca tekrar tekrar kontrol edilir.
  - Test 20 kez üst üste çalıştırıldı, hiç başarısız olmadı.
  - Broker yoksa (örneğin CI ortamında) testler hata vermek yerine atlanır.
- **Commit:** `748d350 test: add end-to-end MQTT integration tests`

## 5. Geçersiz veya sahte mesajların veritabanına girmesi

- **Sorun:** Broker'a bağlanabilen herkes herhangi bir topic'e mesaj yazabilir. Doğrulama
  yapılmazsa bozuk JSON subscriber'ı durdurabilir ya da yanlış veri kaydedilebilir.
  Python'a özgü iki tuzak da vardı:
  - `json.loads` standart dışı `NaN` ve `Infinity` değerlerini kabul eder.
  - `bool`, `int`'in alt sınıfıdır; `"temperature": true` sayı kontrolünden geçer.
- **Çözüm:** `parse_reading` fonksiyonu mesajı kaydetmeden önce doğrular:
  - Cihaz kimliği topic ile eşleşmeli; bir cihaz başka cihaz adına veri yazamaz.
  - Zaman damgasında saat dilimi olmalı.
  - Ölçümler sonlu sayı olmalı; `bool` açıkça reddedilir.

  Geçersiz mesaj loglanıp atlanır, subscriber çalışmaya devam eder.
- **Commit:** `3ddcdeb feat: add MQTT subscriber that stores readings in SQLite`

## 6. Broker güvenliği: parola gerekli mi?

- **Soru:** Plan, Mosquitto'da anonim erişimi kapatıp parola tanımlamayı içeriyordu.
- **İnceleme:** Mosquitto ayar dosyasında `listener` tanımı yoktu. 1883 portunun yalnızca
  `127.0.0.1` ve `::1` adreslerinde dinlediği `Get-NetTCPConnection` ile doğrulandı.
  Mosquitto 2.x bu durumda ağdan gelen bağlantıları kabul etmez.
- **Karar:** Broker yalnızca yerel makineden erişilebilir olduğu için parola eklenmedi. Kod
  `MQTT_USERNAME` / `MQTT_PASSWORD` ayarlarıyla kimlik doğrulamaya hazırdır; broker ağa
  açılırsa yalnızca `.env` doldurulur.
