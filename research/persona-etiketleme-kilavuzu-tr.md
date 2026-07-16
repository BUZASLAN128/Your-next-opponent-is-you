# Kişilik Etiketleme Kılavuzu

Bu kılavuz, özel 24+8 etiketleme paketini Türkçe olarak tamamlamak içindir.
Paket Git dışında kalır. Formda model önerisi bulunmaz ve bu aşama tek başına
kişilik benzerliği kalitesi kanıtlamaz.

## Önce Ne Yapacağım?

1. Özel paketteki `review.md` dosyasını aç.
2. Her kartı sırayla ve bağımsız değerlendir. Bazı kartlar kör tekrar olabilir;
   önceki yanıtını bulmaya veya kopyalamaya çalışma.
3. Aynı klasördeki `labels.template.json` dosyasında, aynı kart kimliğine ait
   zorunlu karar alanlarını doldur. Koşullu alanları yalnız gerçekten
   uygulanıyorsa doldur; aksi durumda `null` bırak.
4. Kart kimliklerini, kanıt metnini, talimatları ve sabit alan adlarını
   değiştirme.
5. Tüm kartlar bitince üst düzey `completed_by` alanını `represented_user` yap.
6. Göndermeden önce yerel kopyayı denetle. İlk gönderim değiştirilemez olarak
   mühürlenir.

## Karar Kuralları

- Yapısal `user` rolü, sözün sana ait olduğunu tek başına kanıtlamaz.
- Alıntı, yapıştırılmış metin, üçüncü kişiye ait ifade veya karışık metin
  kişilik kanıtı sayılmaz.
- Bir ifadeyi bugün benimsemiyorsan `adoption=endorsed` kullanma.
- Emin değilsen ilgili alanlarda `unknown`, ayrıca `should_abstain=true` ve
  `exclude_from_persona=true` kullan. Nedenini `exclusion_reason` alanına yaz.
- `rationale_spans` ve `evidence_demand_spans`, hedef metindeki karakter
  aralığını ve o aralıktaki metnin birebir kopyasını taşımalıdır.
- `persona_kind` yalnız `target_layer=persona` olduğunda kullanılır.

## Sabit Değerler

JSON alan adları ve değerleri teknik sözleşmedir; aşağıdaki İngilizce
karşılıkları aynen kullan.

Yeni Türkçe form `persona-labels/0.2` sürümünü kullanır. Önceden üretilmiş
`persona-labels/0.1` formları, kendi özgün talimatlarıyla geriye dönük olarak
doğrulanmaya devam eder.

| Alan | Değer | Türkçe anlamı |
| --- | --- | --- |
| `authorship` | `self` | Söz bana ait |
|  | `quoted_or_pasted` | Alıntı veya yapıştırma |
|  | `mixed` / `other` / `unknown` | Karışık / başkasına ait / bilinmiyor |
| `claim_holder` | `self` / `assistant` / `third_party` | İddia bana / asistana / üçüncü kişiye ait |
|  | `mixed` / `unknown` | Karışık / bilinmiyor |
| `adoption` | `endorsed` / `rejected` | Hâlen benimsiyorum / reddediyorum |
|  | `hypothetical` / `not_applicable` / `unknown` | Varsayım / uygulanamaz / bilinmiyor |
| `decision` | `accept` / `reject` / `correct` | Kabul / ret / düzeltme |
|  | `defer` / `ask` / `none` / `unknown` | Erteleme / soru / karar yok / bilinmiyor |
| `target_layer` | `persona` / `project_rule` | Kişilik / proje kuralı |
|  | `architecture` / `mission` / `episodic` | Mimari / misyon / olaysal hafıza |
|  | `research` / `none` / `unknown` | Araştırma / katman yok / bilinmiyor |
| `persona_kind` | `trait` / `value` / `narrative` | Nitelik / değer / anlatı |
|  | `metacognition` / `belief` / `preference` | Üstbiliş / inanç / tercih |
|  | `goal` / `relationship` / `skill` | Hedef / ilişki / beceri |
| `confidence` | `high` / `medium` / `low` / `unknown` | Yüksek / orta / düşük / bilinmiyor |
| `scope.risk` | `low` / `medium` / `high` / `unknown` | Düşük / orta / yüksek / bilinmiyor |

`scope.project`, `scope.role`, `scope.audience` ve `scope.temporal` alanları
yalnız karar gerçekten bu kapsamlarla sınırlıysa doldurulur; aksi durumda
`null` kalır.

## Gönderim ve Kör Tekrar Uzlaştırması

Teknik durum kodları otomasyon uyumluluğu için İngilizce kalır. Komut çıktısı
aynı zamanda `message_tr` ve `next_step_tr` alanlarında Türkçe açıklama verir.

~~~powershell
# Bu iki değeri kendi yerel çıktınla değiştir.
$OzelKok = 'C:\git-disinda\ynoy-private'
$CalismaKimligi = 'BURAYA_STUDY_ID'
uv run ynoy --private-root $OzelKok study submit-labels $CalismaKimligi
~~~

Kör tekrarların ilk yanıtları uyuşuyorsa etiketler doğrudan mühürlenir.
Uyuşmuyorsa ilk yanıtlar korunur ve `repeat-adjudication.template.json`
oluşturulur:

1. `initial_judgments` alanlarına dokunma.
2. Her uyuşmazlık için `final_judgment` alanını nihai kararınla doldur.
3. `adjudication_reason` alanına kısa bir gerekçe yaz.
4. `completed_by` alanını `represented_user` yap.
5. Son etiketi mühürle:

~~~powershell
uv run ynoy --private-root $OzelKok study seal-labels $CalismaKimligi
~~~

## Bu Aşamadan Sonra

Etiketler mühürlenmeden saklı değerlendirme kümesi açılmaz. Mühürleme de kendi
başına kişilik kalitesi sonucu değildir. Sonraki aşamada saklı konuşmalar için
yinelenen içerik denetimi yapılır, hedefleri görmeyen tahminler dondurulur ve
ancak daha sonra temsil edilen kullanıcının gerçek hedefleriyle puanlama
yapılır.
