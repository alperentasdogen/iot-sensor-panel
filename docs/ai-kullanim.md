# Yapay Zeka Kullanımı

Bu projede yapay zeka, ürünün içinde bir özellik olarak değil, **geliştirme aracı** olarak
kullanılmaktadır. Yaklaşım "vibe coding" değil, "agentic engineering"dir: yapay zeka kod ve
doküman önerir ya da yazar; her çıktı geliştirici tarafından incelenir, testlerle doğrulanır
ve gerektiğinde düzeltilir veya reddedilir. Kararları geliştirici verir.

## Kullanılan Araç

| Araç | Model | Nasıl kullanıldı |
|---|---|---|
| Claude Code (Claude masaüstü uygulaması) | Claude Opus | Proje klasöründe çalışan bir ajan olarak: dosyaları okuma, kod ve test yazma, testleri ve analiz araçlarını çalıştırma, commit hazırlama |

## Kullanım Alanları

- **Tasarım:** Modül yapısı (`collector/`, `storage/`), veritabanı şeması, mesaj doğrulama kuralları.
- **Kod yazımı:** Subscriber, depolama katmanı, ayar modülündeki eklemeler.
- **Test yazımı:** Birim testleri, sahte (fake) MQTT istemcileri, uçtan uca entegrasyon testi.
- **Hata ayıklama ve kontrol:** Ortamın incelenmesi (Mosquitto ayarları, dinlenen portlar), testlerin tekrar tekrar çalıştırılarak kararsızlık aranması.
- **Dokümantasyon:** README, mimari, zorluklar ve bu belge.

## Çalışma Kuralları

Yapay zekaya oturum başında şu kurallar verildi ve her adımda uygulandı:

1. Adım adım ilerlemek; bir adım bitmeden diğerine geçmemek ve her adımı Türkçe açıklamak.
2. Kod yazmadan önce mevcut dosyaları incelemek; önemli kararları gerekçesiyle açıklamak.
3. Her mantıksal değişikliği ayrı bir commit yapmak (Conventional Commits).
4. Commit öncesi `ruff check`, `ruff format --check` ve `pytest` çalıştırmak.
5. Dosyaları `git add` ile tek tek eklemek; `.env` dosyasını asla commit'lememek.

## Çıktılar Nasıl Doğrulandı

| Yöntem | Ne sağlar |
|---|---|
| `pytest` (birim + entegrasyon testleri) | Kodun beklenen davranışı gösterdiğini kanıtlar |
| `ruff check` ve `ruff format` | Stil ve olası hata kalıplarını yakalar |
| `bandit` | Güvenlik açığı kalıplarını tarar |
| Gerçek broker ile uçtan uca çalıştırma | Testlerin göremediği entegrasyon sorunlarını ortaya çıkarır |
| Geliştiricinin diff incelemesi | Her commit'ten önce değişiklik okunur |

## Yapay Zeka Çıktısının Düzeltildiği veya Yönlendirildiği Örnekler

1. **Hatalı çalıştırma talimatı geliştirici tarafından yakalandı.** Yapay zekanın README'ye
   yazdığı `mosquitto -p 1883` komutu, Mosquitto zaten servis olarak çalıştığı için hata
   veriyordu. Geliştirici bunu fark edip düzeltilmesini istedi (`26d2536`).
2. **Plan dışı bir adım geliştirici kararıyla çıkarıldı.** Planda broker'a parola eklemek
   vardı. Geliştirici gerek olmadığına karar verdi; yapay zeka uygulamadan önce broker'ın
   yalnızca localhost'u dinlediğini doğruladı ve karar gerekçesiyle belgelendi
   (bkz. `docs/zorluklar.md`, madde 6).
3. **Test yazarken mevcut kodda bir sorun bulundu.** Entegrasyon testi planlanırken sabit
   MQTT istemci kimliğinin çalışan bir subscriber'ı düşüreceği fark edildi. Test yazılmadan
   önce bu ayrı bir commit ile düzeltildi (`66c0f86`).
4. **Biçim hataları araçla yakalandı.** Yapay zekanın yazdığı test dosyaları birkaç kez
   `ruff format --check` kontrolünden geçemedi ve commit'ten önce biçimlendirildi.
5. **Kararsız test riski ölçüldü.** Zamanlamaya bağlı entegrasyon testi yazıldıktan sonra
   20 kez üst üste çalıştırıldı; hiç başarısız olmadığı görüldükten sonra commit edildi.
6. **Commit stratejisi geliştirici tarafından değiştirildi.** İlk çalışmada subscriber tek
   bir büyük commit olarak eklendi. Sonrasında geliştirici her mantıksal değişikliğin ayrı
   commit olmasını kural haline getirdi.

## Sınırlar

- Yapay zeka, broker ayarlarını değiştirmek veya parola girmek gibi sistem düzeyindeki
  işlemleri geliştiricinin yerine yapmaz; bu adımlar geliştiriciye bırakılır.
- Yapay zekanın yazdığı her satır geliştiricinin sorumluluğundadır. Sunumda koda hakimiyet
  sorgulanacağı için her önemli karar bu belgede ve `docs/mimari.md` içinde gerekçesiyle
  yazılmıştır.
